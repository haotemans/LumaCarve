"""Pure, deterministic source selection. No IP/location probes, network or package imports."""
from __future__ import annotations

import locale
import os

CHINA_PYPI = "https://pypi.tuna.tsinghua.edu.cn/simple"
GLOBAL_PYPI = "https://pypi.org/simple/"
CHINA_TORCH = "https://mirrors.cernet.edu.cn/pytorch/whl/"
OFFICIAL_TORCH = "https://download.pytorch.org/whl/"
ALLOWED_REGIONS = ("auto", "cn", "global")


def resolve_region(requested: str = "auto", *, language: str | None = None,
                   environment: dict[str, str] | None = None) -> str:
    """Resolve from explicit opt-in/env/OS locale, never from geographic IP.

    The environment override is meaningful for auto only; explicit CLI choice wins.
    """
    if requested not in ALLOWED_REGIONS:
        raise ValueError(f"Unknown region: {requested}")
    if requested != "auto":
        return requested
    env = os.environ if environment is None else environment
    preferred = env.get("LUMACARVE_DOWNLOAD_REGION", "")
    if preferred in ("cn", "global"):
        return preferred
    lang = language if language is not None else (
        env.get("LC_ALL") or env.get("LANGUAGE") or env.get("LANG")
        or locale.getlocale()[0] or ""
    )
    lower = lang.lower().replace("-", "_")
    if lower.startswith("zh_cn") or lower.startswith("zh_hans") or "chinese (simplified)" in lower:
        return "cn"
    return "global"


def pip_index_for_region(region: str) -> str | None:
    if region not in ("cn", "global"):
        raise ValueError("Region must be resolved before choosing an index")
    return CHINA_PYPI if region == "cn" else None


def torch_wheel_index(tag: str, *, region: str = "global", source: str = "auto") -> str | None:
    """PyTorch must come from a CUDA-specific wheel repository, not generic PyPI."""
    if tag not in ("default", "cpu", "cu126", "cu128", "cu130"):
        raise ValueError("Unknown PyTorch wheel tag")
    if region not in ("cn", "global") or source not in ("auto", "official", "cn"):
        raise ValueError("Unknown PyTorch mirror selection")
    if tag == "default":
        return None
    regional = region == "cn" if source == "auto" else source == "cn"
    return (CHINA_TORCH if regional else OFFICIAL_TORCH) + tag
