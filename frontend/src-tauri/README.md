# LumaCarve Desktop · Tauri 2 (portable only)

Tauri 2 hosts the Vue 3 application and starts/stops its bundled lightweight FastAPI sidecar. Its session token and local loopback port are created at each launch.

- Windows: a ZIP containing `LumaCarve.exe`, `lumacarve-api.exe`, `portable.flag`, and `README.txt`. Extract all files, then run `LumaCarve.exe`. The ZIP is **not an installer**.
- Linux: an AppImage built by the manually dispatched `.github/workflows/tauri-desktop.yml` workflow. Do not build DEB or NSIS installer artifacts for new releases.
- Portable mutable files are stored beside the app under `LumaCarveData/workspace`; logs under `LumaCarveData/logs`. Windows uses the marker; Linux AppImage uses the outer `APPIMAGE` location. You must place the executable in a writable directory.
- The Windows launch executable necessarily has an `.exe` suffix; the prohibition applies to **installer packages**, not to the app executable.
- Windows requires WebView2 Runtime; Linux requires a compatible AppImage runtime environment.
- The lightweight desktop core **does not contain PyTorch, CUDA, Triton, GPU Worker, or Anima weights**. Training and actual GPU generation are not bundled and remain unverified.

Build Windows locally via `.\tools\build-windows.ps1` from the repo root and Linux AppImage through the manual Actions workflow. See [CI and portable builds](../../docs/ci-build.md), [Tauri architecture](../../docs/architecture/adr/0002-tauri2-sidecar.md).
