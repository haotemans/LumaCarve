import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from lumacarve_server.app import create_app
from lumacarve_server.config import Settings
from lumacarve_server.models import scan_models


class ModelTests(unittest.TestCase):
    def test_scan_excludes_irrelevant_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root / "dit").mkdir()
            (root / "dit" / "model.safetensors").write_bytes(b"fake")
            (root / "dit" / "bad.py").write_text("print('no')")
            found=scan_models(root)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].id, "dit/model.safetensors")

    def test_unload_guarded_when_engine_unconfigured(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TestClient(create_app(Settings(data_dir=Path(tmp)))) as client:
                status = client.get("/api/v1/models").json()["residency"]
                self.assertEqual(status["state"], "unknown")
                self.assertIsNone(status["model_id"])
                self.assertEqual(client.post("/api/v1/models/unload").status_code, 409)

    def test_model_api_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TestClient(create_app(Settings(data_dir=Path(tmp)))) as c:
                response=c.get("/api/v1/models")
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()["backend_ready"])
                self.assertEqual(response.json()["loaded"], [])
                self.assertEqual(response.json()["residency"]["state"], "unknown")


if __name__ == "__main__":
    unittest.main()
