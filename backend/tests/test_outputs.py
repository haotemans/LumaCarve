"""Generated image retrieval must only serve locally generated file IDs."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from lumacarve_server.app import create_app
from lumacarve_server.config import Settings


class OutputTests(unittest.TestCase):
    def test_output_served_from_controlled_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(data_dir=Path(tmp))
            with TestClient(create_app(settings)) as client:
                output_id = "c" * 32
                Image.new("RGB", (8, 8)).save(settings.outputs_dir / (output_id + ".png"))
                response = client.get("/api/v1/outputs/" + output_id)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["content-type"], "image/png")
                self.assertTrue(response.content.startswith(b"\x89PNG"))
                self.assertEqual(
                    client.get("/api/v1/outputs/" + ("d" * 32)).status_code, 404
                )
                self.assertEqual(client.get("/api/v1/outputs/not-a-token").status_code, 422)


if __name__ == "__main__":
    unittest.main()
