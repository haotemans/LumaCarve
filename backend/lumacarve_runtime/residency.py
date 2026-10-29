"""Budgeted model residency: GPU hot, RAM warm, unloaded cold.

Pure Python policy layer. An adapter is responsible for *actual* torch tensor
moves, safetensors loading, CUDA synchronization and cleanup. No fake GPU
optimizations are performed here.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Any, Iterable, Iterator, Mapping, Protocol

from .budget import ComponentSpec, MemoryBudget


class Tier(str, Enum):
    COLD = "disk"
    WARM = "cpu"
    HOT = "gpu"


class InsufficientMemory(MemoryError):
    """No free budget and no safely evictable component remains."""


class ModelBackend(Protocol):
    """Operations must either succeed or leave the original object usable.

    load(HOT) should stream directly to GPU if the concrete backend supports it.
    The backend must account for transient staging memory and GPU synchronization.
    """

    def load(self, spec: ComponentSpec, target: Tier) -> Any: ...
    def move(self, spec: ComponentSpec, instance: Any, source: Tier, target: Tier) -> Any: ...
    def unload(self, spec: ComponentSpec, instance: Any, source: Tier) -> None: ...


@dataclass(slots=True)
class _Record:
    spec: ComponentSpec
    tier: Tier = Tier.COLD
    instance: Any = None
    leases: int = 0
    last_access: int = 0


@dataclass(frozen=True, slots=True)
class ResidencySnapshot:
    gpu_used_bytes: int
    cpu_used_bytes: int
    gpu_limit_bytes: int
    cpu_limit_bytes: int
    hot_keys: tuple[str, ...]
    warm_keys: tuple[str, ...]
    cold_keys: tuple[str, ...]
    leased_keys: tuple[str, ...]


class ModelResidencyManager:
    """Single-owner, thread-safe policy controller.

    A lease pins all requested components for its duration. Idle GPU models
    remain hot for reuse; memory pressure evicts least-recently-used idle
    models to RAM when possible, otherwise directly to disk/unloaded state.
    """

    def __init__(self, budget: MemoryBudget, backend: ModelBackend) -> None:
        self.budget = budget
        self.backend = backend
        self._lock = RLock()
        self._records: dict[str, _Record] = {}
        self._clock = 0
        self._gpu_used = 0
        self._cpu_used = 0

    def register(self, spec: ComponentSpec) -> None:
        with self._lock:
            if spec.key in self._records:
                if self._records[spec.key].spec != spec:
                    raise ValueError(f"Conflicting component spec for {spec.key}")
                return
            self._records[spec.key] = _Record(spec=spec)

    def _touch(self, record: _Record) -> None:
        self._clock += 1
        record.last_access = self._clock

    def _get(self, key: str) -> _Record:
        try:
            return self._records[key]
        except KeyError as exc:
            raise KeyError(f"Unregistered component: {key}") from exc

    def _unload(self, record: _Record) -> None:
        if record.tier == Tier.COLD:
            return
        original = record.tier
        # Do not update bookkeeping if the adapter fails to unload.
        self.backend.unload(record.spec, record.instance, original)
        if original == Tier.HOT:
            self._gpu_used -= record.spec.gpu_bytes
        else:
            self._cpu_used -= record.spec.cpu_bytes
        record.instance = None
        record.tier = Tier.COLD

    def _evict_hot(self, record: _Record) -> None:
        assert record.tier == Tier.HOT and record.leases == 0
        if record.spec.cpu_bytes <= self.budget.cpu_capacity:
            try:
                self._make_room(Tier.WARM, record.spec.cpu_bytes)
            except InsufficientMemory:
                pass
            else:
                instance = self.backend.move(record.spec, record.instance, Tier.HOT, Tier.WARM)
                record.instance = instance
                record.tier = Tier.WARM
                self._gpu_used -= record.spec.gpu_bytes
                self._cpu_used += record.spec.cpu_bytes
                self._touch(record)
                return
        self._unload(record)

    def _make_room(self, target: Tier, required_bytes: int) -> None:
        if target == Tier.HOT:
            used = self._gpu_used
            limit = self.budget.gpu_capacity
        elif target == Tier.WARM:
            used = self._cpu_used
            limit = self.budget.cpu_capacity
        else:
            raise ValueError("Cannot reserve cold storage")

        if required_bytes > limit:
            raise InsufficientMemory(
                f"{target.value} component needs {required_bytes} bytes; budget is {limit}"
            )
        while used + required_bytes > limit:
            candidates = (
                record for record in self._records.values()
                if record.tier == target and record.leases == 0
            )
            victim = min(candidates, key=lambda item: item.last_access, default=None)
            if victim is None:
                raise InsufficientMemory(
                    f"No idle {target.value} component can free {required_bytes} bytes"
                )
            if target == Tier.HOT:
                self._evict_hot(victim)
                used = self._gpu_used
            else:
                self._unload(victim)
                used = self._cpu_used

    def _ensure_hot(self, record: _Record) -> None:
        if record.tier == Tier.HOT:
            self._touch(record)
            return
        self._make_room(Tier.HOT, record.spec.gpu_bytes)
        if record.tier == Tier.COLD:
            instance = self.backend.load(record.spec, Tier.HOT)
        else:
            instance = self.backend.move(
                record.spec, record.instance, Tier.WARM, Tier.HOT
            )
            self._cpu_used -= record.spec.cpu_bytes
        record.instance = instance
        record.tier = Tier.HOT
        self._gpu_used += record.spec.gpu_bytes
        self._touch(record)

    @contextmanager
    def lease(self, keys: Iterable[str]) -> Iterator[Mapping[str, Any]]:
        """Pin a set of model components during an operation.

        Callers must synchronize any outstanding asynchronous CUDA work
        before leaving this context. The manager never evicts leased objects.
        """
        unique = tuple(dict.fromkeys(keys))
        with self._lock:
            records = [self._get(key) for key in unique]
            required = sum(record.spec.gpu_bytes for record in records)
            if required > self.budget.gpu_capacity:
                raise InsufficientMemory(
                    f"Requested component set needs {required} GPU bytes, "
                    f"but budget is {self.budget.gpu_capacity}"
                )
            # Pin the entire set before loading the first component.
            for record in records:
                record.leases += 1
            try:
                for record in records:
                    self._ensure_hot(record)
                handles = {record.spec.key: record.instance for record in records}
            except BaseException:
                for record in records:
                    record.leases -= 1
                raise
        try:
            yield handles
        finally:
            with self._lock:
                for record in records:
                    record.leases -= 1
                    self._touch(record)

    def warm(self, keys: Iterable[str]) -> None:
        """Explicit low-priority RAM prefetch; never demotes a hot component."""
        unique = tuple(dict.fromkeys(keys))
        with self._lock:
            records = [self._get(key) for key in unique]
            for record in records:
                if record.tier != Tier.COLD:
                    self._touch(record)
                    continue
                self._make_room(Tier.WARM, record.spec.cpu_bytes)
                instance = self.backend.load(record.spec, Tier.WARM)
                record.instance = instance
                record.tier = Tier.WARM
                self._cpu_used += record.spec.cpu_bytes
                self._touch(record)

    def unload_idle(self) -> None:
        """Optional explicit trim: release idle weights; never force every run."""
        with self._lock:
            for record in self._records.values():
                if record.leases == 0:
                    self._unload(record)

    def snapshot(self) -> ResidencySnapshot:
        with self._lock:
            return ResidencySnapshot(
                gpu_used_bytes=self._gpu_used,
                cpu_used_bytes=self._cpu_used,
                gpu_limit_bytes=self.budget.gpu_capacity,
                cpu_limit_bytes=self.budget.cpu_capacity,
                hot_keys=tuple(k for k, r in self._records.items() if r.tier == Tier.HOT),
                warm_keys=tuple(k for k, r in self._records.items() if r.tier == Tier.WARM),
                cold_keys=tuple(k for k, r in self._records.items() if r.tier == Tier.COLD),
                leased_keys=tuple(k for k, r in self._records.items() if r.leases > 0),
            )
