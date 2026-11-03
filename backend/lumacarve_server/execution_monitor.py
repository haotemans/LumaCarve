"""Bounded real execution timeline, owned by the single Python GPU worker.

This module never imports Torch, probes CUDA, logs prompts or stores filesystem
paths. A GPU worker may attach a measured PyTorch allocator snapshot at a
completed phase boundary. Read-only API calls only copy existing events.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
import threading
import time
import uuid
from typing import Any, Callable, Iterator

STAGES = frozenset({
    "job", "model_unload", "model_load", "lora_update",
    "inference", "output_save", "te", "vae", "dit",
})
TERMINAL = frozenset({"completed", "failed", "cancelled"})


class ExecutionMonitor:
    def __init__(self, max_events: int = 80) -> None:
        self._lock = threading.RLock()
        self._events: deque[dict[str, Any]] = deque(maxlen=max(1, min(max_events, 200)))
        self._active: dict[str, dict[str, Any]] = {}
        self._local = threading.local()

    @contextmanager
    def bind_job(self, job_id: str) -> Iterator[None]:
        previous = getattr(self._local, "job_id", None)
        self._local.job_id = job_id
        try:
            yield
        finally:
            self._local.job_id = previous

    def begin(self, stage: str, *, model_id: str | None = None, job_id: str | None = None) -> str:
        if stage not in STAGES:
            raise ValueError("Unrecognized execution phase")
        token = uuid.uuid4().hex
        event = {
            "id": token, "stage": stage, "status": "running",
            "model_id": model_id, "job_id": job_id or getattr(self._local, "job_id", None),
            "started_at": time.time(), "ended_at": None,
            "duration_ms": None, "allocated_bytes": None, "reserved_bytes": None,
            "allocator_source": None, "_started_monotonic": time.perf_counter(),
        }
        with self._lock:
            self._active[token] = event
        return token

    @staticmethod
    def _allocator(torch: Any) -> tuple[int, int] | None:
        """Sample only an already-imported worker Torch; no CUDA synchronization."""
        if torch is None:
            return None
        try:
            cuda = torch.cuda
            allocated = int(cuda.memory_allocated())
            reserved = int(cuda.memory_reserved())
            if allocated < 0 or reserved < 0:
                return None
            return (allocated, reserved)
        except (AttributeError, RuntimeError, ValueError, TypeError):
            return None

    def finish(self, token: str, *, status: str = "completed", torch: Any = None) -> None:
        if status not in TERMINAL:
            raise ValueError("Invalid phase completion status")
        end = time.perf_counter()
        memory = self._allocator(torch)
        with self._lock:
            event = self._active.pop(token, None)
            if event is None:
                raise KeyError("Unknown execution phase token")
            event["status"] = status
            event["ended_at"] = time.time()
            event["duration_ms"] = max(0.0, round((end - event.pop("_started_monotonic")) * 1000, 2))
            if memory is not None:
                event["allocated_bytes"], event["reserved_bytes"] = memory
                event["allocator_source"] = "pytorch_process_allocator"
            self._events.append(event)

    @contextmanager
    def phase(
        self, stage: str, *, model_id: str | None = None,
        torch_provider: Callable[[], Any] | None = None,
    ) -> Iterator[None]:
        token = self.begin(stage, model_id=model_id)
        outcome = "completed"
        try:
            yield
        except BaseException as exc:
            outcome = "cancelled" if isinstance(exc, InterruptedError) else "failed"
            raise
        finally:
            torch = None
            if torch_provider is not None:
                try:
                    torch = torch_provider()
                except Exception:
                    pass
            self.finish(token, status=outcome, torch=torch)

    def snapshot(self, limit: int = 40) -> dict[str, Any]:
        if not 1 <= limit <= 80:
            raise ValueError("Invalid execution timeline limit")
        with self._lock:
            now = time.perf_counter()
            active = []
            for event in self._active.values():
                copy = {key: value for key, value in event.items() if not key.startswith("_")}
                copy["duration_ms"] = max(0.0, round((now - event["_started_monotonic"]) * 1000, 2))
                active.append(copy)
            events = [dict(event) for event in list(self._events)[-limit:][::-1]]
        return {
            "source": "python_worker_in_memory",
            "measured": bool(active or events),
            "active": active,
            "events": events,
            "phase_detail": {
                "te": "instrumentation_not_connected",
                "vae": "instrumentation_not_connected",
                "dit": "instrumentation_not_connected",
            },
        }
