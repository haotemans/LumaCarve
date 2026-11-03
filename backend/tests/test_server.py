"""Server boot tests; no GPU or model weights required."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from lumacarve_server.app import create_app
from lumacarve_server.config import Settings, default_data_dir


class ServerTests(unittest.TestCase):
    def test_default_data_path_preserves_old_model_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(default_data_dir(root), root / "LumaCarveData")
            legacy = root / "backend" / "LumaCarveData"
            legacy.mkdir(parents=True)
            self.assertEqual(default_data_dir(root), legacy)
            (root / "LumaCarveData").mkdir()
            self.assertEqual(default_data_dir(root), legacy)

    def test_health_and_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            app = create_app(Settings(data_dir=root))
            with TestClient(app) as client:
                result = client.get("/api/v1/health")
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()["service"], "lumacarve")
                self.assertTrue((root / "model" / "lora").is_dir())
                runtime = client.get("/api/v1/runtime").json()
                self.assertEqual(runtime["engine"], "not_connected")
                self.assertIn(runtime["graph_scheduler"], ("rust", "python-fallback"))
                self.assertFalse(runtime["gpu"]["measured"])
                self.assertIsNone(runtime["gpu"]["available"])
                self.assertEqual(runtime["memory_planner"], {
                    "adaptive": "not_implemented", "current": "auto",
                })
                self.assertEqual(runtime["optimization"]["state"], "configured_only")
                self.assertFalse(runtime["optimization"]["validated_on_gpu"])
                self.assertEqual(runtime["optimization"]["anima"], {
                    "adaln": "off", "rope": "off", "residual": "off", "ffn": "off",
                })

    def test_runtime_reports_requested_experimental_flags_not_verified_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = Settings(
                data_dir=Path(temp),
                inference_offload="full",
                anima_triton="experimental",
                anima_triton_rope="experimental",
                anima_triton_residual="experimental",
                anima_triton_ffn="experimental",
            )
            with TestClient(create_app(settings)) as client:
                result = client.get("/api/v1/runtime")
                self.assertEqual(result.status_code, 200)
                snapshot = result.json()
                self.assertEqual(snapshot["inference_offload"], "full")
                self.assertEqual(snapshot["memory_planner"]["current"], "full")
                self.assertEqual(snapshot["memory_planner"]["adaptive"], "not_implemented")
                self.assertTrue(all(
                    mode == "experimental"
                    for mode in snapshot["optimization"]["anima"].values()
                ))
                self.assertEqual(snapshot["optimization"]["state"], "configured_only")
                self.assertFalse(snapshot["optimization"]["validated_on_gpu"])
                self.assertIsNone(snapshot["gpu"]["available"])

    def test_local_origin_only(self):
        with tempfile.TemporaryDirectory() as temp:
            with TestClient(create_app(Settings(data_dir=Path(temp)))) as client:
                response = client.get("/api/v1/health", headers={"Origin": "https://malicious.example"})
                self.assertEqual(response.status_code, 403)
                response = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
                self.assertEqual(response.status_code, 200)
                response = client.get("/api/v1/health", headers={"Host": "evil.example"})
                self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
