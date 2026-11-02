"""Experimental Anima/Cosmos fused Q/K rotary position embedding.

The Cosmos self-attention processor uses half-split RoPE on normalized Q/K.
This adapter replaces only the exact Diffusers CosmosAttnProcessor2_0
instances owned by Anima's attn1 blocks, never global Diffusers functions.

Torch, Diffusers, and Triton are never imported at HTTP startup. A failed
Triton launch trips a shared circuit breaker and preserves original inference.
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

_DTYPES = frozenset(("torch.float16", "torch.bfloat16", "torch.float32"))


@dataclass(frozen=True, slots=True)
class AnimaRoPEReport:
    installed: int
    reason: str


def _compatible(q: Any, k: Any, cos: Any, sin: Any) -> bool:
    """CPU-only metadata check. The kernel accepts strided Q/K/frequency views."""
    try:
        if q.ndim != 4 or k.shape != q.shape or k.ndim != 4:
            return False
        batch, heads, seq_len, dim = q.shape
        if min(batch, heads, seq_len) < 1 or dim < 16 or dim > 256 or dim % 2:
            return False
        if (
            q.device.type != "cuda" or q.device != k.device
            or str(q.dtype) not in _DTYPES or k.dtype != q.dtype
            or q.stride(-1) != 1 or k.stride(-1) != 1
        ):
            return False
        for frequencies in (cos, sin):
            if frequencies.ndim != 2 or tuple(frequencies.shape) != (seq_len, dim):
                return False
            if frequencies.device != q.device or str(frequencies.dtype) != "torch.float32":
                return False
            if frequencies.stride(-1) != 1:
                return False
        return True
    except (AttributeError, TypeError, ValueError):
        return False


def _forward_safe() -> bool:
    """Exclude training, autograd, tracing and graph compilation."""
    torch = sys.modules.get("torch")
    if torch is None or torch.is_grad_enabled():
        return False
    if torch.onnx.is_in_onnx_export() or torch.jit.is_tracing():
        return False
    dynamo = getattr(torch, "_dynamo", None)
    if dynamo is not None and dynamo.is_compiling():
        return False
    return True


def fused_qk_rotary(q: Any, k: Any, cos: Any, sin: Any):
    """Only called after safe shape/device checks; no autotune."""
    from ._anima_rope_triton import launch

    return launch(q, k, cos, sin)


def _triton_available() -> bool:
    return importlib.util.find_spec("triton") is not None


def _processor_class():
    from diffusers.models.transformers.transformer_cosmos import CosmosAttnProcessor2_0
    return CosmosAttnProcessor2_0


def _dispatch_attention_fn():
    from diffusers.models.attention_dispatch import dispatch_attention_fn
    return dispatch_attention_fn


class _FusedCosmosSelfAttention:
    """Preserve the baseline processor contract while replacing only Q/K RoPE."""

    def __init__(self, original: Any, state: dict[str, bool], dispatch: Any):
        self.original = original
        self.state = state
        self.dispatch = dispatch

    def __call__(
        self, attn: Any, hidden_states: Any,
        encoder_hidden_states: Any = None,
        attention_mask: Any = None,
        image_rotary_emb: Any = None,
    ) -> Any:
        # Never intercept cross-attention, training or paths without rotary
        # embeddings. No GPU work or allocations precede these guards.
        if (
            not self.state["active"]
            or encoder_hidden_states is not None
            or image_rotary_emb is None
            or not _forward_safe()
            or getattr(hidden_states, "requires_grad", False)
        ):
            return self.original(
                attn, hidden_states,
                encoder_hidden_states=encoder_hidden_states,
                attention_mask=attention_mask,
                image_rotary_emb=image_rotary_emb,
            )
        if (
            not isinstance(image_rotary_emb, tuple)
            or len(image_rotary_emb) != 2
            or getattr(getattr(hidden_states, "device", None), "type", None) != "cuda"
        ):
            return self.original(
                attn, hidden_states, encoder_hidden_states=encoder_hidden_states,
                attention_mask=attention_mask, image_rotary_emb=image_rotary_emb,
            )

        cos, sin = image_rotary_emb
        # Match the original CosmosAttnProcessor2_0 projection/normalization
        # order exactly. LoRA-aware Linear modules remain untouched.
        query = attn.to_q(hidden_states)
        key = attn.to_k(hidden_states)
        value = attn.to_v(hidden_states)
        query = query.unflatten(2, (attn.heads, -1)).transpose(1, 2)
        key = key.unflatten(2, (attn.heads, -1)).transpose(1, 2)
        value = value.unflatten(2, (attn.heads, -1)).transpose(1, 2)
        query = attn.norm_q(query)
        key = attn.norm_k(key)

        if not _compatible(query, key, cos, sin):
            return self.original(
                attn, hidden_states, encoder_hidden_states=encoder_hidden_states,
                attention_mask=attention_mask, image_rotary_emb=image_rotary_emb,
            )
        try:
            query, key = fused_qk_rotary(query, key, cos, sin)
        except Exception:
            self.state["active"] = False
            log.exception("Anima fused RoPE failed; permanently falling back to Diffusers for this pipeline")
            return self.original(
                attn, hidden_states, encoder_hidden_states=encoder_hidden_states,
                attention_mask=attention_mask, image_rotary_emb=image_rotary_emb,
            )

        # Match the rest of CosmosAttnProcessor2_0 and preserve Diffusers'
        # registered Attention implementation (Flash/SDPA/etc.).
        q_dim = query.size(3)
        k_dim = key.size(3)
        v_dim = value.size(3)
        key = key.repeat_interleave(q_dim // k_dim, dim=3)
        value = value.repeat_interleave(q_dim // v_dim, dim=3)
        result = self.dispatch(
            query.transpose(1, 2),
            key.transpose(1, 2),
            value.transpose(1, 2),
            attn_mask=attention_mask, dropout_p=0.0, is_causal=False,
        )
        result = result.flatten(2, 3).type_as(query)
        result = attn.to_out[0](result)
        return attn.to_out[1](result)


def install_anima_rope_triton(pipeline: Any) -> AnimaRoPEReport:
    """Install only on loaded Anima attn1 self-attention blocks (explicit opt-in).

    Never compiles or launches kernels at install time. Incompatible processor
    types (including custom attention implementations) are left untouched.
    """
    if not _triton_available():
        return AnimaRoPEReport(0, "Triton unavailable; original Diffusers self-attention preserved")
    try:
        processor_cls = _processor_class()
        dispatch = _dispatch_attention_fn()
    except ImportError:
        return AnimaRoPEReport(0, "Compatible Diffusers Cosmos attention implementation unavailable")

    transformer = getattr(pipeline, "transformer", None)
    blocks = getattr(transformer, "transformer_blocks", None)
    if blocks is None:
        return AnimaRoPEReport(0, "Loaded pipeline does not expose Cosmos transformer blocks")

    state = {"active": True}
    count = 0
    for block in blocks:
        attn = getattr(block, "attn1", None)
        if not (callable(getattr(attn, "get_processor", None)) and callable(getattr(attn, "set_processor", None))):
            continue
        processor = attn.get_processor()
        if type(processor) is not processor_cls:
            continue
        attn.set_processor(_FusedCosmosSelfAttention(processor, state, dispatch))
        count += 1

    return AnimaRoPEReport(
        count, "Experimental fused RoPE installed; first CUDA call JIT-compiles"
        if count else "No supported Cosmos self-attention processors found",
    )
