"""Forward-only Triton fusion for the three Anima Cosmos gated residuals.

The Diffusers reference evaluates `residual + gate * branch` separately
after self-attention, cross-attention, and GELU FeedForward. This kernel
performs one CUDA launch, avoids the intermediate product allocation, and
preserves the intermediate dtype rounding of PyTorch elementwise multiply.

No dynamic benchmarking or Triton autotune happens on the inference path.
"""
from __future__ import annotations

import triton
import triton.language as tl


@triton.jit
def _gated_residual(
    residual_ptr,
    branch_ptr,
    gate_ptr,
    output_ptr,
    total_elements,
    seq_len,
    gate_tokens,
    residual_stride_b,
    residual_stride_s,
    residual_stride_c,
    branch_stride_b,
    branch_stride_s,
    branch_stride_c,
    gate_stride_b,
    gate_stride_s,
    gate_stride_c,
    channels: tl.constexpr,
    block: tl.constexpr,
):
    offset = tl.program_id(0) * block + tl.arange(0, block)
    valid = offset < total_elements
    channel = offset % channels
    row = offset // channels
    token = row % seq_len
    batch = row // seq_len
    gate_token = tl.where(gate_tokens == 1, 0, token)

    residual_offset = batch * residual_stride_b + token * residual_stride_s + channel * residual_stride_c
    branch_offset = batch * branch_stride_b + token * branch_stride_s + channel * branch_stride_c
    gate_offset = batch * gate_stride_b + gate_token * gate_stride_s + channel * gate_stride_c

    residual = tl.load(residual_ptr + residual_offset, valid, other=0).to(tl.float32)
    branch = tl.load(branch_ptr + branch_offset, valid, other=0).to(tl.float32)
    gate = tl.load(gate_ptr + gate_offset, valid, other=0).to(tl.float32)

    # PyTorch computes gate * branch in the tensor dtype, then adds residual.
    # Preserve that product rounding even for BF16 and FP16.
    product = (gate * branch).to(residual_ptr.dtype.element_ty)
    result = (residual + product.to(tl.float32)).to(residual_ptr.dtype.element_ty)
    tl.store(output_ptr + offset, result, valid)


def launch(residual, gate, branch):
    """Run a single fused kernel for [B,S,C] and a broadcastable [B,1|S,C] gate."""
    import torch

    batch, tokens, channels = residual.shape
    result = torch.empty((batch, tokens, channels), dtype=residual.dtype, device=residual.device)
    total = batch * tokens * channels
    _gated_residual[(triton.cdiv(total, 1024),)](
        residual,
        branch,
        gate,
        result,
        total,
        tokens,
        gate.shape[1],
        *residual.stride(),
        *branch.stride(),
        *gate.stride(),
        channels,
        1024,
        num_warps=4,
        enable_fp_fusion=False,
    )
    return result
