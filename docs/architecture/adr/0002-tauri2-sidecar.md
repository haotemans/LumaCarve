# ADR 0002 · Tauri 2 with a lightweight FastAPI sidecar

Status: Accepted (2026-11-03); portable distribution update 2026-11-07.

## Current architecture

The shared Vue 3 WebUI is hosted by Tauri 2. The Rust host launches a bundled FastAPI sidecar with a random loopback port and a fresh 256-bit token. WebView code receives the connection through a dedicated Tauri command; no broad shell permissions are exposed.

## Portable-only distribution

- Windows x64: a ZIP built by GitHub Actions Windows 2022; fully extract to a writable directory and start the main LumaCarve.exe. The internal lumacarve-api.exe is not user-launched. portable.flag selects adjacent LumaCarveData/workspace and logs.
- Linux x64: AppImage built on Ubuntu Actions; the outer APPIMAGE path selects adjacent LumaCarveData. New releases do not include NSIS, MSI or DEB installer assets; legacy releases remain archived.
- The sidecar expects an absolute workspace path, localhost port and random session token from Tauri. A direct launch is unsupported. No automatic migration from old installer app-data is performed.

## Verification and limitations

Windows CI checks extracted GUI process startup, packaged API health with a token and rejected unauthenticated requests. These are automated smoke tests, **not** full real-device GUI verification. The published portable archive does not include PyTorch, CUDA, Triton, a model checkpoint or a GPU Worker. A responsive API is not evidence of available Anima GPU inference or LoRA training.

Anima adapter code and CPU mock tests exist, but actual GPU inference is not yet verified. LoRA training and Qwen editing are not implemented. Future GPU distribution requires platform-specific installation, lifecycle management, functional smoke tests and validated model weights.

PyInstaller one-file launch may be slow; the WebView waits for authenticated health. API access logs and persisted session secrets are disabled. Ephemeral loopback URL query tokens remain pending a possible custom-protocol proxy.

References: [desktop module](../../../frontend/src-tauri/README.md) · [published release status](../../release-status.md) · [CI build policy](../../ci-build.md).
