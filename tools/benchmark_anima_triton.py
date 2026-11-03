#!/usr/bin/env python3
"""Explicit, opt-in CUDA benchmark of the first Anima fused AdaLN kernel.

Does not download models, load weights, or automatically tune CUDA kernels.
The first-run JIT cost is explicitly excluded from warm-kernel timings.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark Anima's Triton fused AdaLN-Zero vs PyTorch")
    parser.add_argument("--tokens", type=int, default=4096)
    parser.add_argument("--channels", type=int, default=2048)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--dtype", choices=["fp16", "bf16", "fp32"], default="bf16")
    args = parser.parse_args(argv)
    if args.batch <= 0 or args.tokens <= 0 or not 1 <= args.channels <= 8192 or args.repetitions < 2:
        parser.error("batch/tokens must be > 0; channels 1..8192; repetitions >= 2")

    try:
        import torch
        import triton  # noqa: F401
    except ImportError as exc:
        parser.error(f"GPU benchmark requires torch and triton: {exc}")
    if not torch.cuda.is_available():
        parser.error("CUDA GPU required")
    if args.dtype == "bf16" and not torch.cuda.is_bf16_supported():
        parser.error("This device does not support BF16")
    from lumacarve_runtime.kernels.anima_adaln import fused_ada_layer_norm

    dtype = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}[args.dtype]
    device = "cuda"
    x = torch.randn(args.batch, args.tokens, args.channels, dtype=dtype, device=device)
    # Match the actual Diffusers AdaLN layout: channel slices share storage
    # and retain the 3*C stride instead of incurring contiguous copies.
    packed = torch.randn(args.batch, 1, 3 * args.channels, dtype=dtype, device=device) * .1
    shift, scale, _gate = packed.chunk(3, dim=-1)
    expected_fn = lambda: torch.nn.functional.layer_norm(x, (args.channels,), eps=1e-6) * (1 + scale) + shift
    triton_fn = lambda: fused_ada_layer_norm(x, shift, scale, 1e-6)

    # Explicitly pay compilation cost before warm-run measurement.
    actual = triton_fn()
    expected = expected_fn()
    atol, rtol = ((2e-4, 2e-4) if dtype == torch.float32 else
                  (8e-3, 8e-3) if dtype == torch.float16 else (3e-2, 2e-2))
    torch.testing.assert_close(actual, expected, atol=atol, rtol=rtol)

    def elapsed_ms(fn):
        for _ in range(10):
            fn()
        torch.cuda.synchronize()
        start, finish = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        start.record()
        for _ in range(args.repetitions):
            fn()
        finish.record()
        finish.synchronize()
        return start.elapsed_time(finish) / args.repetitions

    reference_ms = elapsed_ms(expected_fn)
    triton_ms = elapsed_ms(triton_fn)
    summary = {
        "gpu": torch.cuda.get_device_name(), "dtype": args.dtype,
        "shape": [args.batch, args.tokens, args.channels],
        "repetitions": args.repetitions,
        "pytorch_ms": round(reference_ms, 5), "triton_ms": round(triton_ms, 5),
        "speedup": round(reference_ms / triton_ms, 3) if triton_ms else None,
        "note": "Microbenchmark only; not end-to-end Anima acceleration or a quality guarantee",
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
