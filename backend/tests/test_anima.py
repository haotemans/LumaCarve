"""Anima adapter contract tests (mocked pipeline; no GPU downloads)."""
from __future__ import annotations

from contextlib import nullcontext
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from lumacarve_server.adapters.anima import (
    AnimaAdapter, MODEL_ID, SIZES, compile_anima_request,
    find_anima_snapshot,
)
from lumacarve_server.app import create_app
from lumacarve_server.config import Settings
from test_workflows import sample


class FakeGenerator:
    def __init__(self, device):
        self.device = device

    def manual_seed(self, seed):
        self.seed = seed
        return self


class FakeTorch:
    Generator = FakeGenerator
    cuda = SimpleNamespace(synchronize=lambda: None)
    inference_mode = staticmethod(nullcontext)


class FakePipeline:
    def __init__(self, after_generate=None):
        self.calls = []
        self.guider = SimpleNamespace(guidance_scale=4)
        self.loads = []
        self.activated = []
        self.unloads = 0
        self.after_generate = after_generate

    def load_lora_weights(self, path, adapter_name):
        self.loads.append((path, adapter_name))

    def set_adapters(self, names, adapter_weights):
        self.activated.append((tuple(names), tuple(adapter_weights)))

    def unload_lora_weights(self):
        self.unloads += 1

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.after_generate is not None:
            self.after_generate()
        return SimpleNamespace(images=[Image.new("RGB", (kwargs["width"], kwargs["height"]))])


def make_workflow(intent="create"):
    workflow = sample(intent)
    workflow["nodes"][0]["params"]["modelId"] = MODEL_ID
    return workflow


def install_dummy_snapshot(settings, *, completed=True):
    folder = settings.models_dir / "bundles" / MODEL_ID / "huggingface" / "main"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "modular_model_index.json").write_text(json.dumps({"_class_name": "AnimaModularPipeline"}))
    for component in (
        "transformer", "vae", "text_encoder", "text_conditioner",
        "tokenizer", "t5_tokenizer", "scheduler",
    ):
        component_dir = folder / component
        component_dir.mkdir(exist_ok=True)
        if component in ("transformer", "vae", "text_encoder", "text_conditioner"):
            (component_dir / "model.safetensors").write_bytes(b"test-weight")
    if completed:
        (folder / ".lumacarve-complete").write_text("verified fixture", encoding="utf-8")
    return folder


class AnimaTests(unittest.TestCase):
    def test_anima_workflow_compile_and_capabilities(self):
        prepared = compile_anima_request(make_workflow(), {})
        self.assertEqual(prepared.prompt, "a star")
        self.assertEqual((prepared.width, prepared.height), SIZES["1:1"])
        self.assertEqual(prepared.steps, 28)
        self.assertEqual(prepared.seed, 1)
        with self.assertRaisesRegex(ValueError, "only text-to-image"):
            compile_anima_request(make_workflow("reference"), {"asset_ids": []})
        bad = make_workflow()
        bad["nodes"][-1]["params"]["transparent"] = True
        with self.assertRaisesRegex(ValueError, "transparent"):
            compile_anima_request(bad, {})

    def test_only_verified_diffusers_snapshot_is_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(data_dir=Path(tmp))
            install_dummy_snapshot(settings, completed=False)
            self.assertIsNone(find_anima_snapshot(settings))
            folder = install_dummy_snapshot(settings)
            self.assertEqual(find_anima_snapshot(settings), folder.resolve())
            explicit = Settings(data_dir=Path(tmp), anima_model_path=folder)
            (folder / ".lumacarve-complete").unlink()
            self.assertEqual(find_anima_snapshot(explicit), folder.resolve())
            self.assertFalse(AnimaAdapter(settings).ready)

    def test_local_inference_writes_actual_png_and_reuses_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(data_dir=Path(tmp))
            settings.ensure_dirs()
            install_dummy_snapshot(settings)
            fake = FakePipeline()
            adapter = AnimaAdapter(settings)
            with patch.object(adapter, "_build", return_value=(fake, FakeTorch)) as build:
                first = adapter.run(make_workflow(), {}, threading.Event())
                second = adapter.run(make_workflow(), {}, threading.Event())
            build.assert_called_once()
            self.assertEqual(first["model_id"], MODEL_ID)
            self.assertNotEqual(first["output_id"], second["output_id"])
            self.assertEqual(len(fake.calls), 2)
            self.assertEqual(fake.calls[0]["generator"].seed, 1)
            self.assertEqual(fake.guider.guidance_scale, 4.0)
            for result in (first, second):
                target = settings.outputs_dir / f'{result["output_id"]}.png'
                self.assertTrue(target.is_file())
                with Image.open(target) as image:
                    self.assertEqual(image.size, SIZES["1:1"])

    def test_multi_lora_load_does_not_duplicate_base_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(data_dir=Path(tmp))
            settings.ensure_dirs()
            install_dummy_snapshot(settings)
            for name in ("a.safetensors", "b.safetensors"):
                (settings.models_dir / "lora" / name).write_bytes(b"fixture")
            workflow = make_workflow()
            loras = [
                {"name": "a.safetensors", "strength": 0.8, "enabled": True},
                {"name": "b.safetensors", "strength": -0.4, "enabled": True},
            ]
            workflow["nodes"][2]["params"]["loras"] = loras
            fake = FakePipeline()
            adapter = AnimaAdapter(settings)
            with patch.object(adapter, "_build", return_value=(fake, FakeTorch)) as build:
                adapter.run(workflow, {}, threading.Event())
                adapter.run(workflow, {}, threading.Event())
                self.assertEqual(len(fake.loads), 2)
                self.assertEqual(fake.activated[0][1], (0.8, -0.4))
                workflow["nodes"][2]["params"]["loras"] = []
                adapter.run(workflow, {}, threading.Event())
                self.assertEqual(fake.unloads, 1)
            build.assert_called_once()

    def test_cancellation_never_publishes_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(data_dir=Path(tmp))
            settings.ensure_dirs()
            install_dummy_snapshot(settings)
            cancel = threading.Event()
            fake = FakePipeline(after_generate=cancel.set)
            adapter = AnimaAdapter(settings)
            with patch.object(adapter, "_build", return_value=(fake, FakeTorch)):
                with self.assertRaises(InterruptedError):
                    adapter.run(make_workflow(), {}, cancel)
            self.assertEqual(list(settings.outputs_dir.glob("*.png")), [])

    def test_api_enqueues_anima_when_explicitly_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(data_dir=Path(tmp), inference_backend="anima")
            settings.ensure_dirs()
            install_dummy_snapshot(settings)
            with patch("lumacarve_server.adapters.anima.dependencies_available", return_value=True):
                with TestClient(create_app(settings)) as client:
                    runtime = client.get("/api/v1/runtime").json()
                    self.assertEqual(runtime["engine"], "anima")
                    adapter = client.app.state.job_queue.adapter
                    fake = FakePipeline()
                    with patch.object(adapter, "_build", return_value=(fake, FakeTorch)):
                        submitted = client.post("/api/v1/jobs", json={"workflow": make_workflow()})
                        self.assertEqual(submitted.status_code, 202, submitted.text)
                        job_id = submitted.json()["id"]
                        for _ in range(120):
                            state = client.get("/api/v1/jobs/" + job_id).json()
                            if state["state"] in ("completed", "failed", "cancelled"):
                                break
                            time.sleep(.01)
                        self.assertEqual(state["state"], "completed", state)
                        self.assertEqual(state["priority"], "interactive")
                        self.assertTrue(
                            (settings.outputs_dir / f'{state["result"]["output_id"]}.png').exists()
                        )
                    refused = client.post("/api/v1/jobs", json={"workflow": sample()})
                    self.assertEqual(refused.status_code, 422)


if __name__ == "__main__":
    unittest.main()


class ModelSnapshotContractTests(unittest.TestCase):
    def test_model_endpoint_differentiates_index_from_executable_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(data_dir=Path(tmp), inference_backend="anima")
            settings.ensure_dirs()
            with TestClient(create_app(settings)) as client:
                payload = client.get("/api/v1/models").json()
                self.assertFalse(payload["backend_ready"])
                self.assertIsNone(payload["anima_snapshot"])
                self.assertTrue(payload["backend_configured"])
                folder = install_dummy_snapshot(settings)
                payload = client.get("/api/v1/models").json()
                self.assertEqual(payload["anima_snapshot"], folder.relative_to(settings.models_dir).as_posix())
                self.assertFalse(payload["backend_ready"])  # CUDA deps still missing

    def test_browser_selected_checkpoint_cannot_silently_change_backend_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(data_dir=Path(tmp), inference_backend="anima")
            settings.ensure_dirs()
            install_dummy_snapshot(settings)
            data = make_workflow()
            data["nodes"][0]["params"]["checkpoint"] = "some-local-file.safetensors"
            with TestClient(create_app(settings)) as client:
                response = client.post("/api/v1/jobs", json={"workflow": data})
                self.assertEqual(response.status_code, 422)
                self.assertIn("checkpoint", response.text)
