"""Memory-budget checks are admission estimates, never claims of CUDA peak use."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .graph import ExecutionPlan


@dataclass(frozen=True, slots=True)
class ComponentSpec:
    # Use a content/version/precision-aware key so incompatible weights never alias.
    key: str
    gpu_bytes: int
    cpu_bytes: int
    kind: str = "model"

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("Component key cannot be empty")
        if self.gpu_bytes < 0 or self.cpu_bytes < 0:
            raise ValueError("Component sizes must be nonnegative")


@dataclass(frozen=True, slots=True)
class MemoryBudget:
    gpu_total_bytes: int
    cpu_total_bytes: int
    # Reserve headroom for activations, CUDA allocations and transfer staging.
    gpu_reserve_bytes: int = 0
    cpu_reserve_bytes: int = 0

    def __post_init__(self) -> None:
        if min(
            self.gpu_total_bytes, self.cpu_total_bytes,
            self.gpu_reserve_bytes, self.cpu_reserve_bytes,
        ) < 0:
            raise ValueError("Memory budget values must be nonnegative")
        if self.gpu_reserve_bytes > self.gpu_total_bytes:
            raise ValueError("GPU reserve exceeds GPU capacity")
        if self.cpu_reserve_bytes > self.cpu_total_bytes:
            raise ValueError("CPU reserve exceeds system-memory capacity")

    @property
    def gpu_capacity(self) -> int:
        return self.gpu_total_bytes - self.gpu_reserve_bytes

    @property
    def cpu_capacity(self) -> int:
        return self.cpu_total_bytes - self.cpu_reserve_bytes


@dataclass(frozen=True, slots=True)
class BudgetEstimate:
    # Count of simultaneous component weights, not runtime activation/allocator peak.
    required_gpu_bytes: int
    budget_gpu_bytes: int
    over_budget_nodes: tuple[str, ...]

    @property
    def fits_estimated_weights(self) -> bool:
        return not self.over_budget_nodes


def preflight(plan: ExecutionPlan, specs: Mapping[str, ComponentSpec], budget: MemoryBudget) -> BudgetEstimate:
    highest = 0
    too_large: list[str] = []
    for step in plan.steps:
        required = 0
        for key in dict.fromkeys(step.components):
            if key not in specs:
                raise KeyError(f"Missing component specification: {key}")
            required += specs[key].gpu_bytes
        highest = max(highest, required)
        if required > budget.gpu_capacity:
            too_large.append(step.node_id)
    return BudgetEstimate(highest, budget.gpu_capacity, tuple(too_large))
