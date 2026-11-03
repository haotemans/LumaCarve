"""Anima Base 1.0 local Diffusers ModularPipeline image generation.

Only local verified snapshots are loaded. No Torch/Diffusers imports on API startup.
The single GPU job worker owns this instance and reuses loaded weights across jobs.
"""
from __future__ import annotations

import importlib.util
import json
import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from ..config import Settings
from ..jobs import EngineUnavailable
from ..workflows import validate_workflow

MODEL_ID = "anima-base-1"
COMPONENTS = (
    "transformer", "text_encoder", "tokenizer", "t5_tokenizer",
    "text_conditioner", "scheduler", "vae",
)
SIZES = {
    "1:1": (1024, 1024),
    "4:3": (1024, 768),
    "3:4": (768, 1024),
    "16:9": (1152, 640),
    "9:16": (640, 1152),
    "2:3": (768, 1152),
    "3:2": (1152, 768),
}


def find_anima_snapshot(settings: Settings) -> Path | None:
    """Resolve only complete, local ModularPipeline snapshots.

    The ModelScope split-checkpoint version is intentionally NOT accepted here.
    """
    if settings.anima_model_path is not None:
        candidates = [settings.anima_model_path.expanduser()]
    else:
        base = settings.models_dir / "bundles" / MODEL_ID / "huggingface"
        candidates = [base / "main"]
        if base.is_dir():
            candidates.extend(sorted(
                (item for item in base.iterdir() if item.is_dir() and item.name != "main"),
                key=lambda item: item.name,
            ))
    for folder in candidates:
        if not folder.is_dir() or not (folder / "modular_model_index.json").is_file():
            continue
        # A user-provided local directory may not contain our download marker,
        # but must still contain the complete documented ModularPipeline layout.
        if settings.anima_model_path is None and not (folder / ".lumacarve-complete").is_file():
            continue
        if not all((folder / name).is_dir() for name in COMPONENTS):
            continue
        weight_components = ("transformer", "vae", "text_encoder", "text_conditioner")
        if any(
            not any(p.is_file() for p in (folder / component).rglob("*.safetensors"))
            for component in weight_components
        ):
            continue
        try:
            manifest = json.loads((folder / "modular_model_index.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        return folder.resolve()
    return None


def dependencies_available() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in ("torch", "diffusers", "transformers"))


@dataclass(frozen=True)
class AnimaRequest:
    prompt: str
    negative_prompt: str
    steps: int
    seed: int
    guidance: float
    width: int
    height: int
    loras: tuple[tuple[str, float], ...]


def compile_anima_request(workflow: dict[str, Any], inputs: dict[str, Any]) -> AnimaRequest:
    summary = validate_workflow(workflow)
    if summary.model_id != MODEL_ID or summary.intent != "create":
        raise ValueError("Anima Base 1.0 adapter currently supports only text-to-image")
    if inputs.get("asset_ids") or inputs.get("mask_asset_id"):
        raise ValueError("Anima text-to-image does not accept reference or mask images")
    nodes = {node["kind"]: node for node in workflow["nodes"]}
    prompts = nodes["prompt"].get("params", {})
    sampling = nodes["sampler"].get("params", {})
    output = nodes["output"].get("params", {})
    if output.get("transparent", False):
        raise ValueError("Anima Base does not provide a native transparent-alpha output")
    prompt = prompts.get("prompt", "").strip()
    if not prompt:
        raise ValueError("Prompt must not be empty")
    width, height = SIZES[sampling.get("aspect", "1:1")]
    return AnimaRequest(
        prompt=prompt,
        negative_prompt=prompts.get("negativePrompt", ""),
        steps=sampling.get("steps", 28),
        seed=sampling.get("seed", 0),
        guidance=float(sampling.get("guidance", 4)),
        width=width,
        height=height,
        loras=summary.loras,
    )


class AnimaAdapter:
    """Lazy single-model adapter. A JobQueue serializes calls to run()."""

    model_id = MODEL_ID

    def __init__(self, settings: Settings):
        self.settings = settings
        self._pipeline: Any | None = None
        self._torch: Any | None = None
        self._loaded_path: Path | None = None
        self._active_loras: tuple[tuple[str, float], ...] = ()

    @property
    def ready(self) -> bool:
        # Disk/package check only: importing PyTorch / probing CUDA here would
        # slow healthy API requests and could allocate accelerator contexts.
        return find_anima_snapshot(self.settings) is not None and dependencies_available()

    def _build(self, folder: Path) -> tuple[Any, Any]:
        import torch
        from diffusers import ComponentsManager, ModularPipeline

        if not torch.cuda.is_available():
            raise EngineUnavailable("Anima requires a CUDA GPU for the current backend")
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        mode = self.settings.inference_offload
        if mode not in ("auto", "model_cpu", "full"):
            raise EngineUnavailable(f"Unsupported inference offload mode: {mode}")
        if mode in ("auto", "model_cpu"):
            manager = ComponentsManager()
            manager.enable_auto_cpu_offload(device="cuda")
            pipe = ModularPipeline.from_pretrained(str(folder), components_manager=manager)
            pipe.load_components(dtype=dtype)
        else:
            pipe = ModularPipeline.from_pretrained(str(folder))
            pipe.load_components(dtype=dtype)
            pipe.to("cuda")
        if self.settings.anima_triton == "experimental":
            from lumacarve_runtime.kernels.anima_adaln import install_anima_adaln_triton

            report = install_anima_adaln_triton(pipe)
            import logging
            logging.getLogger(__name__).info(
                "Anima Triton AdaLN: installed=%d; %s", report.installed, report.reason
            )
        if self.settings.anima_triton_rope == "experimental":
            from lumacarve_runtime.kernels.anima_rope import install_anima_rope_triton

            report = install_anima_rope_triton(pipe)
            import logging
            logging.getLogger(__name__).info(
                "Anima Triton RoPE: installed=%d; %s", report.installed, report.reason
            )
        if self.settings.anima_triton_residual == "experimental":
            from lumacarve_runtime.kernels.anima_residual import install_anima_residual_triton

            report = install_anima_residual_triton(pipe)
            import logging
            logging.getLogger(__name__).info(
                "Anima Triton Residual: installed=%d; %s", report.installed, report.reason
            )
        if self.settings.anima_triton_ffn == "experimental":
            # The custom GEMM bypasses nn.Linear.__call__, so prohibit it when
            # CPU offload may install residency hooks on the module hierarchy.
            if mode == "full":
                from lumacarve_runtime.kernels.anima_ffn import install_anima_ffn_triton

                report = install_anima_ffn_triton(pipe)
                import logging
                logging.getLogger(__name__).info(
                    "Anima Triton FFN: installed=%d; %s", report.installed, report.reason
                )
            else:
                import logging
                logging.getLogger(__name__).info(
                    "Anima Triton FFN skipped: requires inference_offload=full"
                )
        return pipe, torch

    def _lora_path(self, name: str) -> Path:
        if not name or "/" in name or "\\" in name or Path(name).name != name or Path(name).suffix.lower() != ".safetensors":
            raise ValueError("LoRA name must be a .safetensors filename without directories")
        root = (self.settings.models_dir / "lora").resolve()
        candidate = (root / name)
        if candidate.is_symlink() or not candidate.is_file() or not candidate.resolve().is_relative_to(root):
            raise FileNotFoundError(f"Installed LoRA file not found: {name}")
        return candidate.resolve()

    def _apply_loras(self, pipe: Any, requested: tuple[tuple[str, float], ...]) -> None:
        if requested == self._active_loras:
            return
        if self._active_loras:
            if not callable(getattr(pipe, "unload_lora_weights", None)):
                raise RuntimeError("Anima cannot unload previous LoRA adapters safely")
            pipe.unload_lora_weights()
        if requested:
            if not callable(getattr(pipe, "load_lora_weights", None)) or not callable(
                getattr(pipe, "set_adapters", None)
            ):
                raise EngineUnavailable("Installed Diffusers does not support Anima multi-LoRA")
            names = []
            weights = []
            for index, (filename, weight) in enumerate(requested):
                adapter_name = f"lumacarve_{index}"
                pipe.load_lora_weights(str(self._lora_path(filename)), adapter_name=adapter_name)
                names.append(adapter_name)
                weights.append(weight)
            pipe.set_adapters(names, adapter_weights=weights)
        self._active_loras = requested

    def run(self, workflow: dict[str, Any], inputs: dict[str, Any], cancel: threading.Event) -> dict[str, Any]:
        request = compile_anima_request(workflow, inputs)
        if cancel.is_set():
            raise InterruptedError("Anima generation was cancelled before loading")
        model_dir = find_anima_snapshot(self.settings)
        if model_dir is None:
            raise EngineUnavailable("Download the complete Anima Diffusers snapshot before generation")
        # Checkpoint identifiers are backend snapshot paths, never browser-side
        # file handles or arbitrary .safetensors paths.
        model_node = next(node for node in workflow["nodes"] if node["kind"] == "model")
        chosen = model_node.get("params", {}).get("checkpoint", "")
        if chosen:
            try:
                expected = model_dir.relative_to(self.settings.models_dir.resolve()).as_posix()
            except ValueError:
                expected = str(model_dir)
            if chosen != expected:
                raise ValueError("Selected checkpoint is not the installed Anima ModularPipeline snapshot")

        if self._pipeline is None or self._loaded_path != model_dir:
            self._pipeline, self._torch = self._build(model_dir)
            self._loaded_path = model_dir
            self._active_loras = ()
        pipe = self._pipeline
        torch = self._torch
        try:
            self._apply_loras(pipe, request.loras)
        except Exception:
            # An interrupted LoRA update must never poison the next request.
            self._pipeline, self._torch, self._loaded_path = None, None, None
            self._active_loras = ()
            raise
        if cancel.is_set():
            raise InterruptedError("Anima generation cancelled before sampling")
        guider = getattr(pipe, "guider", None)
        if guider is None or not hasattr(guider, "guidance_scale"):
            raise EngineUnavailable("The installed Anima Diffusers guider is incompatible")
        guider.guidance_scale = request.guidance
        generator = torch.Generator(device="cpu").manual_seed(request.seed)

        with torch.inference_mode():
            images = pipe(
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                height=request.height,
                width=request.width,
                num_inference_steps=request.steps,
                generator=generator,
            ).images
        torch.cuda.synchronize()
        if cancel.is_set():
            raise InterruptedError("Anima generation cancelled; result was not published")
        if len(images) != 1 or not isinstance(images[0], Image.Image):
            raise RuntimeError("Anima pipeline did not return one PIL image")
        output_id = uuid.uuid4().hex
        output_file = self.settings.outputs_dir / f"{output_id}.png"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        temp = output_file.with_suffix(".tmp")
        try:
            images[0].save(temp, format="PNG")
            if cancel.is_set():
                raise InterruptedError("Anima generation cancelled before image publication")
            os.replace(temp, output_file)
        finally:
            if temp.exists():
                temp.unlink()
        return {
            "output_id": output_id,
            "model_id": MODEL_ID,
            "model_path": model_dir.name,
            "seed": request.seed,
            "width": images[0].width,
            "height": images[0].height,
            "steps": request.steps,
            "loras": [{"name": name, "strength": weight} for name, weight in request.loras],
        }
