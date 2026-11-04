# LumaCarve Desktop · Tauri 2

Vue 3 and Tauri 2 share one frontend for Windows and Linux. The native Rust shell starts/stops an embedded PyInstaller FastAPI core sidecar and supplies a random loopback port and per-launch session token. The webview cannot spawn arbitrary processes.

All mutable data lives under the OS Tauri app data directory in one workspace root (models, datasets, outputs, assets, SQLite); API logs are in its sibling logs directory.

This **core desktop bundle does not contain PyTorch, CUDA, Triton or Anima weights**. Full GPU inference requires a later separately managed worker installation. No fake GPU capabilities are claimed.

## Local build

Install Python 3.11, Node 22, Rust and native Tauri system packages:

```sh
python -m pip install -e ./backend pyinstaller
python tools/generate-desktop-icons.py
python tools/build-sidecar.py
cd frontend
npm install
npm run desktop:build
```

For normal development, Windows NSIS installers are built and tested locally with `..\\..\\tools\\build-windows.ps1` (from the repository root use `.\\tools\\build-windows.ps1`). Linux `.deb`/`.AppImage` installers are built only when `gh` dispatches the Linux GitHub Actions workflow. The CLI does not run the build itself. See [CI and local builds](../../docs/ci-build.md).

See `docs/architecture/adr/0002-tauri2-sidecar.md`.
