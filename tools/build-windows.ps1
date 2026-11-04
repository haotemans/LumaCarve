# Build the unsigned Windows NSIS installer locally, without a Windows Actions runner.
# Requires Windows, Python 3.11, Node.js 22, Rust/MSVC, and Tauri prerequisites.
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$RefreshDependencies
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'This installer must be built on Windows.'
}
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python = Join-Path $root '.venv\Scripts\python.exe'
$npm = (Get-Command 'npm.cmd' -ErrorAction Stop).Source
$null = Get-Command 'cargo.exe' -ErrorAction Stop

function Assert-Success([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$step failed with exit code $LASTEXITCODE"
    }
}

$needsPythonDeps = $RefreshDependencies
if (-not (Test-Path $python)) {
    $launcher = (Get-Command 'py.exe' -ErrorAction Stop).Source
    & $launcher -3.11 -m venv (Join-Path $root '.venv')
    Assert-Success 'Create Python 3.11 virtual environment'
    $needsPythonDeps = $true
}
if (-not $needsPythonDeps) {
    & $python -c "import importlib.util as u,sys; sys.exit(0 if all(u.find_spec(m) for m in ('PyInstaller','lumacarve_server','PIL','httpx')) else 1)"
    $needsPythonDeps = ($LASTEXITCODE -ne 0)
}
if ($needsPythonDeps) {
    & $python -m pip install --disable-pip-version-check -e ($backend + '[dev]') pyinstaller
    Assert-Success 'Install Python packaging and test dependencies'
}

if (-not $SkipTests) {
    & $python -m unittest discover -s (Join-Path $backend 'tests') -v
    Assert-Success 'Backend tests'
    & cargo.exe test --manifest-path (Join-Path $root 'scheduler\Cargo.toml') --all-targets
    Assert-Success 'Rust scheduler tests'
}

& $python (Join-Path $root 'tools\generate-desktop-icons.py')
Assert-Success 'Generate desktop icons'
& $python (Join-Path $root 'tools\build-sidecar.py') --target x86_64-pc-windows-msvc
Assert-Success 'Build Windows API sidecar'

Push-Location $frontend
try {
    if ($RefreshDependencies -or -not (Test-Path (Join-Path $frontend 'node_modules'))) {
        & $npm install --no-audit --no-fund --prefer-offline
        Assert-Success 'Install frontend dependencies'
    }
    if (-not $SkipTests) {
        & $npm run test
        Assert-Success 'Frontend tests'
    }
    # Tauri invokes 'npm run build' through beforeBuildCommand; do not build twice.
    & $npm run desktop:build -- --config src-tauri/tauri.windows.conf.json
    Assert-Success 'Build Windows NSIS installer'
}
finally {
    Pop-Location
}

$nsisDir = Join-Path $frontend 'src-tauri\target\release\bundle\nsis'
$installer = Get-ChildItem -Path $nsisDir -Filter '*.exe' -File -ErrorAction Stop |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if ($null -eq $installer) {
    throw 'Tauri finished without producing an NSIS .exe installer.'
}
$signature = Get-AuthenticodeSignature -FilePath $installer.FullName
if ($signature.Status -ne 'NotSigned') {
    throw "Expected unsigned preview; installer signature status: $($signature.Status)"
}
$hash = (Get-FileHash -Path $installer.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "Windows installer: $($installer.FullName)"
Write-Host "SHA256: $hash"
