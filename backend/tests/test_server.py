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
