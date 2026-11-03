#!/usr/bin/env python3
"""Opt-in CUDA benchmark: PyTorch Linear+exact GELU vs fused Anima FFN Triton.

This benchmark is deliberately NOT connected to image generation or AMEP. It
reports first JIT/driver cost separately from warm kernel latency and can
optionally compare an explicit torch.compile (Inductor) baseline. No autotune.
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
    parser = argparse.ArgumentParser(description="Anima first FFN Linear+GELU microbenchmark")
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--tokens", type=int, default=512)
    parser.add_argument("--in-features", type=int, default=1024)
    parser.add_argument("--out-features", type=int, default=4096)
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--dtype", choices=["fp16", "bf16"], default="bf16")
    parser.add_argument("--bias", action="store_true", help="Include bias in first FFN Linear")
    parser.add_argument(
        "--compare-compile", action="store_true",
        help="Explicit opt-in to slow torch.compile / Inductor compilation comparison",
    )
    args = parser.parse_args(argv)
    if args.batch < 1 or args.tokens < 1 or args.repetitions < 2:
        parser.error("batch/tokens >=1 and repetitions >=2")
    if not (64 <= args.in_features <= 8192 and 64 <= args.out_features <= 32768):
        parser.error("in/out features outside tested benchmark range")
    if args.in_features % 16 or args.out_features % 16:
        parser.error("in/out features must be multiples of 16")

    try:
        import torch
        import torch.nn.functional as functional
        import triton  # noqa: F401
    except ImportError as exc:
        parser.error(f"PyTorch and Triton required: {exc}")

    if not torch.cuda.is_available():
        parser.error("CUDA GPU required")
    if args.dtype == "bf16" and not torch.cuda.is_bf16_supported():
        parser.error("BF16 is unavailable on this GPU")

    from lumacarve_runtime.kernels.anima_ffn import fused_ffn_linear_gelu

    dtype = torch.bfloat16 if args.dtype == "bf16" else torch.float16
    torch.manual_seed(2026)
    inputs = torch.randn(
        (args.batch, args.tokens, args.in_features), device="cuda", dtype=dtype
    )
    weight = torch.randn(
        (args.out_features, args.in_features), device="cuda", dtype=dtype
    ) * 0.03
    bias = (
        torch.randn((args.out_features,), device="cuda", dtype=dtype) * 0.03
        if args.bias else None
    )

    def baseline(tensor=inputs):
        return functional.gelu(
            functional.linear(tensor, weight, bias), approximate="none"
        )

    def fused(tensor=inputs):
        return fused_ffn_linear_gelu(tensor, weight, bias)

    tolerances = ((0.012, 0.015) if dtype == torch.float16 else (0.06, 0.055))
    def verify(actual, expected):
        torch.testing.assert_close(
            actual, expected, rtol=tolerances[0], atol=tolerances[1]
        )

    def timed_ms(fn):
        for _ in range(8):
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

    with torch.inference_mode():
        reference = baseline()
        clock = time.perf_counter()
        output = fused()
        torch.cuda.synchronize()
        first_call_ms = (time.perf_counter() - clock) * 1000
        verify(output, reference)

        native_ms = timed_ms(baseline)
        triton_ms = timed_ms(fused)
        result = {
            "device": torch.cuda.get_device_name(),
            "pytorch": torch.__version__,
            "dtype": args.dtype,
            "shape": [args.batch, args.tokens, args.in_features, args.out_features],
            "bias": args.bias,
            "repetitions": args.repetitions,
            "triton_first_call_ms": round(first_call_ms, 3),
            "eager_ms": round(native_ms, 5),
            "triton_ms": round(triton_ms, 5),
            "triton_vs_eager": round(native_ms / triton_ms, 3) if triton_ms else None,
            "claim": "microbenchmark only, not full Anima speedup",
        }
        if args.compare_compile:
            if not hasattr(torch, "compile"):
                parser.error("This PyTorch build lacks torch.compile")
            # This potentially performs expensive compilation and benchmarking
            # only because the operator explicitly requested --compare-compile.
            compiled = torch.compile(baseline, fullgraph=True)
            clock = time.perf_counter()
            compiled_output = compiled()
            torch.cuda.synchronize()
            result["inductor_first_call_ms"] = round(
                (time.perf_counter() - clock) * 1000, 3
            )
            verify(compiled_output, reference)
            result["inductor_ms"] = round(timed_ms(compiled), 5)
            result["triton_vs_inductor"] = (
                round(result["inductor_ms"] / triton_ms, 3) if triton_ms else None
            )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
