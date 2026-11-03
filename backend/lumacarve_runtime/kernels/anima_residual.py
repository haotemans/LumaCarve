"""Experimental Cosmos gated-residual fusion for Diffusers Anima inference.

Only exact, unmodified CosmosTransformerBlock instances are patched; model
weights, attention processors, feed-forward layers and class globals remain
untouched. GPU code is imported only on an eligible forward call.
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass
from types import MethodType
from typing import Any

log = logging.getLogger(__name__)
_DTYPES = ("torch.float16", "torch.bfloat16", "torch.float32")


@dataclass(frozen=True, slots=True)
class AnimaResidualReport:
    installed: int
    reason: str


def _torch_inference_safe() -> bool:
    """No GPU queries; avoid injecting a forward-only kernel into autograd/compile."""
    torch = sys.modules.get("torch")
    if torch is None or torch.is_grad_enabled():
        return False
    if torch.onnx.is_in_onnx_export() or torch.jit.is_tracing():
        return False
    dynamo = getattr(torch, "_dynamo", None)
    return dynamo is None or not dynamo.is_compiling()


def _compatible(residual: Any, gate: Any, branch: Any) -> bool:
    """Validate shapes, device, dtype and strides using Python metadata only."""
    try:
        if residual.ndim != 3 or branch.ndim != 3 or gate.ndim != 3:
            return False
        if residual.shape != branch.shape or str(residual.dtype) not in _DTYPES:
            return False
        batch, tokens, channels = residual.shape
        if batch < 1 or tokens < 1 or channels < 1 or channels > 8192:
            return False
        if gate.shape[0] != batch or gate.shape[1] not in (1, tokens) or gate.shape[2] != channels:
            return False
        if residual.dtype != gate.dtype or residual.dtype != branch.dtype:
            return False
        if residual.device.type != "cuda" or residual.device != gate.device or residual.device != branch.device:
            return False
        return (
            residual.stride(-1) == 1
            and branch.stride(-1) == 1
            and gate.stride(-1) == 1
        )
    except (AttributeError, TypeError, ValueError):
        return False


def fused_gated_residual(residual: Any, gate: Any, branch: Any) -> Any:
    """One fused forward CUDA operation; no autotune."""
    from ._anima_residual_triton import launch

    return launch(residual, gate, branch)


def _triton_available() -> bool:
    return importlib.util.find_spec("triton") is not None


def _cosmos_block_class():
    from diffusers.models.transformers.transformer_cosmos import CosmosTransformerBlock

    return CosmosTransformerBlock


def _combine(residual: Any, gate: Any, branch: Any, state: dict[str, bool]) -> Any:
    if state["active"] and _compatible(residual, gate, branch):
        try:
            return fused_gated_residual(residual, gate, branch)
        except Exception:
            # Stop *all* subsequent attempts in this pipeline, without losing
            # the current block's already-computed QKV/MLP intermediates.
            state["active"] = False
            log.exception("Anima residual Triton failed; falling back to PyTorch")
    return residual + gate * branch


def install_anima_residual_triton(pipeline: Any) -> AnimaResidualReport:
    """Install a forward-only optimization on precisely compatible Cosmos blocks.

    The copy of forward below mirrors Diffusers v0.42.1 CosmosTransformerBlock
    for the standard Anima path. Optional controlnet/before/after projection and
    training/compile paths always use the original implementation. No kernel
    compilation or CUDA allocations are performed during installation.
    """
    if not _triton_available():
        return AnimaResidualReport(0, "Triton unavailable; original block forward preserved")
    try:
        block_type = _cosmos_block_class()
    except ImportError:
        return AnimaResidualReport(0, "Diffusers CosmosTransformerBlock not found")

    transformer = getattr(pipeline, "transformer", None)
    blocks = getattr(transformer, "transformer_blocks", None)
    if blocks is None:
        return AnimaResidualReport(0, "Anima pipeline has no Cosmos transformer_blocks")

    state = {"active": True}
    installed = 0
    for block in blocks:
        if type(block) is not block_type or hasattr(block, "_lumacarve_residual_original"):
            continue
        # Never override a preexisting per-instance forward hook/wrapper
        # installed by Accelerate, another extension, or the model provider.
        if getattr(getattr(block, "forward", None), "__func__", None) is not type(block).forward:
            continue
        if getattr(block, "before_proj", None) is not None or getattr(block, "after_proj", None) is not None:
            continue
        if not all(callable(getattr(block, name, None)) for name in ("norm1", "norm2", "norm3", "attn1", "attn2", "ff")):
            continue

        original = type(block).forward

        def accelerated(
            self,
            hidden_states,
            encoder_hidden_states,
            embedded_timestep,
            temb=None,
            image_rotary_emb=None,
            extra_pos_emb=None,
            attention_mask=None,
            controlnet_residual=None,
            latents=None,
            block_idx=None,
            _original=original,
            **kwargs,
        ):
            if (
                not state["active"]
                or not _torch_inference_safe()
                or controlnet_residual is not None
                or getattr(self, "before_proj", None) is not None
                or getattr(self, "after_proj", None) is not None
                or kwargs
                or getattr(hidden_states, "requires_grad", False)
                or getattr(hidden_states, "ndim", None) != 3
                or getattr(getattr(hidden_states, "device", None), "type", None) != "cuda"
            ):
                return _original(
                    self, hidden_states, encoder_hidden_states, embedded_timestep,
                    temb=temb, image_rotary_emb=image_rotary_emb,
                    extra_pos_emb=extra_pos_emb, attention_mask=attention_mask,
                    controlnet_residual=controlnet_residual, latents=latents,
                    block_idx=block_idx, **kwargs,
                )
            # Exact Diffusers CosmosTransformerBlock 0.42.x execution order.
            if extra_pos_emb is not None:
                hidden_states = hidden_states + extra_pos_emb
            norm_hidden, gate = self.norm1(hidden_states, embedded_timestep, temb)
            attention_output = self.attn1(norm_hidden, image_rotary_emb=image_rotary_emb)
            hidden_states = _combine(hidden_states, gate, attention_output, state)

            norm_hidden, gate = self.norm2(hidden_states, embedded_timestep, temb)
            attention_output = self.attn2(
                norm_hidden,
                encoder_hidden_states=encoder_hidden_states,
                attention_mask=attention_mask,
            )
            hidden_states = _combine(hidden_states, gate, attention_output, state)

            norm_hidden, gate = self.norm3(hidden_states, embedded_timestep, temb)
            ff_output = self.ff(norm_hidden)
            return _combine(hidden_states, gate, ff_output, state)

        block._lumacarve_residual_original = original
        block.forward = MethodType(accelerated, block)
        installed += 1

    if not installed:
        return AnimaResidualReport(0, "No unmodified compatible Cosmos blocks")
    return AnimaResidualReport(installed, "Experimental 3-way gated residual fusion; JIT only on first eligible call")
