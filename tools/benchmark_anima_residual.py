#!/usr/bin/env python3
"""Explicit GPU microbenchmark: Anima/Cosmos gated residual vs Triton.

This script is never called by normal image generation. It does not load
weights, download models, autotune or train a predictor. A warm CUDA launch
is performed before timing and compilation time is reported separately.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Anima gated residual CUDA microbenchmark")
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--tokens", type=int, default=4096)
    parser.add_argument("--channels", type=int, default=2048)
    parser.add_argument("--repetitions", type=int, default=200)
    parser.add_argument("--dtype", choices=["fp16", "bf16", "fp32"], default="bf16")
    parser.add_argument("--gate-tokens", choices=["one", "per-token"], default="one")
    args = parser.parse_args(argv)
    if args.batch < 1 or args.tokens < 1 or not 1 <= args.channels <= 8192 or args.repetitions < 2:
        parser.error("batch/tokens must be positive, channels 1..8192, repetitions >=2")

    try:
        import torch
        import triton  # noqa: F401
    except ImportError as exc:
        parser.error(f"PyTorch/Triton not installed: {exc}")
    if not torch.cuda.is_available():
        parser.error("CUDA GPU required")
    if args.dtype == "bf16" and not torch.cuda.is_bf16_supported():
        parser.error("BF16 not supported by GPU")

    from lumacarve_runtime.kernels.anima_residual import fused_gated_residual

    dtype = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}[args.dtype]
    batch, tokens, channels = args.batch, args.tokens, args.channels
    g_tokens = tokens if args.gate_tokens == "per-token" else 1
    # Strided gate slice matches the actual Cosmos AdaLN output from chunk(3).
    packed = torch.randn((batch, g_tokens, 3 * channels), dtype=dtype, device="cuda")
    gate = packed.chunk(3, dim=-1)[2]
    residual = torch.randn((batch, tokens, channels), dtype=dtype, device="cuda")
    branch = torch.randn((batch, tokens, channels), dtype=dtype, device="cuda")

    reference = lambda: residual + gate * branch
    optimized = lambda: fused_gated_residual(residual, gate, branch)

    with torch.inference_mode():
        t0 = time.perf_counter()
        fused = optimized()  # explicitly pay first JIT/driver initialization
        torch.cuda.synchronize()
        cold_ms = (time.perf_counter() - t0) * 1000
        native = reference()
        tol = (2e-5, 2e-5) if dtype == torch.float32 else (
            (4e-3, 4e-3) if dtype == torch.float16 else (3e-2, 3e-2)
        )
        torch.testing.assert_close(fused, native, rtol=tol[0], atol=tol[1])

        def cuda_latency_ms(fn):
            for _ in range(10):
                fn()
            torch.cuda.synchronize()
            start = torch.cuda.Event(enable_timing=True)
            end = torch.cuda.Event(enable_timing=True)
            start.record()
            for _ in range(args.repetitions):
                fn()
            end.record()
            end.synchronize()
            return start.elapsed_time(end) / args.repetitions

        torch_ms = cuda_latency_ms(reference)
        triton_ms = cuda_latency_ms(optimized)

    print(json.dumps({
        "gpu": torch.cuda.get_device_name(),
        "dtype": args.dtype,
        "shape": [batch, tokens, channels],
        "gate_tokens": g_tokens,
        "repetitions": args.repetitions,
        "jit_first_call_ms": round(cold_ms, 3),
        "torch_ms": round(torch_ms, 6),
        "triton_ms": round(triton_ms, 6),
        "microbenchmark_speedup": round(torch_ms / triton_ms, 3) if triton_ms else None,
        "note": "No end-to-end inference or output-quality claim. Manual opt-in microbenchmark only.",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
