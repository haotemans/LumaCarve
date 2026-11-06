# CI and portable desktop build workflow

## Portable-only distribution policy

- **Windows x64:** Build **only** `LumaCarve-Windows-x64-Portable.zip` via GitHub Actions Windows 2022 runners or locally. Extract fully to a writable directory, then run `LumaCarve.exe`. The ZIP contains `lumacarve-api.exe`, `portable.flag`, and `README.txt`; it contains **no NSIS installer**. `.exe` is still the Windows application executable; avoiding a Windows `.exe` *altogether* is not supported by this native desktop architecture.
- **Linux x64:** Dispatch **only** the `.AppImage` build via GitHub Actions. A standalone AppImage does not require `.deb` installation. Make it executable, then run it.
- Historical installer releases and tags are preserved. Legacy installer publishing workflows have no active triggers.
- Neither portable build bundles PyTorch, CUDA/Triton, Anima weights, or a ready-to-use GPU Worker. GPU inference and training must not be advertised as available.
- Windows requires Microsoft Edge WebView2 Runtime. Both platforms depend on compatible OS libraries; unsigned binaries may be blocked or warned about by the operating system.

## Windows local build

Prerequisites: Windows x64, Python 3.11 (`py.exe`), Node.js 22, Rust MSVC, Microsoft C++ Build Tools, and Tauri 2 prerequisites.

From repository root:

```powershell
.\tools\build-windows.ps1
```

Reuses `.venv` and `frontend/node_modules`, runs Python, Rust and Vue tests, freezes the API sidecar, and builds Tauri with `--no-bundle`. Then constructs and verifies the ZIP and writes `dist/SHA256SUMS.txt`.

```powershell
.\tools\build-windows.ps1 -RefreshDependencies
.\tools\build-windows.ps1 -SkipTests
```

`-SkipTests` is for local exploration, not verified distribution. The script invokes `npm.cmd` rather than `npm.ps1` to avoid Windows PowerShell execution policy failures. Local builds are not automatically published; CI-built, tested ZIPs can be attached to the portable GitHub prerelease.

Portable data: `portable.flag` next to the main executable selects `LumaCarveData/workspace` and `LumaCarveData/logs` beneath the extraction directory. **Keep the folder writable**. This mode does not migrate previously installed user data; backup/move old data explicitly before changing directories. Never launch an executable directly from inside the ZIP.

## Linux GitHub Actions AppImage

After committing changes to the desired branch, dispatch manually:

```powershell
gh workflow run tauri-desktop.yml --repo haotemans/LumaCarve --ref main
gh run list --repo haotemans/LumaCarve --workflow tauri-desktop.yml --branch main --limit 5
gh run view <run-id> --repo haotemans/LumaCarve --json headSha,headBranch,event,status,conclusion,url
gh run watch <run-id> --repo haotemans/LumaCarve --compact --interval 60 --exit-status
gh run download <run-id> --repo haotemans/LumaCarve --name LumaCarve-Linux-x64-Portable-AppImage --dir .\dist\linux
```

AppImage builds are not automatic on PR or push. Verify the run SHA, result, artifact, and checksum before publishing. `APPIMAGE` points at the original outer AppImage path, so the portable workspace is stored next to that file (not in the temporary mount). The directory must be writable. AppImage requires host runtime compatibility (including potential FUSE support). GitHub Actions artifact retention is seven days.

## Release rules

1. Distribute **only** the Windows portable ZIP and Linux AppImage, plus SHA-256 checksum manifest. Do not upload `*.deb`, `*.msi`, or NSIS installer `*.exe` assets for new releases.
2. Require successful build verification on the corresponding OS and inspect the application + sidecar startup before declaring a working portable release.
3. Keep historical releases untouched. Do not silently replace assets attached to existing release tags.
4. Windows x64 is built on GitHub Actions **Windows 2022** runner (or locally on Windows); Linux remains on Ubuntu. Both OS-specific binaries must be compiled and verified on their own platform.
5. Maintain code, Markdown and tests together; inspect status/diff, preserve unrelated changes, commit related work, and inspect exact GitHub CI SHA and status. Queued CI is not a pass.

## One-off Linux portable prerelease

The first portable Linux prerelease is driven by a new `docs/releases/v0.2.2-portable.md` file. When that file is merged into `main`, the existing Linux AppImage workflow runs once and attempts to publish tag `v0.2.2-portable-preview.1` **only after** compilation, tests, checksum verification, and AppImage extraction inspection pass. The tag is immutable: an existing tag/release causes failure rather than replacement. Normal manual `workflow_dispatch` builds do **not** publish a release.

The Windows CI is initiated only after the Linux release workflow succeeds on a main-branch push. It checks out the **same commit**, runs `tools/build-windows.ps1`, verifies a portable ZIP and launches the extracted GUI/API in a smoke test, then adds the ZIP and `SHA256SUMS-Windows.txt` to the **same prerelease**. Neither workflow publishes NSIS, MSI or DEB. Manual workflow dispatches build artifacts without updating Releases.

## Windows Actions build and release

Workflow: `.github/workflows/windows-portable.yml`, runner: `windows-2022`, toolchains: Python 3.11, Node.js 22, Rust MSVC. A successful, main-branch Linux portable release run triggers the Windows build once via `workflow_run`. The Windows job checks out the producer's `head_sha`, runs Python/Rust/JavaScript checks, packages the ZIP without installers, verifies its checksum and the extracted app + API sidecar. Only the release tag that points to that **same commit SHA** may receive the new Windows artifacts; existing file names are never overwritten. You can manually dispatch the Windows workflow for build-only diagnostic artifacts without publishing.

Windows smoke tests require the app to stay alive, create an adjacent workspace and start the bundled API sidecar. This is an automated runner smoke test, not proof of successful GPU generation or full user acceptance testing.
