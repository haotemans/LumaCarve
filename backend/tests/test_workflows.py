"""Graph schema acceptance and error cases."""
import unittest
from lumacarve_server.workflows import WorkflowValidationError, validate_workflow


def sample(intent="create"):
    nodes = [
        {"id": "model", "kind": "model", "params": {"modelId": "qwen-image-2.1"}, "exposed": ["modelId"]},
        {"id": "prompt", "kind": "prompt", "params": {"prompt": "a star"}, "exposed": ["prompt"]},
        {"id": "lora", "kind": "lora", "params": {"loras": []}, "exposed": ["loras"]},
        {"id": "sampler", "kind": "sampler", "params": {"steps": 28, "seed": 1}, "exposed": ["steps"]},
        {"id": "vae", "kind": "vae", "params": {}, "exposed": []},
        {"id": "output", "kind": "output", "params": {}, "exposed": []},
    ]
    edges = [{"source": a, "target": b} for a,b in (
        ("model", "lora"), ("lora", "sampler"), ("prompt", "sampler"),
        ("sampler", "vae"), ("vae", "output")
    )]
    if intent in ("reference", "inpaint"):
        nodes.append({"id": "references", "kind": "references", "params": {}, "exposed": ["images"]})
        edges.append({"source": "references", "target": "sampler"})
    if intent == "inpaint":
        nodes.append({"id": "mask", "kind": "mask", "params": {}, "exposed": ["mask"]})
        edges.append({"source": "mask", "target": "sampler"})
    return {"format": "lumacarve.studio.workflow.v1", "intent": intent, "nodes": nodes, "edges": edges}


class WorkflowTests(unittest.TestCase):
    def test_all_three_intents(self):
        for intent in ("create", "reference", "inpaint"):
            with self.subTest(intent=intent):
                result = validate_workflow(sample(intent))
                self.assertEqual(result.intent, intent)
                self.assertEqual(result.node_order[-1], "output")
                self.assertEqual(result.mask_required, intent == "inpaint")

    def test_incompatible_edge(self):
        doc = sample()
        doc["edges"].append({"source": "model", "target": "output"})
        with self.assertRaises(WorkflowValidationError):
            validate_workflow(doc)

    def test_orphan_node(self):
        doc = sample()
        doc["nodes"].append({"id": "orphan", "kind": "prompt", "params": {}, "exposed": []})
        with self.assertRaises(WorkflowValidationError):
            validate_workflow(doc)

    def test_lora_stack(self):
        doc = sample()
        lora = doc["nodes"][2]
        lora["params"]["loras"] = [
            {"name": f"adapter-{i}", "strength": 0.6, "enabled": True} for i in range(35)
        ]
        result = validate_workflow(doc)
        self.assertEqual(len(result.loras), 35)

    def test_invalid_lora_weight(self):
        doc = sample()
        doc["nodes"][2]["params"]["loras"] = [{"name": "a", "strength": 2.9, "enabled": True}]
        with self.assertRaises(WorkflowValidationError):
            validate_workflow(doc)


if __name__ == "__main__":
    unittest.main()
