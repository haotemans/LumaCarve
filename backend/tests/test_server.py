"""Server boot tests; no GPU or model weights required."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from lumacarve_server.app import create_app
from lumacarve_server.config import Settings


class ServerTests(unittest.TestCase):
    def test_health_and_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            app = create_app(Settings(data_dir=root))
            with TestClient(app) as client:
                result = client.get("/api/v1/health")
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()["service"], "lumacarve")
                self.assertTrue((root / "model" / "lora").is_dir())
                self.assertEqual(client.get("/api/v1/runtime").json()["engine"], "not_connected")

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
