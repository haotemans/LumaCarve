"""Resolve attention backend at runtime without eager CUDA imports.

FlashAttention and SageAttention are optional and never selected on package
presence alone: CUDA, device architecture and execution mode must be suitable.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Callable, Literal

AttentionPreference = Literal["auto", "sdpa", "flash", "sage"]
AttentionKind = Literal["sdpa", "flash", "sage"]


@dataclass(frozen=True, slots=True)
class AttentionSelection:
    requested: str
    selected: AttentionKind
    reason: str


def select_attention(
    requested: AttentionPreference = "auto",
    *,
    cuda_available: bool,
    training: bool,
    flash_installed: bool,
    sage_installed: bool,
    flash_supported: bool = True,
    sage_supported: bool = True,
) -> AttentionSelection:
    """Pure policy; a model adapter must separately verify tensor dtypes/shapes."""
    if requested not in ("auto", "sdpa", "flash", "sage"):
        raise ValueError(f"Unknown attention backend: {requested}")
    if not cuda_available:
        return AttentionSelection(requested, "sdpa", "CUDA unavailable")
    if requested == "sdpa":
        return AttentionSelection(requested, "sdpa", "User selected PyTorch SDPA")
    if requested == "flash":
        if flash_installed and flash_supported:
            return AttentionSelection(requested, "flash", "Explicit FlashAttention preference")
        return AttentionSelection(requested, "sdpa", "FlashAttention missing or unsupported")
    if requested == "sage":
        if not training and sage_installed and sage_supported:
            return AttentionSelection(requested, "sage", "Explicit SageAttention preference")
        return AttentionSelection(requested, "sdpa", "SageAttention unavailable, unsupported or training mode")
    # Auto favors verified exact attention for training; in inference, adapters
    # should benchmark before opting into approximate SageAttention.
    if flash_installed and flash_supported:
        return AttentionSelection(requested, "flash", "FlashAttention available")
    return AttentionSelection(requested, "sdpa", "Safe default; SageAttention requires explicit choice")


def check_packages() -> dict[str, bool]:
    """Safe import-spec check; does not import GPU extension modules."""
    return {
        "torch": importlib.util.find_spec("torch") is not None,
        "flash": importlib.util.find_spec("flash_attn") is not None,
        "sage": importlib.util.find_spec("sageattention") is not None,
    }
