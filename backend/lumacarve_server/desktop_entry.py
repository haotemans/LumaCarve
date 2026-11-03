"""Entrypoint for the bundled Tauri 2 FastAPI sidecar (core API only).

PyInstaller freezes the lightweight FastAPI/Pillow service; heavyweight
PyTorch/CUDA/Triton inference is not bundled in this first desktop installer.
The OS app-data directory is selected by the Tauri host, never by cwd.
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path


def main() -> int:
    root = Path(os.environ.get("LUMACARVE_DATA_DIR", "")).expanduser()
    if not root.is_absolute():
        raise RuntimeError("Desktop sidecar requires an absolute LUMACARVE_DATA_DIR")
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
