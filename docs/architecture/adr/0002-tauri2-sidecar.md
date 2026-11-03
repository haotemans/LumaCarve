# ADR 0002 · Tauri 2 and lightweight FastAPI sidecar

Status: Accepted (2026-11-03).

Tauri 2 wraps the existing Vue 3 application. Its Rust host starts a locally bundled FastAPI core process with a random loopback port and a fresh 256-bit session token. Webview code only receives connection information through a dedicated Tauri command; no broad shell permissions.

User data belongs in one per-user app-data workspace. The application installer is separate because managed OS application directories are normally not writable.

The initial installer deliberately excludes heavyweight PyTorch/CUDA/Triton and Anima model weights. Bundling all GPU stacks is unsafe across driver, GPU and Python ABI combinations and would be very large. Full GPU worker distribution remains future work.

PyInstaller one-file startup can take time; desktop initialization waits for backend health. Access logs are disabled, secrets never persisted. Image URLs use ephemeral loopback-token query strings until a future custom protocol proxy can remove them.

CI builds native Windows and Linux unsigned installers on respective runners, uploaded as Actions artifacts; no assumption of local cross-compilation.
