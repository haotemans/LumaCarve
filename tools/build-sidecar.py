#!/usr/bin/env python3
"""Freeze core FastAPI for a native Tauri 2 desktop sidecar."""
import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def current_target() -> str:
    machine = platform.machine().lower()
    if machine not in ("x86_64", "amd64"):
        raise SystemExit("Only x86_64 Windows/Linux supported currently")
    if platform.system() == "Windows":
        return "x86_64-pc-windows-msvc"
    if platform.system() == "Linux":
        return "x86_64-unknown-linux-gnu"
    raise SystemExit("Unsupported desktop platform")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=current_target())
    args = parser.parse_args()
    ext = ".exe" if "windows" in args.target else ""
    destination = ROOT / "frontend" / "src-tauri" / "binaries"
    destination.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
        "--name", "lumacarve-api",
        *(["--windowed"] if platform.system() == "Windows" else []),
        "--paths", str(ROOT / "backend"),
        "--collect-submodules", "uvicorn",
        "--collect-submodules", "fastapi",
        "--collect-submodules", "pydantic",
        "--collect-submodules", "lumacarve_server",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "uvicorn.protocols.http.h11_impl",
        "--distpath", str(ROOT / "build" / "sidecar"),
        "--workpath", str(ROOT / "build" / "pyinstaller"),
        "--specpath", str(ROOT / "build" / "spec"),
        str(ROOT / "backend" / "lumacarve_server" / "desktop_entry.py"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    source = ROOT / "build" / "sidecar" / ("lumacarve-api" + ext)
    if not source.is_file():
        raise SystemExit("Missing frozen API sidecar: " + str(source))
    target = destination / ("lumacarve-api-" + args.target + ext)
    shutil.copyfile(source, target)
    target.chmod(0o755)
    print("Sidecar ready:", target)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
