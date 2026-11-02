"""Opt-in Triton FFN GEMM+GELU fusion for Diffusers Anima Cosmos blocks.

Only the *first* Linear -> GELU pair in an otherwise unmodified
Cosmos FeedForward is changed. The second Linear remains native PyTorch /
cuBLAS, as do dropout and all LoRA wrappers. The optimization is forward-only.

No Torch/Diffusers/Triton import at service startup, no GPU queries during
module selection, and no benchmarking or autotune in inference.
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass
from types import MethodType
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnimaFFNReport:
    installed: int
    reason: str


def _inference_safe() -> bool:
    torch = sys.modules.get("torch")
    if torch is None or torch.is_grad_enabled():
        return False
    if torch.onnx.is_in_onnx_export() or torch.jit.is_tracing():
        return False
    dynamo = getattr(torch, "_dynamo", None)
    if dynamo is not None and dynamo.is_compiling():
        return False
    # Native Linear under autocast may run with different input / weight
    # dtypes than the tensors passed into its forward method.
    autocast = getattr(torch, "is_autocast_enabled", None)
    if autocast is not None:
        try:
            if autocast("cuda"):
                return False
        except TypeError:
            if autocast():
                return False
    return True


def _compatible(hidden_states: Any, projection: Any) -> bool:
    """Metadata checks only: no kernels, copies or GPU memory polling."""
    try:
        if hidden_states.ndim != 3 or not hidden_states.is_contiguous():
            return False
        batch, tokens, channels = hidden_states.shape
        if batch < 1 or tokens < 1 or batch * tokens < 32:
            return False
        if hidden_states.device.type != "cuda":
            return False
        if str(hidden_states.dtype) not in ("torch.float16", "torch.bfloat16"):
            return False
        weight = projection.weight
        if weight.ndim != 2 or not weight.is_contiguous():
            return False
        outer, inner = weight.shape
        if channels != inner or outer < 64 or outer > 32768 or inner < 64:
            return False
        if inner % 16 != 0 or outer % 16 != 0:
            return False
        if weight.device != hidden_states.device or weight.dtype != hidden_states.dtype:
            return False
        bias = projection.bias
        if bias is not None and (
            bias.ndim != 1
            or bias.shape != (outer,)
            or not bias.is_contiguous()
            or bias.device != hidden_states.device
            or bias.dtype != hidden_states.dtype
        ):
            return False
        return True
    except (AttributeError, TypeError, ValueError):
        return False


def _native_projection(projection: Any, linear_type: type) -> bool:
    """Prevent bypassing PEFT/LoRA modules, onload/offload or custom hooks."""
    if type(projection) is not linear_type:
        return False
    forward = getattr(projection, "forward", None)
    if getattr(forward, "__func__", None) is not linear_type.forward:
        return False
    for attr in ("_forward_hooks", "_forward_pre_hooks", "_backward_hooks", "_backward_pre_hooks"):
        if getattr(projection, attr, None):
            return False

    torch = sys.modules.get("torch")
    mod = getattr(getattr(getattr(torch, "nn", None), "modules", None), "module", None)
    if mod is not None:
        for attr in (
            "_global_forward_hooks", "_global_forward_pre_hooks",
            "_global_backward_hooks", "_global_backward_pre_hooks",
        ):
            if getattr(mod, attr, None):
                return False
    return True


def fused_ffn_linear_gelu(hidden_states: Any, weight: Any, bias: Any) -> Any:
    """Lazy import: executes precisely one kernel when explicitly enabled."""
    from ._anima_ffn_triton import launch

    return launch(hidden_states, weight, bias)


def _triton_available() -> bool:
    return importlib.util.find_spec("triton") is not None


def _resolve_model_types():
    from diffusers.models.transformers.transformer_cosmos import CosmosTransformerBlock
    from diffusers.models.attention import FeedForward
    from diffusers.models.activations import GELU
    from torch.nn import Dropout, Linear

    return CosmosTransformerBlock, FeedForward, GELU, Linear, Dropout


def install_anima_ffn_triton(pipeline: Any) -> AnimaFFNReport:
    """Patch only native Cosmos FFN's GELU activation instance, not classes.

    Activation Module.__call__ and the outer FeedForward remain intact.
    Runtime checks catch subsequently-injected LoRA/Offload wrappers. If the
    JIT kernel fails, a pipeline-scoped circuit breaker permanently reverts
    all installed activations to the original Diffusers implementation.
    """
    if not _triton_available():
        return AnimaFFNReport(0, "Triton unavailable; native FFN retained")
    try:
        block_type, ff_type, gelu_type, linear_type, dropout_type = _resolve_model_types()
    except ImportError:
        return AnimaFFNReport(0, "Compatible Diffusers Cosmos FFN classes unavailable")

    transformer = getattr(pipeline, "transformer", None)
    blocks = getattr(transformer, "transformer_blocks", None)
    if blocks is None:
        return AnimaFFNReport(0, "No Cosmos transformer_blocks on loaded Anima")

    state = {"active": True}
    installed = 0
    for block in blocks:
        if type(block) is not block_type:
            continue
        ff = getattr(block, "ff", None)
        if type(ff) is not ff_type or getattr(getattr(ff, "forward", None), "__func__", None) is not ff_type.forward:
            continue
        modules = getattr(ff, "net", ())
        if len(modules) != 3:
            continue
        activation, dropout, output_linear = modules
        if (
            type(activation) is not gelu_type or
            getattr(activation, "approximate", None) != "none" or
            hasattr(activation, "_lumacarve_ffn_original_forward") or
            getattr(getattr(activation, "forward", None), "__func__", None) is not gelu_type.forward or
            type(dropout) is not dropout_type or dropout.p != 0 or
            type(output_linear) is not linear_type
        ):
            continue
        projection = getattr(activation, "proj", None)
        if not _native_projection(projection, linear_type):
            continue

        original = type(activation).forward

        def accelerated(self, hidden_states, _original=original):
            projection = getattr(self, "proj", None)
            if (
                not state["active"]
                or not _inference_safe()
                or getattr(hidden_states, "requires_grad", False)
                or not _native_projection(projection, linear_type)
                or not _compatible(hidden_states, projection)
            ):
                return _original(self, hidden_states)
            try:
                return fused_ffn_linear_gelu(hidden_states, projection.weight, projection.bias)
            except Exception:
                state["active"] = False
                log.exception("Anima Triton FFN GEMM+GELU failed; reverting this pipeline to native FFN")
                return _original(self, hidden_states)

        activation._lumacarve_ffn_original_forward = original
        activation.forward = MethodType(accelerated, activation)
        installed += 1

    if not installed:
        return AnimaFFNReport(0, "No unmodified native Cosmos Linear+exact-GELU sites")
    return AnimaFFNReport(installed, "Experimental fused GEMM+GELU installed; first eligible call may JIT compile")
