#!/usr/bin/env python3
"""Explicit CUDA microbenchmark for Anima's fused Cosmos Q/K RoPE.

No model weights, no implicit downloads and no Triton autotuning. The caller
opts in to GPU measurements; first JIT compilation is excluded from hot timings.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark Diffusers-style Cosmos RoPE vs Triton Q/K fusion")
    parser.add_argument("--tokens", type=int, default=4096)
    parser.add_argument("--heads", type=int, default=16)
    parser.add_argument("--channels", type=int, choices=[64, 128, 256], default=128)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--dtype", choices=["fp16", "bf16", "fp32"], default="bf16")
    args = parser.parse_args(argv)
    if min(args.batch, args.heads, args.tokens) < 1 or args.repetitions < 2:
        parser.error("batch/heads/tokens must be > 0 and repetitions must be >= 2")

    try:
        import torch
        import triton  # noqa: F401
    except ImportError as exc:
        parser.error(f"GPU benchmark requires torch and triton: {exc}")
    if not torch.cuda.is_available():
        parser.error("CUDA GPU is required")
    if args.dtype == "bf16" and not torch.cuda.is_bf16_supported():
        parser.error("GPU does not support BF16")
    from lumacarve_runtime.kernels.anima_rope import fused_qk_rotary

    dtype = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}[args.dtype]
    b, h, s, d = args.batch, args.heads, args.tokens, args.channels
    q = torch.randn((b, s, h, d), dtype=dtype, device="cuda").transpose(1, 2)
    k = torch.randn((b, s, h, d), dtype=dtype, device="cuda").transpose(1, 2)
    angles = torch.randn((s, d // 2), dtype=torch.float32, device="cuda")
    cos = angles.cos().repeat(1, 2)
    sin = angles.sin().repeat(1, 2)

    def rotary(t):
        rotated = torch.cat((-t[..., d // 2 :], t[..., : d // 2]), dim=-1)
        return (t.float() * cos[None, None, :, :] + rotated.float() * sin[None, None, :, :]).to(t.dtype)

    def baseline():
        return rotary(q), rotary(k)

    def experimental():
        return fused_qk_rotary(q, k, cos, sin)

    # A functional test and JIT warm-up precede any timing.
    with torch.inference_mode():
        baseline_q, baseline_k = baseline()
        actual_q, actual_k = experimental()
        atol, rtol = ((2e-5, 2e-5) if dtype == torch.float32 else
                      (2e-3, 2e-3) if dtype == torch.float16 else (2e-2, 2e-2))
        torch.testing.assert_close(actual_q, baseline_q, atol=atol, rtol=rtol)
        torch.testing.assert_close(actual_k, baseline_k, atol=atol, rtol=rtol)

        def time_ms(fn):
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

        baseline_ms = time_ms(baseline)
        triton_ms = time_ms(experimental)
    print(json.dumps({
        "gpu": torch.cuda.get_device_name(),
        "dtype": args.dtype, "shape": [b, h, s, d],
        "repetitions": args.repetitions,
        "torch_ms": round(baseline_ms, 6),
        "triton_ms": round(triton_ms, 6),
        "speedup": round(baseline_ms / triton_ms, 3) if triton_ms else None,
        "note": "RoPE microbenchmark only; not full Anima/Attention performance",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
