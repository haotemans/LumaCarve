#!/usr/bin/env python3
"""Bootstrap a single repository-root .venv for LumaCarve.

Default: core + inference + training + optional attention attempt on Linux CUDA.
Windows CUDA: SDPA safe default (Flash/Sage require validated platform wheels).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import venv
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
VENV = ROOT / ".venv"
REPORT = ROOT / "LumaCarveData" / "dependency-install.json"


def venv_python(root: Path = VENV) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def command(argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(argv), flush=True)
    return subprocess.run(argv, check=check)


def torch_index(choice: str) -> str | None:
    return None if choice == "default" else f"https://download.pytorch.org/whl/{choice}"


def plan_attention(requested: str, *, system: str, cuda_available: bool, toolkit: bool) -> tuple[list[str], str | None]:
    if requested == "none":
        return [], None
    if not cuda_available:
        return [], "GPU CUDA not available; using PyTorch SDPA"
    if system == "Windows":
        return [], "Windows: flash-attn/SageAttention auto-build skipped; use verified wheels or Linux/WSL2"
    if not toolkit:
        return [], "CUDA Toolkit (nvcc) not available; using PyTorch SDPA"
    packages = ["flash-attn", "sageattention"] if requested in ("auto", "both") else [requested]
    return packages, None


def main() -> int:
    parser = argparse.ArgumentParser(description="LumaCarve single-.venv dependency installer")
    parser.add_argument("--torch", choices=["default", "cpu", "cu126", "cu128", "cu130"], default="default",
                        help="PyTorch official wheel index; use appropriate CUDA wheel for your GPU/driver")
    parser.add_argument("--attention", choices=["auto", "both", "flash-attn", "sageattention", "none"], default="auto")
    parser.add_argument("--profile", choices=["full", "api"], default="full")
    parser.add_argument("--strict-attention", action="store_true", help="Fail instead of SDPA fallback")
    parser.add_argument("--upgrade", action="store_true", help="Upgrade installed packages")
    args = parser.parse_args()
    if not venv_python().is_file():
        venv.EnvBuilder(with_pip=True, clear=False).create(VENV)
    python = str(venv_python())
    pip = [python, "-m", "pip"]
    command(pip + ["install", "--upgrade", "pip", "setuptools", "wheel"])

    report: dict[str, object] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "venv": str(VENV),
        "profile": args.profile,
        "torch_index": args.torch,
        "attention_requested": args.attention,
        "attention_installed": [],
        "fallback": None,
    }
    try:
        if args.profile == "full":
            cmd = pip + ["install"] + (["--upgrade"] if args.upgrade else []) + ["torch"]
            index = torch_index(args.torch)
            if index:
                cmd += ["--index-url", index]
            command(cmd)
            # -e installs API and ML dependencies in the same project environment.
            command(pip + ["install", "--upgrade-strategy", "only-if-needed", "-e", str(BACKEND) + "[inference,training,dev]"])
        else:
            command(pip + ["install", "-e", str(BACKEND) + "[dev]"])
        probe = subprocess.run(
            [python, "-c", "import torch; print(int(torch.cuda.is_available()))"],
            capture_output=True, text=True, check=False,
        ) if args.profile == "full" else None
        cuda = bool(probe and probe.returncode == 0 and probe.stdout.strip() == "1")
        nvcc = subprocess.run(["nvcc", "--version"],capture_output=True,check=False) if cuda and platform.system() != "Windows" else None
        toolkit = bool(nvcc and nvcc.returncode == 0)
        report["cuda_available"] = cuda
        packages, reason = plan_attention(args.attention, system=platform.system(),cuda_available=cuda,toolkit=toolkit)
        report["fallback"] = reason
        if args.profile == "full" and packages:
            command(pip + ["install", "ninja", "packaging", "psutil"])
            for package in packages:
                result = command(pip + ["install", "--no-build-isolation", package], check=False)
                if result.returncode:
                    if args.strict_attention:
                        raise RuntimeError(f"{package} installation failed (strict attention mode)")
                    report["fallback"] = f"{package} installation failed; PyTorch SDPA remains available"
                else:
                    report["attention_installed"].append(package)
        if args.strict_attention and args.attention != "none" and args.profile == "full":
            if len(report["attention_installed"]) != len(packages) or reason:
                raise RuntimeError(reason or "Attention installation incomplete")
        print("LumaCarve environment ready:", python)
        print("Attention:", report["attention_installed"] or "PyTorch SDPA")
        if report["fallback"]:
            print("Note:", report["fallback"])
        return 0
    finally:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
        print("Dependency report:", REPORT)


if __name__ == "__main__":
    raise SystemExit(main())
