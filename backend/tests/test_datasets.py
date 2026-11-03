"""GPU-free end-to-end tests for persistent image/tag dataset management."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from lumacarve_server.app import create_app
from lumacarve_server.config import Settings


def png(width: int = 64, height: int = 48) -> bytes:
    image = Image.new("RGB", (width, height), (24, 93, 120))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class DatasetTests(unittest.TestCase):
    def test_create_upload_edit_reopen_and_delete(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = Settings(data_dir=Path(temp))
            with TestClient(create_app(settings)) as client:
                self.assertEqual(client.get("/api/v1/datasets").json(), {"datasets": []})
                created = client.post("/api/v1/datasets", json={"id": "style_pack", "title": "Style Pack"})
                self.assertEqual(created.status_code, 201, created.text)
                upload = client.post("/api/v1/datasets/style_pack/images", data={"caption": "a girl, sky"},
                                     files={"file": ("scene.png", png(), "image/png")})
                self.assertEqual(upload.status_code, 201, upload.text)
                image = upload.json()
                self.assertEqual((image["width"], image["height"]), (64, 48))
                self.assertEqual(image["caption"], "a girl, sky")
                names = client.get("/api/v1/datasets").json()["datasets"]
                self.assertEqual(names[0]["image_count"], 1)
                self.assertGreater(names[0]["size_bytes"], 0)
                page = client.get("/api/v1/datasets/style_pack/images?limit=1").json()
                self.assertEqual(page["total"], 1)
                self.assertEqual(page["items"][0]["name"], "scene.png")
                view = client.get(f"/api/v1/datasets/style_pack/images/{image['id']}")
                self.assertEqual(view.status_code, 200)
                self.assertEqual(view.headers["content-type"], "image/png")
                edited = client.put(f"/api/v1/datasets/style_pack/images/{image['id']}/caption", json={"caption": "new caption\n第二行"})
                self.assertEqual(edited.status_code, 200, edited.text)
                sidecar = settings.datasets_dir / "style_pack" / (image["id"] + ".tags.txt")
                self.assertEqual(sidecar.read_text(encoding="utf-8"), "new caption\n第二行")
            # The data survives an application restart, unlike browser-only previews.
            with TestClient(create_app(settings)) as client:
                page = client.get("/api/v1/datasets/style_pack/images").json()
                self.assertEqual(page["items"][0]["caption"], "new caption\n第二行")
                deleted = client.delete(f"/api/v1/datasets/style_pack/images/{image['id']}")
                self.assertEqual(deleted.status_code, 204, deleted.text)
                self.assertFalse(sidecar.exists())
                self.assertEqual(client.get("/api/v1/datasets/style_pack/images").json()["total"], 0)

    def test_input_rejection_duplicate_and_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            with TestClient(create_app(Settings(data_dir=Path(temp)))) as client:
                for name in ("../outside", "UPPER", "a/b", ".env"):
                    response = client.post("/api/v1/datasets", json={"id": name, "title": "Test"})
                    self.assertIn(response.status_code, (404, 422))
                self.assertEqual(client.post("/api/v1/datasets", json={"id": "train", "title": "Train"}).status_code, 201)
                self.assertEqual(client.post("/api/v1/datasets", json={"id": "train", "title": "Again"}).status_code, 409)
                bad = client.post("/api/v1/datasets/train/images", files={"file": ("evil.png", b"not an image", "image/png")})
                self.assertEqual(bad.status_code, 422)
                self.assertEqual(client.get("/api/v1/datasets/train/images").json()["total"], 0)
                image = client.post("/api/v1/datasets/train/images", files={"file": ("valid.png", png(), "image/png")})
                self.assertEqual(image.status_code, 201, image.text)
                repeat = client.post("/api/v1/datasets/train/images", files={"file": ("copy.png", png(), "image/png")})
                self.assertEqual(repeat.status_code, 409)
                self.assertEqual(client.get("/api/v1/datasets/train/images?offset=1").json()["items"], [])
                self.assertEqual(client.get("/api/v1/datasets/train/images?limit=1000").status_code, 422)
                self.assertEqual(client.get("/api/v1/datasets/train/images?offset=-1").status_code, 422)
                self.assertEqual(client.get("/api/v1/datasets/missing/images").status_code, 404)
                self.assertEqual(client.get("/api/v1/datasets/train/images/../secrets").status_code, 404)
                self.assertEqual(client.get("/api/v1/datasets/train/images/123").status_code, 422)
                image_id = image.json()["id"]
                self.assertEqual(client.put(f"/api/v1/datasets/train/images/{image_id}/caption", json={"caption": "x"*20001}).status_code, 422)
                self.assertEqual(client.delete(f"/api/v1/datasets/train/images/{'0'*64}").status_code, 404)

    def test_browser_put_caption_cors_preflight_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            with TestClient(create_app(Settings(data_dir=Path(temp)))) as client:
                result = client.options(
                    "/api/v1/datasets/demo/images/" + "a"*64 + "/caption",
                    headers={
                        "Origin": "http://localhost:5173",
                        "Access-Control-Request-Method": "PUT",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )
                self.assertEqual(result.status_code, 200, result.text)
                self.assertIn("PUT", result.headers.get("access-control-allow-methods", ""))
                self.assertEqual(result.headers.get("access-control-allow-origin"), "http://localhost:5173")

    def test_user_origin_blocked_without_creating_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            with TestClient(create_app(Settings(data_dir=Path(temp)))) as client:
                result = client.post("/api/v1/datasets", json={"id": "unsafe", "title": "Unsafe"},
                                     headers={"origin": "https://malicious.invalid"})
                self.assertEqual(result.status_code, 403)
                self.assertEqual(client.get("/api/v1/datasets").json()["datasets"], [])


if __name__ == "__main__":
    unittest.main()
