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
    def __init__(self, max_events: int = 80, event_sink: Callable[[dict[str, Any]], None] | None = None) -> None:
        self._lock = threading.RLock()
        self._events: deque[dict[str, Any]] = deque(maxlen=max(1, min(max_events, 200)))
        self._active: dict[str, dict[str, Any]] = {}
        self._local = threading.local()
        self._sink = event_sink
        self._component_status = {key: "instrumentation_not_connected" for key in ("te", "vae", "dit")}
        self._components: list[dict[str, Any]] = []

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
        self._publish({k: v for k, v in event.items() if not k.startswith("_")})
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

    def finish(self, token: str, *, status: str = "completed", torch: Any = None,
               duration_override_ms: float | None = None, timing_source: str | None = None,
               calls: int | None = None) -> None:
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
            if duration_override_ms is not None:
                event["duration_ms"] = max(0.0, round(duration_override_ms, 2))
            if timing_source is not None:
                event["timing_source"] = timing_source
            if calls is not None:
                event["calls"] = calls
            if memory is not None:
                event["allocated_bytes"], event["reserved_bytes"] = memory
                event["allocator_source"] = "pytorch_process_allocator"
            self._events.append(event)
        self._publish(dict(event))

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

    def _publish(self, event: dict[str, Any]) -> None:
        if self._sink is None:
            return
        try:
            self._sink(event)
        except Exception:
            pass  # Monitoring must never make an inference fail.

    def accept_remote_event(self, event: dict[str, Any]) -> None:
        """Called by supervisor receiving trusted child-process phase messages."""
        if event.get("stage") not in STAGES or not isinstance(event.get("id"), str):
            return
        with self._lock:
            item = dict(event)
            if item.get("status") == "running":
                item["_started_monotonic"] = time.perf_counter() - max(0, float(item.get("duration_ms") or 0)) / 1000
                self._active[item["id"]] = item
            elif item.get("status") in TERMINAL:
                self._active.pop(item["id"], None)
                self._events.append(item)

    def update_components(self, components: list[dict[str, Any]], phase_status: dict[str, str]) -> None:
        with self._lock:
            self._components = [dict(item) for item in components]
            self._component_status.update({key: value for key, value in phase_status.items() if key in self._component_status})

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
            status = dict(self._component_status)
            components = [dict(item) for item in self._components]
        return {
            "source": "python_worker_in_memory",
            "measured": bool(active or events),
            "active": active,
            "events": events,
            "phase_detail": status,
            "components": components,
        }
