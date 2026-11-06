# Build a portable Windows ZIP on Windows (local workstation or GitHub Actions runner).
# Requires Windows, Python 3.11, Node.js 22, Rust/MSVC, and Tauri prerequisites.
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$RefreshDependencies
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'Windows portable packages must be built on Windows.'
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
    $pythonHost = (Get-Command 'python.exe' -ErrorAction Stop).Source
    & $pythonHost -m venv (Join-Path $root '.venv')
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
    & $npm run desktop:build -- --config src-tauri/tauri.windows.conf.json --no-bundle
    Assert-Success 'Build portable Windows desktop binary'
}
finally {
    Pop-Location
}

$releaseDir = Join-Path $frontend 'src-tauri\target\release'
$appExe = Join-Path $releaseDir 'lumacarve-desktop.exe'
$sidecarExe = Join-Path $frontend 'src-tauri\binaries\lumacarve-api-x86_64-pc-windows-msvc.exe'
foreach ($file in @($appExe, $sidecarExe)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "Portable build missing required executable: $file"
    }
}
$dist = Join-Path $root 'dist'
$staging = Join-Path $dist 'LumaCarve-Windows-x64-Portable'
$archive = Join-Path $dist 'LumaCarve-Windows-x64-Portable.zip'
New-Item -ItemType Directory -Path $dist -Force | Out-Null
if (Test-Path $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging -Force | Out-Null
Copy-Item -LiteralPath $appExe -Destination (Join-Path $staging 'LumaCarve.exe')
Copy-Item -LiteralPath $sidecarExe -Destination (Join-Path $staging 'lumacarve-api.exe')
New-Item -ItemType File -Path (Join-Path $staging 'portable.flag') -Force | Out-Null
@'
LumaCarve Windows Portable

Extract the entire ZIP to a writable directory and run LumaCarve.exe.
Keep lumacarve-api.exe and portable.flag beside LumaCarve.exe.
User data is stored under LumaCarveData in the same directory.
Do not run directly from inside the ZIP.
Requires Windows WebView2 Runtime. Basic desktop UI/API only:
PyTorch, CUDA, Triton, Anima model weights and GPU workers are NOT included.
This unsigned build may trigger Windows SmartScreen.
'@ | Set-Content -Path (Join-Path $staging 'README.txt') -Encoding utf8
if (Test-Path $archive) { Remove-Item -LiteralPath $archive -Force }
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $archive -CompressionLevel Optimal
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($archive)
try {
    $files = @($zip.Entries | Where-Object { $_.Name })
    foreach ($required in @('LumaCarve.exe', 'lumacarve-api.exe', 'portable.flag', 'README.txt')) {
        if (-not ($files | Where-Object { $_.FullName -eq $required })) {
            throw "Portable archive missing $required"
        }
    }
}
finally {
    $zip.Dispose()
}
$hash = (Get-FileHash -Path $archive -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum = Join-Path $dist 'SHA256SUMS.txt'
"$hash  $(Split-Path $archive -Leaf)" | Set-Content -Path $checksum -Encoding ascii
Write-Host "Windows portable archive: $archive"
Write-Host "SHA256: $hash"
Write-Host 'This ZIP is portable and contains no installer.'
