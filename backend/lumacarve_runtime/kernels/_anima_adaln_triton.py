"""Inference-only Triton implementation of Cosmos AdaLN-Zero's final stage.

This module imports Triton eagerly by design. Its public parent module imports
it only when an explicitly enabled CUDA inference call reaches the kernel.
"""
from __future__ import annotations

import triton
import triton.language as tl


@triton.jit
def _ada_layer_norm_modulate(
    x_ptr,
    shift_ptr,
    scale_ptr,
    out_ptr,
    channels: tl.constexpr,
    tokens: tl.constexpr,
    cond_tokens: tl.constexpr,
    shift_stride_b: tl.constexpr,
    shift_stride_s: tl.constexpr,
    scale_stride_b: tl.constexpr,
    scale_stride_s: tl.constexpr,
    eps: tl.constexpr,
    block: tl.constexpr,
):
    row = tl.program_id(0)
    cols = tl.arange(0, block)
    mask = cols < channels
    offset = row * channels + cols
    x = tl.load(x_ptr + offset, mask=mask, other=0).to(tl.float32)
    mean = tl.sum(x, 0) / channels
    centered = tl.where(mask, x - mean, 0.0)
    variance = tl.sum(centered * centered, 0) / channels
    rstd = tl.rsqrt(variance + eps)

    # Preserve the PyTorch reference's intermediate dtype rounding:
    # LayerNorm -> (1 + scale) -> multiply -> add shift.
    normed = ((x - mean) * rstd).to(x_ptr.dtype.element_ty)
    batch = row // tokens
    token = row % tokens
    if cond_tokens == 1:
        token = 0
    shift_offset = batch * shift_stride_b + token * shift_stride_s + cols
    scale_offset = batch * scale_stride_b + token * scale_stride_s + cols
    scale = tl.load(scale_ptr + scale_offset, mask=mask, other=0).to(tl.float32)
    shift = tl.load(shift_ptr + shift_offset, mask=mask, other=0).to(tl.float32)
    scale_plus_one = (scale + 1.0).to(x_ptr.dtype.element_ty)
    multiplied = (normed.to(tl.float32) * scale_plus_one.to(tl.float32)).to(x_ptr.dtype.element_ty)
    result = (multiplied.to(tl.float32) + shift).to(x_ptr.dtype.element_ty)
    tl.store(out_ptr + offset, result, mask=mask)


def launch(x, shift, scale, eps: float):
    """Execute one fused kernel per (batch, token) row (no autotune)."""
    batch, tokens, channels = x.shape
    output = x.new_empty(x.shape)
    block = triton.next_power_of_2(channels)
    warps = 4 if block <= 4096 else 8
    _ada_layer_norm_modulate[(batch * tokens,)](
        x, shift, scale, output,
        channels, tokens, shift.shape[1], shift.stride(0), shift.stride(1), scale.stride(0), scale.stride(1), eps, block,
        num_warps=warps,
    )
    return output
