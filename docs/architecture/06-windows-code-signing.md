# Windows preview packaging and future Authenticode signing

## Current state: unsigned preview (no paid certificate)

LumaCarve's actual Tauri application lives under `frontend/src-tauri`.
The shared base `tauri.conf.json` continues to bundle Windows NSIS and Linux
DEB/AppImage. The Windows-specific overlay `tauri.windows.conf.json` selects
only NSIS for preview builds without affecting Linux builds.

Run GitHub Actions **Windows unsigned preview** via **Actions > Run workflow**
on the `main` branch after the change is merged. The workflow:

1. Uses a Windows x64 runner with Python 3.11, Node 22 and Rust MSVC.
2. Installs only the minimal FastAPI/PyInstaller backend dependencies.
3. Builds `lumacarve-api-x86_64-pc-windows-msvc.exe` with the existing
   `tools/build-sidecar.py`, then bundles it through Tauri 2.
4. Builds the NSIS setup executable with no Authenticode signing certificate.
5. Fails if the resulting installer is unexpectedly signed, writes
   `SHA256SUMS.txt`, and uploads both as a short-lived Actions artifact.

The Windows installer may trigger SmartScreen or be blocked by Smart App
Control. Never tell testers to disable operating-system security protections.
This workflow does not push to GitHub Releases, and its artifact is not a
trusted or production-signed installer.

### Local Windows build (PowerShell, repository root)

```powershell
py -3.11 -m pip install -e ./backend pyinstaller
py -3.11 tools/generate-desktop-icons.py
py -3.11 tools/build-sidecar.py --target x86_64-pc-windows-msvc
cd frontend
npm.cmd install --no-audit --no-fund
npm.cmd run desktop:build -- --config src-tauri/tauri.windows.conf.json
```

Installer output: `frontend/src-tauri/target/release/bundle/nsis/`.
This is a **core API-only** desktop bundle: no CUDA, PyTorch, training Worker or
model weights are included. Model inference must not be advertised as included.

### Before a production release

- Obtain an Authenticode code-signing certificate or enroll in Microsoft
  Artifact Signing. A self-signed certificate is not generally trusted on
  other Windows machines.
- Add a **separate, production-only** config overlay, e.g.
  `frontend/src-tauri/tauri.windows.signed.conf.json`, supplying either the
  issuer-approved signing method with `bundle.windows.signCommand` or a
  certificate thumbprint supported by the installed signing tool.
- Do not add certificate material, passwords, tokens or private keys to Git;
  use restricted CI secrets and protected release environments.
- In production CI, use the signed overlay and require
  `Get-AuthenticodeSignature` to report `Valid` for installer deliverables;
  fail closed if the certificate or signing service is unavailable.
- Keep the same Tauri application identifier and do not confuse Authenticode
  signing with the separate Tauri Updater Ed25519 signing mechanism.
- Validate signed deliverables on a fresh Windows installation, and publish
  hashes and versioned release notes.
- Code signing does not guarantee that Microsoft SmartScreen immediately
  stops displaying reputation warnings.

Tauri reference: https://v2.tauri.app/distribute/sign/windows/
