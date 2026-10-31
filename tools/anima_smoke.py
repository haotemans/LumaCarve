#!/usr/bin/env python3
"""Run a real local Anima Base 1.0 image generation (no server required).

This command requires downloaded Diffusers modular weights and a CUDA GPU.
It does NOT download weights or silently fall back to fake preview images.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def make_smoke_workflow(
    prompt: str, negative_prompt: str, steps: int, seed: int, aspect: str,
    guidance: float,
) -> dict:
    nodes = [
        {"id": "model", "kind": "model", "params": {"modelId": "anima-base-1"}, "exposed": ["modelId"]},
        {"id": "lora", "kind": "lora", "params": {"loras": []}, "exposed": ["loras"]},
        {"id": "prompt", "kind": "prompt",
         "params": {"prompt": prompt, "negativePrompt": negative_prompt},
         "exposed": ["prompt", "negativePrompt"]},
        {"id": "sampler", "kind": "sampler",
         "params": {"steps": steps, "seed": seed, "aspect": aspect, "guidance": guidance},
         "exposed": ["steps", "seed", "aspect", "guidance"]},
        {"id": "vae", "kind": "vae", "params": {}, "exposed": []},
        {"id": "output", "kind": "output", "params": {"transparent": False}, "exposed": []},
    ]
    pairs = [
        ("model", "lora"), ("lora", "sampler"), ("prompt", "sampler"),
        ("sampler", "vae"), ("vae", "output"),
    ]
    return {
        "format": "lumacarve.studio.workflow.v1",
        "intent": "create",
        "nodes": nodes,
        "edges": [{"source": source, "target": target} for source, target in pairs],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LumaCarve Anima Base 1.0 GPU smoke test")
    parser.add_argument("--model-path", type=Path, help="Complete local Diffusers ModularPipeline folder")
    parser.add_argument("--prompt", default="masterpiece, best quality, 1girl, city lights")
    parser.add_argument("--negative-prompt", default="")
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--aspect", choices=["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2"], default="1:1")
    parser.add_argument("--guidance", type=float, default=4)
    parser.add_argument("--offload", choices=["auto", "full", "model_cpu"], default="auto")
    args = parser.parse_args(argv)

    from lumacarve_server.config import Settings
    from lumacarve_server.adapters.anima import AnimaAdapter, find_anima_snapshot

    settings = replace(
        Settings.from_env(),
        inference_backend="anima",
        inference_offload=args.offload,
        anima_model_path=args.model_path.resolve() if args.model_path else None,
    )
    workflow = make_smoke_workflow(
        args.prompt, args.negative_prompt, args.steps, args.seed,
        args.aspect, args.guidance,
    )
    model_path = find_anima_snapshot(settings)
    if model_path is None:
        parser.error("Anima Diffusers model files not found or incomplete; see backend/docs/17-anima-adapter.md")
    if not AnimaAdapter(settings).ready:
        parser.error("Missing Diffusers/Torch dependencies; run tools/setup.py first")
    adapter = AnimaAdapter(settings)
    result = adapter.run(workflow, {}, threading.Event())
    result["local_png"] = str(settings.outputs_dir / (result["output_id"] + ".png"))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
