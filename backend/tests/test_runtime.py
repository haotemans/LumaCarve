"""Dependency-free tests; no CUDA hardware or PyTorch installation required."""
import unittest

from lumacarve_runtime import (
    ComponentSpec, InsufficientMemory, InvalidWorkflow, MemoryBudget,
    ModelResidencyManager, Tier, WorkflowNode, compile_workflow, preflight,
    run_plan,
)


class FakeBackend:
    def __init__(self):
        self.calls = []

    def load(self, spec, target):
        self.calls.append(("load", spec.key, target))
        return {"key": spec.key, "target": target}

    def move(self, spec, instance, source, target):
        self.calls.append(("move", spec.key, source, target))
        return {"key": spec.key, "target": target}

    def unload(self, spec, instance, source):
        self.calls.append(("unload", spec.key, source))


class RuntimeTests(unittest.TestCase):
    def manager(self, gpu=8, cpu=12):
        backend = FakeBackend()
        manager = ModelResidencyManager(MemoryBudget(gpu, cpu), backend)
        return manager, backend

    def test_dag_order_and_lifetime(self):
        plan = compile_workflow([
            WorkflowNode("vae", "decode", ("sample",), ("vae",)),
            WorkflowNode("sample", "diffuse", ("encode",), ("dit", "lora1")),
            WorkflowNode("encode", "text_encoder", (), ("te",)),
        ])
        self.assertEqual([n.node_id for n in plan.steps], ["encode", "sample", "vae"])
        self.assertEqual(plan.last_output_use["encode"], 1)
        self.assertEqual(plan.last_output_use["sample"], 2)
        self.assertEqual(plan.output_nodes, frozenset({"vae"}))
        self.assertEqual(plan.last_component_use["dit"], 1)

    def test_invalid_graph(self):
        with self.assertRaises(InvalidWorkflow):
            compile_workflow([WorkflowNode("a", "load", ("unknown",))])
        with self.assertRaises(InvalidWorkflow):
            compile_workflow([WorkflowNode("a", "x"), WorkflowNode("a", "y")])
        with self.assertRaises(InvalidWorkflow):
            compile_workflow([WorkflowNode("a", "x", ("b",)), WorkflowNode("b", "y", ("a",))])

    def test_preflight_simultaneous_weights(self):
        plan = compile_workflow([
            WorkflowNode("sample", "diffusion", components=("dit", "lora", "lora")),
        ])
        specs = {"dit": ComponentSpec("dit", 6, 6), "lora": ComponentSpec("lora", 1, 1)}
        estimate = preflight(plan, specs, MemoryBudget(8, 12, gpu_reserve_bytes=2))
        self.assertEqual(estimate.required_gpu_bytes, 7)
        self.assertFalse(estimate.fits_estimated_weights)
        self.assertEqual(estimate.over_budget_nodes, ("sample",))

    def test_idle_model_stays_hot_and_is_reused(self):
        manager, backend = self.manager()
        manager.register(ComponentSpec("dit", 6, 6))
        with manager.lease(["dit"]) as handles:
            self.assertEqual(handles["dit"]["key"], "dit")
        with manager.lease(["dit", "dit"]):
            self.assertEqual(manager.snapshot().leased_keys, ("dit",))
        self.assertEqual([call[0] for call in backend.calls], ["load"])
        self.assertEqual(manager.snapshot().gpu_used_bytes, 6)

    def test_pressure_offloads_to_ram_then_reuses(self):
        manager, backend = self.manager(gpu=8, cpu=12)
        manager.register(ComponentSpec("a", 6, 6))
        manager.register(ComponentSpec("b", 6, 6))
        with manager.lease(["a"]):
            pass
        with manager.lease(["b"]):
            pass
        self.assertEqual(manager.snapshot().warm_keys, ("a",))
        with manager.lease(["a"]):
            pass
        self.assertEqual(manager.snapshot().warm_keys, ("b",))
        self.assertEqual(
            len([call for call in backend.calls if call[0] == "load"]), 2
        )
        self.assertIn(("move", "a", Tier.WARM, Tier.HOT), backend.calls)

    def test_pressure_falls_back_to_disk_when_ram_tight(self):
        manager, backend = self.manager(gpu=8, cpu=0)
        manager.register(ComponentSpec("a", 6, 6))
        manager.register(ComponentSpec("b", 6, 6))
        with manager.lease(["a"]):
            pass
        with manager.lease(["b"]):
            pass
        self.assertEqual(manager.snapshot().cold_keys, ("a",))
        self.assertIn(("unload", "a", Tier.HOT), backend.calls)

    def test_active_component_cannot_be_evicted(self):
        manager, _ = self.manager(gpu=8)
        manager.register(ComponentSpec("dit", 6, 6))
        manager.register(ComponentSpec("vae", 4, 4))
        with manager.lease(["dit"]):
            with self.assertRaises(InsufficientMemory):
                with manager.lease(["vae"]):
                    pass
            self.assertEqual(manager.snapshot().leased_keys, ("dit",))
        self.assertEqual(manager.snapshot().leased_keys, ())

    def test_no_artificial_lora_count_limit(self):
        manager, _ = self.manager(gpu=80, cpu=60)
        manager.register(ComponentSpec("dit", 30, 30))
        keys = ["dit"]
        for i in range(35):
            key = f"lora-{i}"
            manager.register(ComponentSpec(key, 1, 1, "lora"))
            keys.append(key)
        with manager.lease(keys) as handles:
            self.assertEqual(len(handles), 36)
            self.assertEqual(manager.snapshot().gpu_used_bytes, 65)

    def test_warm_prefetch_and_manual_trim(self):
        manager, backend = self.manager(gpu=8, cpu=8)
        manager.register(ComponentSpec("te", 2, 4))
        manager.warm(["te"])
        self.assertEqual(manager.snapshot().warm_keys, ("te",))
        with manager.lease(["te"]):
            self.assertEqual(manager.snapshot().gpu_used_bytes, 2)
        manager.unload_idle()
        self.assertEqual(manager.snapshot().gpu_used_bytes, 0)
        self.assertEqual(manager.snapshot().cold_keys, ("te",))
        self.assertIn(("move", "te", Tier.WARM, Tier.HOT), backend.calls)

    def test_trim_does_not_evict_active(self):
        manager, _ = self.manager()
        manager.register(ComponentSpec("dit", 6, 6))
        with manager.lease(["dit"]):
            manager.unload_idle()
            self.assertEqual(manager.snapshot().hot_keys, ("dit",))

    def test_executor_releases_unused_outputs(self):
        manager, _ = self.manager(gpu=8, cpu=8)
        manager.register(ComponentSpec("te", 3, 3))
        manager.register(ComponentSpec("dit", 6, 6))
        manager.register(ComponentSpec("vae", 4, 4))
        plan = compile_workflow([
            WorkflowNode("encode", "encode", components=("te",)),
            WorkflowNode("sample", "sample", depends_on=("encode",), components=("dit",)),
            WorkflowNode("decode", "decode", depends_on=("sample",), components=("vae",)),
        ])
        observed = []
        def execute(node, handles, inputs):
            observed.append((node.node_id, sorted(inputs), sorted(handles)))
            return f"output:{node.node_id}"
        outputs = run_plan(plan, manager, execute)
        self.assertEqual(outputs, {"decode": "output:decode"})
        self.assertEqual(observed[1][1], ["encode"])
        self.assertEqual(observed[2][1], ["sample"])


if __name__ == "__main__":
    unittest.main()
