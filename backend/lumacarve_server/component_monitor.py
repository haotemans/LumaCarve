"""Real Anima component observations; optional hooks never alter inference output.

GPU time uses CUDA events recorded around *actual* module forward calls and
resolved only after the existing end-of-inference CUDA synchronization. Without
CUDA events we retain observed host-dispatch time with an explicit label.
Parameter residency is a point-in-time device snapshot, not GPU allocator use.
"""
from __future__ import annotations

from contextlib import contextmanager
import time
from typing import Any, Iterator

COMPONENT_NAMES = {
    "te": ("text_encoder", "text_conditioner"),
    "vae": ("vae",),
    "dit": ("transformer",),
}


def _module(pipe: Any, names: tuple[str, ...]) -> Any | None:
    for name in names:
        try:
            module = getattr(pipe, name, None)
        except Exception:
            continue
        if module is not None and callable(getattr(module, "parameters", None)):
            return module
    return None


def component_residency(pipe: Any | None) -> list[dict[str, Any]]:
    """Read parameter devices at safe boundaries, not while CUDA is executing."""
    now = time.time()
    result: list[dict[str, Any]] = []
    for key, names in COMPONENT_NAMES.items():
        entry: dict[str, Any] = {
            "key": key, "state": "unknown", "gpu_weight_bytes": None,
            "cpu_weight_bytes": None, "source": "torch_parameter_device",
            "observed_at": now,
        }
        if pipe is None:
            entry.update(state="unloaded", gpu_weight_bytes=0, cpu_weight_bytes=0)
        else:
            module = _module(pipe, names)
            if module is not None:
                cpu = gpu = meta = total = 0
                seen: set[int] = set()
                try:
                    for item in list(module.parameters()) + list(module.buffers()):
                        if id(item) in seen:
                            continue
                        seen.add(id(item))
                        amount = int(item.numel()) * int(item.element_size())
                        device = str(item.device.type)
                        if device == "cuda":
                            gpu += amount
                        elif device == "cpu":
                            cpu += amount
                        else:
                            meta += amount
                        total += 1
                except Exception:
                    total = 0
                if total:
                    entry["gpu_weight_bytes"] = gpu
                    entry["cpu_weight_bytes"] = cpu
                    entry["state"] = (
                        "mixed" if gpu and cpu else "gpu" if gpu else
                        "cpu" if cpu else "offloaded" if meta else "unknown"
                    )
        result.append(entry)
    return result


class ComponentForwardProfiler:
    """Attach only to observable nn.Module forward calls, then fully remove hooks."""

    def __init__(self, torch: Any, pipe: Any):
        self.torch = torch
        self.pipe = pipe
        self.handles: list[Any] = []
        self.pending: dict[str, list[tuple[Any | None, float, float]]] = {}
        self.samples: dict[str, list[tuple[Any | None, Any | None, float, float, float]]] = {}
        self.connected: set[str] = set()

    def _cuda_event(self) -> Any | None:
        try:
            event = self.torch.cuda.Event(enable_timing=True)
            event.record()
            return event
        except Exception:
            return None

    def _attach(self, key: str, module: Any) -> None:
        if not callable(getattr(module, "register_forward_pre_hook", None)):
            return
        if not callable(getattr(module, "register_forward_hook", None)):
            return

        self.pending[key] = []
        self.samples[key] = []

        def pre(_module: Any, _args: Any) -> None:
            try:
                self.pending[key].append((self._cuda_event(), time.perf_counter(), time.time()))
            except Exception:
                pass

        def post(_module: Any, _args: Any, _output: Any) -> None:
            try:
                if not self.pending[key]:
                    return
                start_event, start_time, start_wall = self.pending[key].pop()
                end_event = self._cuda_event() if start_event is not None else None
                elapsed = max(0.0, (time.perf_counter() - start_time) * 1000)
                self.samples[key].append((start_event, end_event, elapsed, start_wall, time.time()))
            except Exception:
                pass

        try:
            before = module.register_forward_pre_hook(pre)
            try:
                after = module.register_forward_hook(post, always_call=True)
            except TypeError:
                after = module.register_forward_hook(post)
            self.handles.extend((before, after))
            self.connected.add(key)
        except Exception:
            if "before" in locals():
                before.remove()

    @contextmanager
    def instrument(self) -> Iterator[None]:
        for key, names in COMPONENT_NAMES.items():
            module = _module(self.pipe, names)
            if module is not None:
                self._attach(key, module)
        try:
            yield
        finally:
            for handle in self.handles:
                try:
                    handle.remove()
                except Exception:
                    pass
            self.handles.clear()

    def results(self) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """Call only after the pipeline's existing final CUDA synchronize."""
        observations: list[dict[str, Any]] = []
        status: dict[str, str] = {}
        for key in COMPONENT_NAMES:
            samples = self.samples.get(key, [])
            if not samples:
                status[key] = "hook_connected_no_calls" if key in self.connected else "hook_unavailable"
                continue
            gpu_elapsed = 0.0
            can_measure_gpu = True
            for start, end, _wall, _begin, _finish in samples:
                if start is None or end is None:
                    can_measure_gpu = False
                    break
                try:
                    gpu_elapsed += float(start.elapsed_time(end))
                except Exception:
                    can_measure_gpu = False
                    break
            if can_measure_gpu:
                elapsed = gpu_elapsed
                source = "cuda_events_sum"
                status[key] = "observed_cuda"
            else:
                elapsed = sum(sample[2] for sample in samples)
                source = "python_forward_dispatch_wall"
                status[key] = "observed_wall"
            observations.append({
                "key": key, "duration_ms": round(max(0.0, elapsed), 2),
                "calls": len(samples), "timing_source": source,
                "started_at": min(sample[3] for sample in samples),
                "ended_at": max(sample[4] for sample in samples),
            })
        return observations, status
