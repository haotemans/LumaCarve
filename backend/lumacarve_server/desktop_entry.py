"""Entrypoint for the bundled Tauri 2 FastAPI sidecar (core API only).

PyInstaller freezes the lightweight FastAPI/Pillow service; heavyweight
PyTorch/CUDA/Triton inference is not bundled in this first desktop installer.
The data directory is selected by the Tauri host, never by cwd.\nThe sidecar is not a user-facing executable and must not be opened directly.
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from collections.abc import Mapping
from pathlib import Path


def launch_configuration_error(env: Mapping[str, str]) -> str | None:
    """Reject direct invocation before importing the large API stack."""
    raw_path = env.get("LUMACARVE_DATA_DIR", "")
    if not raw_path or not Path(raw_path).expanduser().is_absolute():
        return "Background service must be started by LumaCarve.exe (missing absolute data directory)"
    token = env.get("LUMACARVE_DESKTOP_TOKEN", "")
    if len(token) != 64 or any(letter not in "0123456789abcdef" for letter in token):
        return "Background service must be started by LumaCarve.exe (missing desktop session token)"
    if env.get("LUMACARVE_HOST") != "127.0.0.1":
        return "Background service must be bound to 127.0.0.1"
    try:
        port = int(env.get("LUMACARVE_PORT", ""))
        if not 1 <= port <= 65535:
            raise ValueError("invalid port")
    except ValueError:
        return "Background service requires a valid local port from LumaCarve.exe"
    return None


def report_launch_configuration_error(message: str) -> None:
    """Tell Windows users to launch the main app, not the PyInstaller sidecar."""
    display = "请运行 LumaCarve.exe，不要单独打开 lumacarve-api.exe。\\n" + message
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, display, "LumaCarve 后台服务", 0x30)
            return
        except Exception:
            pass
    if sys.stderr is not None:
        print(display, file=sys.stderr)


def main() -> int:
    problem = launch_configuration_error(os.environ)
    if problem is not None:
        report_launch_configuration_error(problem)
        return 2
    root = Path(os.environ["LUMACARVE_DATA_DIR"]).expanduser()
    logs = root.parent / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    # A GUI (PyInstaller --windowed) process has no console on Windows.
    # Preserve startup failures in the shared application data directory.
    logfile = open(logs / "api.log", "a", buffering=1, encoding="utf-8")
    sys.stderr = logfile
    sys.stdout = logfile
    try:
        import uvicorn
        from lumacarve_server.app import create_app
        from lumacarve_server.config import Settings

        settings = Settings.from_env()
        if settings.host != "127.0.0.1" or not settings.desktop_token:
            raise RuntimeError("Desktop API must use loopback and a unique session token")
        logging.basicConfig(stream=logfile, level=logging.WARNING, force=True)
        uvicorn.run(
            create_app(settings),
            host=settings.host,
            port=settings.port,
            access_log=False,
            log_config=None,
            loop="asyncio",
            http="h11",
        )
        return 0
    except Exception:
        traceback.print_exc(file=logfile)
        return 1
    finally:
        logfile.close()


if __name__ == "__main__":
    raise SystemExit(main())
