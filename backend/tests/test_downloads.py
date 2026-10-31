import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from lumacarve_server.app import create_app
from lumacarve_server.config import Settings
from lumacarve_server.model_downloads import ModelDownloadError, MODEL_CATALOG, model_destination


class ModelDownloadTests(unittest.TestCase):
    def test_catalog_and_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            with TestClient(create_app(Settings(data_dir=Path(temp),download_region="cn"))) as client:
                response = client.get("/api/v1/downloads/catalog")
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()["models"][0]["provider"],"modelscope")
                self.assertFalse(response.json()["downloads_enabled"])
                rejected = client.post("/api/v1/downloads", json={"model_id": "qwen-image-2.1"})
                self.assertEqual(rejected.status_code,403)

    def test_anima_download_sources_have_distinct_formats(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = Settings(data_dir=Path(temp), download_region="cn")
            cn = model_destination(settings, "anima-base-1", "master", provider="modelscope")
            hf = model_destination(settings, "anima-base-1", "main", provider="huggingface")
            self.assertNotEqual(cn, hf)
            self.assertIn("/modelscope/", cn.as_posix())
            self.assertIn("/huggingface/", hf.as_posix())
            with self.assertRaises(ModelDownloadError):
                model_destination(settings, "anima-base-1", "main")
            with TestClient(create_app(settings)) as client:
                entry = next(x for x in client.get("/api/v1/downloads/catalog").json()["models"]
                             if x["id"] == "anima-base-1")
                self.assertEqual(entry["format"], "comfyui_split")
                self.assertFalse(entry["supports_lumacarve_inference"])

    def test_anima_download_worker_uses_provider_isolated_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(
                data_dir=Path(tmp), allow_model_download=True, download_region="cn"
            )
            settings.ensure_dirs()
            def fake_download(provider, repo_id, revision, destination, *, allow_patterns=None):
                self.assertEqual(provider, "modelscope")
                for rel in (
                    "split_files/diffusion_models/anima-base-v1.0.safetensors",
                    "split_files/text_encoders/qwen_3_06b_base.safetensors",
                    "split_files/vae/qwen_image_vae.safetensors",
                ):
                    path = destination / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"mock")
                return destination
            with patch(
                "lumacarve_server.model_downloads.download_snapshot",
                side_effect=fake_download,
            ):
                with TestClient(create_app(settings)) as client:
                    response = client.post(
                        "/api/v1/downloads",
                        json={"model_id": "anima-base-1", "provider": "modelscope"},
                    )
                    self.assertEqual(response.status_code, 202, response.text)
                    import time
                    state = None
                    for _ in range(100):
                        state = client.get(
                            "/api/v1/downloads/" + response.json()["id"]
                        ).json()
                        if state["state"] in ("completed", "failed"):
                            break
                        time.sleep(.01)
                    self.assertEqual(state["state"], "completed", state)
                    location = model_destination(
                        settings, "anima-base-1", "master", provider="modelscope"
                    )
                    self.assertTrue(
                        (location / ".lumacarve-complete").is_file()
                    )

    def test_unknown_model_or_revision_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            settings=Settings(data_dir=Path(temp),allow_model_download=True)
            with TestClient(create_app(settings)) as client:
                self.assertEqual(client.post("/api/v1/downloads",json={"model_id":"../../etc"}).status_code,422)
            with self.assertRaises(ModelDownloadError):
                model_destination(settings,"qwen-image-2.1","../../etc")

    def test_download_status_is_real_and_completed_file_is_marked(self):
        with tempfile.TemporaryDirectory() as temp:
            def fake_download(provider,repo_id,revision,destination):
                (destination/"config.json").write_text("{}",encoding="utf-8")
                return destination
            settings=Settings(data_dir=Path(temp),download_region="cn",allow_model_download=True)
            with patch("lumacarve_server.model_downloads.download_snapshot",side_effect=fake_download):
                with TestClient(create_app(settings)) as client:
                    r=client.post("/api/v1/downloads",json={"model_id":"qwen-image-2.1"})
                    self.assertEqual(r.status_code,202,r.text)
                    task_id=r.json()["id"]
                    import time
                    for _ in range(100):
                        state=client.get("/api/v1/downloads/"+task_id).json()
                        if state["state"]!="running" and state["state"]!="queued":break
                        time.sleep(.01)
                    self.assertEqual(state["state"],"completed",state)
                    target=model_destination(settings,"qwen-image-2.1","master")
                    self.assertTrue((target/".lumacarve-complete").exists())
                    self.assertEqual(client.post("/api/v1/downloads",json={"model_id":"qwen-image-2.1"}).status_code,409)


if __name__=="__main__":
    unittest.main()
