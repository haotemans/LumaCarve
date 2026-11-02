"""Opt-in Triton fused AdaLN-Zero for Diffusers Anima/Cosmos inference.

Never imports torch, Triton, or Diffusers at API startup. The installer patches
only three known norm sites in each CosmosTransformerBlock instance, and can
fall back to the original forward method without affecting checkpoint weights.
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass
from types import MethodType
from typing import Any

log = logging.getLogger(__name__)
_MAX_CHANNELS = 8192
_ALLOWED_DTYPES = ("torch.float16", "torch.bfloat16", "torch.float32")


@dataclass(frozen=True, slots=True)
class AnimaKernelReport:
    installed: int
    reason: str


def _compatible(x: Any, shift: Any, scale: Any) -> bool:
    """No GPU queries, conversions, copies, or tensor allocations."""
    try:
        if (
            x.device.type != "cuda" or x.ndim != 3 or not x.is_contiguous()
            or x.dtype != shift.dtype or x.dtype != scale.dtype
            or str(x.dtype) not in _ALLOWED_DTYPES
        ):
            return False
        batch, tokens, channels = x.shape
        if batch < 1 or tokens < 1 or not 1 <= channels <= _MAX_CHANNELS:
            return False
        if shift.shape != scale.shape or shift.ndim != 3:
            return False
        if shift.shape[0] != batch or shift.shape[2] != channels:
            return False
        if shift.shape[1] not in (1, tokens):
            return False
        if shift.device != x.device or scale.device != x.device:
            return False
        # PyTorch chunk(3) yields strided views; do not materialize them to fuse.
        return shift.stride(-1) == 1 and scale.stride(-1) == 1
    except (AttributeError, TypeError, ValueError):
        return False


def _grad_enabled() -> bool:
    torch = sys.modules.get("torch")
    return bool(torch is not None and torch.is_grad_enabled())


def fused_ada_layer_norm(x: Any, shift: Any, scale: Any, eps: float) -> Any:
    """GPU-only forward. Must be used under no_grad/inference_mode."""
    from ._anima_adaln_triton import launch

    return launch(x, shift, scale, eps)


def _triton_available() -> bool:
    return importlib.util.find_spec("triton") is not None


def _resolve_cosmos_zero_type():
    from diffusers.models.transformers.transformer_cosmos import CosmosAdaLayerNormZero

    return CosmosAdaLayerNormZero


def install_anima_adaln_triton(pipeline: Any) -> AnimaKernelReport:
    """Patch loaded Anima CosmosTransformer3DModel instances, opt-in only.

    No Triton compilation or CUDA allocations happen here. On the first kernel
    runtime failure the entire pipeline's set of patches disables itself and
    uses the original PyTorch implementation for the remainder of its lifetime.
    """
    if not _triton_available():
        return AnimaKernelReport(0, "Triton not installed; original PyTorch path retained")
    try:
        cosmos_zero_type = _resolve_cosmos_zero_type()
    except ImportError:
        return AnimaKernelReport(0, "Compatible Diffusers Cosmos AdaLN-Zero class not found")

    transformer = getattr(pipeline, "transformer", None)
    blocks = getattr(transformer, "transformer_blocks", None)
    if blocks is None:
        return AnimaKernelReport(0, "No Cosmos transformer_blocks on the loaded pipeline")

    # All installed sites share one circuit breaker: repeated JIT failures must
    # not trigger thousands of compilation attempts in one denoising loop.
    state = {"active": True}
    count = 0
    for block in blocks:
        for name in ("norm1", "norm2", "norm3"):
            module = getattr(block, name, None)
            if type(module) is not cosmos_zero_type or hasattr(module, "_lumacarve_original_forward"):
                continue
            norm = getattr(module, "norm", None)
            if (
                norm is None or getattr(norm, "elementwise_affine", True)
                or getattr(norm, "eps", None) != 1e-6
                or not all(hasattr(module, key) for key in ("activation", "linear_1", "linear_2"))
            ):
                continue
            # Hold the original *unbound* class method: avoids a reference cycle.
            original = type(module).forward

            def accelerated(self, hidden_states, embedded_timestep, temb=None, _original=original):
                # No compilation, activation, or extra tensor ops on fallback.
                if not state["active"] or _grad_enabled() or getattr(hidden_states, "requires_grad", False):
                    return _original(self, hidden_states, embedded_timestep, temb)
                if not (
                    getattr(hidden_states, "ndim", None) == 3
                    and getattr(getattr(hidden_states, "device", None), "type", None) == "cuda"
                ):
                    return _original(self, hidden_states, embedded_timestep, temb)

                # These operations are identical to Diffusers CosmosAdaLayerNormZero.
                emb = self.linear_2(self.linear_1(self.activation(embedded_timestep)))
                if temb is not None:
                    emb = emb + temb
                if emb.shape[-1] != 3 * hidden_states.shape[-1]:
                    return _original(self, hidden_states, embedded_timestep, temb)
                shift, scale, gate = emb.chunk(3, dim=-1)
                if emb.ndim == 2:
                    shift, scale, gate = (value.unsqueeze(1) for value in (shift, scale, gate))
                if not _compatible(hidden_states, shift, scale):
                    return _original(self, hidden_states, embedded_timestep, temb)
                try:
                    output = fused_ada_layer_norm(hidden_states, shift, scale, self.norm.eps)
                except Exception:
                    state["active"] = False
                    log.exception("Anima Triton AdaLN failed; switching all patched sites to PyTorch")
                    return _original(self, hidden_states, embedded_timestep, temb)
                return output, gate

            module._lumacarve_original_forward = original
            module.forward = MethodType(accelerated, module)
            count += 1
    if not count:
        return AnimaKernelReport(0, "No compatible, unpatched Cosmos AdaLN-Zero sites")
    return AnimaKernelReport(count, "Experimental Triton AdaLN-Zero installed; JIT occurs on first use")
