# CI and desktop build workflow (low traffic)

## Platform ownership

- **Windows x64:** Build and test on a local Windows machine using `tools/build-windows.ps1`. No Windows cloud runner is used for normal development or installer packaging.
- **Linux x64:** GitHub Actions runners build `.deb` and `.AppImage` packages. The `gh` CLI **only triggers, monitors and downloads** runs; it never compiles or executes the tests itself.
- **Fast CI:** Backend, frontend, layout and scheduler checks run on Linux for pull requests and pushes to `main`, filtered by changed paths. Unrelated feature-branch pushes do not duplicate PR checks.
- **Desktop packages:** The expensive Linux Tauri workflow runs **only** through `workflow_dispatch`. Merge/push alone does not package or publish a release.

## Windows local build

Prerequisites: Windows x64, Python 3.11 (`py.exe`), Node.js 22, Rust MSVC toolchain, Microsoft C++ Build Tools, WebView2 and the required [Tauri 2 Windows prerequisites](https://v2.tauri.app/start/prerequisites/).

From the repository root, in PowerShell:

```powershell
.\tools\build-windows.ps1
```

The script reuses the existing repository-root `.venv` and `frontend/node_modules` by default. It performs backend, Rust and frontend tests, builds the PyInstaller FastAPI sidecar, generates icons, and creates an unsigned NSIS installer. Tauri invokes the frontend production build once.

```powershell
.\tools\build-windows.ps1 -RefreshDependencies
.\tools\build-windows.ps1 -SkipTests
```

Use `-RefreshDependencies` after dependency changes and `-SkipTests` only for exploratory local builds. To avoid PowerShell's `npm.ps1` execution-policy issue, the script calls `npm.cmd`. The produced `.exe` and SHA256 hash are printed locally; Windows installers are **not** uploaded or published automatically. Treat `NotSigned` as expected for the unsigned test preview, not as a signature verification success.

## Linux GitHub Actions build via gh

Once a commit is pushed and merged into `main`, explicitly request a Linux desktop package:

```powershell
gh workflow run tauri-desktop.yml --repo haotemans/LumaCarve --ref main
gh run list --repo haotemans/LumaCarve --workflow tauri-desktop.yml --branch main --limit 5
gh run view <run-id> --repo haotemans/LumaCarve --json headSha,headBranch,event,status,conclusion,url
gh run watch <run-id> --repo haotemans/LumaCarve --compact --interval 60 --exit-status
gh run download <run-id> --repo haotemans/LumaCarve --name LumaCarve-Linux-deb-AppImage --dir .\dist\linux
```

Before reporting a result, verify the repository, branch and `headSha` correspond to the intended commit. The Actions page is authoritative for success, failure, or cancellation. Artifact retention is 7 days. This workflow does not create a GitHub Release.

## Agent git / CI rules

1. Inspect `.github/workflows/` once, and inspect again only after workflow changes.
2. Run local targeted tests where the current machine supports them. Never claim a Windows local build was executed on a Linux host.
3. Inspect `git status` and `git diff`, preserve unrelated changes, stage task-related files only, and commit completed changes without prompting again.
4. Batch related commits before one push. For a new commit, identify only runs tied to that repository, branch and SHA; check relevant required checks.
5. Avoid broad log downloads. Inspect failed jobs with `gh run view <run-id> --log-failed`; fix a deterministic failure before re-running.
6. Poll only when monitoring is necessary, at 60-second intervals with compact output. Queued or running CI is not a pass.
7. Use an existing pull request when one exists, or open a new PR. Merge only when the user explicitly authorized it and GitHub permits it; never force-push or bypass branch protection.
8. Report the change summary, commit, branch, push status, linked Actions run/status and PR/merge result. Report missing CI runs or environmental blockers truthfully.

Historical release publishing workflows are retained for existing tags and artifacts; they are not the new standard path for desktop packaging.
