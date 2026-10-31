"""Rust/Python graph plan parity tests.

Real PyO3 extension is installed by scheduler-ci; unit CI without Rust uses
Python fallback and a deliberately malformed fake extension.
"""
import unittest
import json
from unittest.mock import patch

from lumacarve_runtime.graph import WorkflowNode, compile_workflow, InvalidWorkflow
from lumacarve_runtime.rust_bridge import compile_preferred, scheduler_backend


def workflow():
    return [
        WorkflowNode("vae", "decode", ("sample",), ("vae",)),
        WorkflowNode("sample", "diffuse", ("prompt", "model"), ("dit", "lora_A")),
        WorkflowNode("model", "load", (), ("dit",)),
        WorkflowNode("prompt", "encode", (), ("te",)),
    ]


class RustBridgeTests(unittest.TestCase):
    def test_missing_extension_uses_python_fallback(self):
        nodes = workflow()
        with patch("lumacarve_runtime.rust_bridge._extension", return_value=None):
            preferred = compile_preferred(nodes)
        self.assertEqual(preferred, compile_workflow(nodes))

    def test_invalid_extension_fails_closed(self):
        class Broken:
            @staticmethod
            def compile_graph_json(_):
                return '{"order":["fake"],"last_output_use":{}}'
        with patch("lumacarve_runtime.rust_bridge._extension", return_value=Broken()):
            with self.assertRaises(InvalidWorkflow):
                compile_preferred(workflow())

    def test_real_rust_matches_python(self):
        if scheduler_backend() != "rust":
            self.skipTest("Rust extension not installed in optional Python fallback CI")
        nodes = workflow()
        actual = compile_preferred(nodes)
        expected = compile_workflow(nodes)
        self.assertEqual(actual.steps, expected.steps)
        self.assertEqual(actual.last_output_use, expected.last_output_use)
        self.assertEqual(actual.last_component_use, expected.last_component_use)
        self.assertEqual(actual.output_nodes, expected.output_nodes)

        # Exercise Rust queue and memory lease from the actual extension.
        import lumacarve_scheduler
        q = lumacarve_scheduler.RustJobScheduler(3)
        q.submit("task-1", "interactive")
        q.submit("task-2", "normal")
        self.assertEqual(q.start_next(), "task-1")
        self.assertEqual(q.cancel("task-2"), "cancelled")
        self.assertEqual(q.cancel("task-1"), "requested")
        self.assertTrue(q.should_cancel("task-1"))
        self.assertEqual(q.finish("task-1", True), "cancelled")
        arbiter = lumacarve_scheduler.RustMemoryArbiter(8, 16)
        arbiter.reserve("dit", 6, 10)
        self.assertEqual(arbiter.used(), (6, 10))
        with self.assertRaises(ValueError):
            arbiter.reserve("vae", 4, 3)
        self.assertEqual(arbiter.release("dit"), (6, 10))
        self.assertEqual(arbiter.used(), (0, 0))


    def test_rust_incremental_plan_reuses_valid_text_embeddings(self):
        if scheduler_backend() != "rust":
            self.skipTest("Optional Rust extension not installed")
        import lumacarve_scheduler
        nodes = [
            {"node_id": "encode", "operation": "encode", "depends_on": [],
             "params": {"prompt": "moon"}, "model_revision": "model-v1"},
            {"node_id": "sample", "operation": "sample", "depends_on": ["encode"],
             "params": {"seed": 7}, "model_revision": "model-v1"},
            {"node_id": "decode", "operation": "decode", "depends_on": ["sample"],
             "params": {}, "model_revision": "model-v1"},
        ]
        metadata = json.dumps(nodes)
        fingerprints = json.loads(lumacarve_scheduler.fingerprints_json(metadata))
        cached = {"encode": {"fingerprint": fingerprints["encode"], "available": True}}
        plan = json.loads(lumacarve_scheduler.plan_incremental_json(
            metadata, json.dumps(cached), json.dumps(["decode"])
        ))
        self.assertEqual(plan["executed"], 2)
        self.assertEqual(plan["reused"], 1)
        self.assertEqual([(step["node_id"], step["action"]) for step in plan["steps"]], [
            ("encode", "reuse"), ("sample", "execute"), ("decode", "execute")
        ])
        # A cache fingerprint is not enough if Python has already evicted data.
        cached["encode"]["available"] = False
        evicted = json.loads(lumacarve_scheduler.plan_incremental_json(
            metadata, json.dumps(cached), json.dumps(["decode"])
        ))
        self.assertEqual(evicted["executed"], 3)
        self.assertEqual(evicted["reused"], 0)


if __name__ == "__main__":
    unittest.main()
