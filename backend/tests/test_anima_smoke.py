"""Validate the CLI-generated graph without PyTorch or model downloads."""
import importlib.util
import unittest
from pathlib import Path

from lumacarve_server.workflows import validate_workflow

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "anima_smoke.py"
spec = importlib.util.spec_from_file_location("anima_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class AnimaSmokeTests(unittest.TestCase):
    def test_smoke_workflow_compiles(self):
        workflow = smoke.make_smoke_workflow(
            "a cute anime girl", "low quality", 35, 17, "3:4", 4.5
        )
        summary = validate_workflow(workflow)
        self.assertEqual(summary.model_id, "anima-base-1")
        self.assertEqual(summary.intent, "create")
        self.assertEqual(summary.exposed_fields.count("sampler.seed"), 1)

    def test_smoke_workflow_invalid_steps_are_rejected(self):
        workflow = smoke.make_smoke_workflow("a cat", "", 0, 9, "1:1", 4)
        from lumacarve_server.workflows import WorkflowValidationError
        with self.assertRaises(WorkflowValidationError):
            validate_workflow(workflow)


if __name__ == "__main__":
    unittest.main()
