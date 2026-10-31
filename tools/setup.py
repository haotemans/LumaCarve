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
import shutil
import tempfile
import subprocess
import sys
import venv
from datetime import datetime, timezone
from pathlib import Path

# Use the shared pure policy module before an editable install exists.

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
VENV = ROOT / ".venv"
REPORT = ROOT / "LumaCarveData" / "dependency-install.json"
sys.path.insert(0, str(BACKEND))
from lumacarve_server.download_sources import pip_index_for_region, resolve_region, torch_wheel_index


def venv_python(root: Path = VENV) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def command(argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(argv), flush=True)
    return subprocess.run(argv, check=check)


def torch_index(choice: str, *, region: str = "global", source: str = "official") -> str | None:
    return torch_wheel_index(choice, region=region, source=source)


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


def plan_rust_scheduler(requested: str, *, cargo_available: bool) -> tuple[bool, str | None]:
    """Build in the shared .venv when possible; never install Rust automatically."""
    if requested not in ("auto", "required", "python"):
        raise ValueError("scheduler must be auto, required or python")
    if requested == "python":
        return False, "Rust scheduler explicitly disabled"
    if not cargo_available:
        if requested == "required":
            raise RuntimeError("Rust scheduler required but Cargo is missing; install Rust via rustup")
        return False, "Cargo not found; using Python fallback"
    return True, None


def install_rust_scheduler(python: str, pip: list[str], mirror_flags: list[str]) -> None:
    """Compile an optional PyO3 extension into the existing environment."""
    command(pip + ["install", "maturin>=1.7,<2"] + mirror_flags)
    with tempfile.TemporaryDirectory(prefix="lumacarve-rust-wheel-") as wheel_dir:
        command([
            python, "-m", "maturin", "build",
            "--manifest-path", str(ROOT / "scheduler" / "Cargo.toml"),
            "--features", "python",
            "--interpreter", python,
            "--out", wheel_dir,
        ])
        wheels = sorted(Path(wheel_dir).glob("lumacarve_scheduler-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("Expected exactly one Rust scheduler wheel")
        command(pip + ["install", "--no-deps", "--force-reinstall", str(wheels[0])])
        command([
            python, "-c",
            "import lumacarve_scheduler; assert callable(lumacarve_scheduler.compile_graph_json)",
        ])


def main() -> int:
    parser = argparse.ArgumentParser(description="LumaCarve single-.venv dependency installer")
    parser.add_argument("--torch", choices=["default", "cpu", "cu126", "cu128", "cu130"], default="default",
                        help="PyTorch official wheel index; use appropriate CUDA wheel for your GPU/driver")
    parser.add_argument("--region", choices=["auto", "cn", "global"], default="auto",
                        help="Download region: auto detects OS language, cn uses mainland mirrors")
    parser.add_argument("--torch-source", choices=["auto", "official", "cn"], default="auto",
                        help="Torch CUDA wheels: regional PyTorch mirror or official")
    parser.add_argument("--attention", choices=["auto", "both", "flash-attn", "sageattention", "none"], default="auto")
    parser.add_argument("--scheduler", choices=["auto", "required", "python"], default="auto",
                        help="Rust scheduler: auto builds with local Cargo, required fails, python skips")
    parser.add_argument("--profile", choices=["full", "api"], default="full")
    parser.add_argument("--strict-attention", action="store_true", help="Fail instead of SDPA fallback")
    parser.add_argument("--upgrade", action="store_true", help="Upgrade installed packages")
    args = parser.parse_args()
    try:
        rust_build, rust_reason = plan_rust_scheduler(args.scheduler, cargo_available=shutil.which("cargo") is not None)
    except RuntimeError as exc:
        parser.error(str(exc))
    region = resolve_region(args.region)
    pip_index = pip_index_for_region(region)
    mirror_flags = ["--index-url", pip_index] if pip_index else []
    if not venv_python().is_file():
        venv.EnvBuilder(with_pip=True, clear=False).create(VENV)
    python = str(venv_python())
    pip = [python, "-m", "pip"]
    command(pip + ["install", "--upgrade", "pip", "setuptools", "wheel"] + mirror_flags)

    report: dict[str, object] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "venv": str(VENV),
        "profile": args.profile,
        "torch_index": args.torch,
        "attention_requested": args.attention,
        "region": region,
        "python_index_url": pip_index or "https://pypi.org/simple/",
        "model_provider": "modelscope" if region == "cn" else "huggingface",
        "torch_wheel_url": torch_index(args.torch, region=region, source=args.torch_source) or "default PyPI index",
        "attention_installed": [],
        "scheduler_requested": args.scheduler,
        "scheduler_backend": "python-fallback",
        "scheduler_reason": rust_reason,
        "fallback": None,
    }
    try:
        if args.profile == "full":
            cmd = pip + ["install"] + (["--upgrade"] if args.upgrade else []) + ["torch"]
            index = torch_index(args.torch, region=region, source=args.torch_source)
            cmd += ["--index-url", index] if index else mirror_flags
            command(cmd)
            # For CUDA wheels, ensure the installed torch contains a CUDA runtime.
            if args.torch.startswith("cu"):
                check = subprocess.run(
                    [python, "-c", "import torch; print(torch.version.cuda or '')"],
                    capture_output=True, text=True, check=False,
                )
                if check.returncode != 0 or not check.stdout.strip():
                    raise RuntimeError("CUDA PyTorch wheel required but CPU-only torch was installed")
                report["torch_runtime_cuda"] = check.stdout.strip()
            # -e uses the SAME venv; hub SDK is only installed for CN mode.
            extras = "inference,training,dev,china" if region == "cn" else "inference,training,dev"
            command(pip + ["install", "--upgrade-strategy", "only-if-needed", "-e", str(BACKEND) + f"[{extras}]"] + mirror_flags)
        else:
            extras = "dev,china" if region == "cn" else "dev"
            command(pip + ["install", "-e", str(BACKEND) + f"[{extras}]"] + mirror_flags)
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
            command(pip + ["install", "ninja", "packaging", "psutil"] + mirror_flags)
            for package in packages:
                result = command(pip + ["install", "--no-build-isolation", package] + mirror_flags, check=False)
                if result.returncode:
                    if args.strict_attention:
                        raise RuntimeError(f"{package} installation failed (strict attention mode)")
                    report["fallback"] = f"{package} installation failed; PyTorch SDPA remains available"
                else:
                    report["attention_installed"].append(package)
        if args.strict_attention and args.attention != "none" and args.profile == "full":
            if len(report["attention_installed"]) != len(packages) or reason:
                raise RuntimeError(reason or "Attention installation incomplete")
        if rust_build:
            try:
                install_rust_scheduler(python, pip, mirror_flags)
                report["scheduler_backend"] = "rust"
                report["scheduler_reason"] = None
            except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
                report["scheduler_reason"] = f"Rust build failed: {exc}"
                if args.scheduler == "required":
                    raise
        print("LumaCarve environment ready:", python)
        print("Download region:", region, "| Python packages:", report["python_index_url"])
        print("Model hub:", report["model_provider"], "| Torch index:", report["torch_wheel_url"])
        print("Attention:", report["attention_installed"] or "PyTorch SDPA")
        print("Graph scheduler:", report["scheduler_backend"], "|", report["scheduler_reason"] or "extension installed")
        if report["fallback"]:
            print("Note:", report["fallback"])
        return 0
    finally:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
        print("Dependency report:", REPORT)


if __name__ == "__main__":
    raise SystemExit(main())
