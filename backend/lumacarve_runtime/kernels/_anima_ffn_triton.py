"""Anima/Cosmos experimental first FFN projection + exact GELU epilogue.

The first FFN operation in Diffusers Cosmos is Linear(K -> N) followed by
GELU(approximate="none"). This kernel fuses both into one Triton GEMM launch
and avoids writing a separate pre-GELU [B,S,N] activation.

This is a candidate optimization: PyTorch/cuBLAS may still be faster on many
GPUs. It is never enabled automatically, and NEVER benchmarks/autotunes while
generating images.
"""
from __future__ import annotations

import triton
import triton.language as tl
from triton.language.extra import libdevice


@triton.jit
def _linear_exact_gelu(
    x_ptr,
    weight_ptr,
    bias_ptr,
    out_ptr,
    rows,
    out_features: tl.constexpr,
    in_features: tl.constexpr,
    has_bias: tl.constexpr,
    block_m: tl.constexpr,
    block_n: tl.constexpr,
    block_k: tl.constexpr,
):
    row_idx = tl.program_id(0) * block_m + tl.arange(0, block_m)
    col_idx = tl.program_id(1) * block_n + tl.arange(0, block_n)
    inner_idx = tl.arange(0, block_k)

    accumulator = tl.full((block_m, block_n), 0.0, tl.float32)
    for block_idx in range(tl.cdiv(in_features, block_k)):
        k = block_idx * block_k + inner_idx
        lhs = tl.load(
            x_ptr + row_idx[:, None] * in_features + k[None, :],
            mask=(row_idx[:, None] < rows) & (k[None, :] < in_features),
            other=0,
        )
        # Weight layout is [out_features, in_features]; contiguous K loads
        # are transposed within the Triton program for the GEMM.
        rhs = tl.load(
            weight_ptr + col_idx[:, None] * in_features + k[None, :],
            mask=(col_idx[:, None] < out_features) & (k[None, :] < in_features),
            other=0,
        )
        accumulator = tl.dot(lhs, tl.trans(rhs), accumulator)

    if has_bias:
        bias = tl.load(
            bias_ptr + col_idx,
            mask=col_idx < out_features,
            other=0,
        ).to(tl.float32)
        accumulator = accumulator + bias[None, :]

    # Native F.linear returns an input-dtype tensor before F.gelu runs.
    # Match this round-to-FP16/BF16 boundary instead of applying GELU to
    # the full-precision GEMM accumulator.
    projected = accumulator.to(x_ptr.dtype.element_ty).to(tl.float32)
    # Diffusers GELU(approximate="none") uses the erf definition, not tanh.
    activated = 0.5 * projected * (
        1.0 + libdevice.erf(projected * 0.7071067811865476)
    )
    output = activated.to(x_ptr.dtype.element_ty)
    tl.store(
        out_ptr + row_idx[:, None] * out_features + col_idx[None, :],
        output,
        mask=(row_idx[:, None] < rows) & (col_idx[None, :] < out_features),
    )


def launch(hidden_states, weight, bias):
    """Execute one non-autotuned CUDA GEMM+GELU kernel.

    Inputs are prevalidated contiguous FP16/BF16 tensors; weight is [N,K],
    hidden_states is [B,S,K], bias is None or [N]. Output is [B,S,N].
    """
    batch, tokens, in_features = hidden_states.shape
    out_features = weight.shape[0]
    result = hidden_states.new_empty((batch, tokens, out_features))

    block_m, block_n, block_k = 32, 64, 32
    rows = batch * tokens
    _linear_exact_gelu[
        (triton.cdiv(rows, block_m), triton.cdiv(out_features, block_n))
    ](
        hidden_states,
        weight,
        bias if bias is not None else weight,
        result,
        rows,
        out_features,
        in_features,
        bias is not None,
        block_m,
        block_n,
        block_k,
        num_warps=4,
        num_stages=3,
        enable_fp_fusion=False,
    )
    return result
