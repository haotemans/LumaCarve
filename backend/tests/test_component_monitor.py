"""CPU-only component observations and actual hook invocation contracts."""
import unittest
from types import SimpleNamespace

from lumacarve_server.component_monitor import (
    ComponentForwardProfiler, component_residency,
)


class Tensor:
    def __init__(self, device="cuda", n=16, size=2):
        self.device = SimpleNamespace(type=device)
        self._n, self._size = n, size

    def numel(self):
        return self._n

    def element_size(self):
        return self._size


class Hook:
    def __init__(self, hooks, func):
        self.hooks, self.func = hooks, func

    def remove(self):
        self.hooks.remove(self.func)


class Module:
    def __init__(self, device="cuda"):
        self._device = device
        self.pre = []
        self.post = []

    def parameters(self):
        return [Tensor(self._device)]

    def buffers(self):
        return []

    def register_forward_pre_hook(self, hook):
        self.pre.append(hook)
        return Hook(self.pre, hook)

    def register_forward_hook(self, hook, always_call=False):
        self.post.append(hook)
        return Hook(self.post, hook)

    def forward(self):
        for hook in list(self.pre):
            hook(self, ())
        for hook in list(self.post):
            hook(self, (), None)


class FakeCudaEvent:
    def __init__(self, enable_timing):
        self.timed = enable_timing

    def record(self):
        pass

    def elapsed_time(self, end):
        return 2.5


class FakeTorch:
    cuda = SimpleNamespace(Event=FakeCudaEvent)


class ComponentTests(unittest.TestCase):
    def test_residency_is_parameter_device_snapshot_not_vram_usage(self):
        pipe = SimpleNamespace(transformer=Module("cuda"), vae=Module("cpu"), text_encoder=Module("cuda"))
        items = {entry["key"]: entry for entry in component_residency(pipe)}
        self.assertEqual(items["dit"]["state"], "gpu")
        self.assertEqual(items["dit"]["gpu_weight_bytes"], 32)
        self.assertEqual(items["vae"]["state"], "cpu")
        self.assertEqual(items["vae"]["cpu_weight_bytes"], 32)
        self.assertEqual(items["te"]["gpu_weight_bytes"], 32)
        self.assertEqual(items["te"]["source"], "torch_parameter_device")

    def test_real_forward_hooks_and_cuda_event_source(self):
        pipe = SimpleNamespace(transformer=Module(), vae=Module(), text_encoder=Module())
        profiler = ComponentForwardProfiler(FakeTorch, pipe)
        with profiler.instrument():
            pipe.transformer.forward()
            pipe.transformer.forward()
            pipe.vae.forward()
        self.assertFalse(pipe.transformer.pre)
        self.assertFalse(pipe.transformer.post)
        samples, states = profiler.results()
        by_key = {s["key"]: s for s in samples}
        self.assertEqual(by_key["dit"]["calls"], 2)
        self.assertEqual(by_key["dit"]["duration_ms"], 5.0)
        self.assertEqual(by_key["dit"]["timing_source"], "cuda_events_sum")
        self.assertEqual(states["te"], "hook_connected_no_calls")
        self.assertNotIn("te", by_key)

    def test_unobservable_components_are_not_guessed(self):
        pipe = SimpleNamespace(transformer=object())
        profiler = ComponentForwardProfiler(FakeTorch, pipe)
        with profiler.instrument():
            pass
        samples, states = profiler.results()
        self.assertEqual(samples, [])
        self.assertEqual(states["dit"], "hook_unavailable")
        self.assertEqual({v["key"]: v["state"] for v in component_residency(pipe)}["dit"], "unknown")

    def test_no_pipeline_means_no_component_weights(self):
        items = component_residency(None)
        self.assertTrue(all(e["state"] == "unloaded" and e["gpu_weight_bytes"] == 0 for e in items))


if __name__ == "__main__":
    unittest.main()
