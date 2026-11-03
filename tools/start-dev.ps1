# LumaCarve local-only development launcher (Windows PowerShell 5.1+).
# Uses npm.cmd explicitly to avoid the npm.ps1 ExecutionPolicy error.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$frontend = Join-Path $root 'frontend'
$backend = Join-Path $root 'backend'

if (-not (Test-Path $python)) {
    throw "Missing shared virtual environment at $python. Run: py -3.11 tools/setup.py"
}
if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    throw "Missing frontend dependencies. Run: cd frontend; npm.cmd install"
}
$npm = (Get-Command 'npm.cmd' -ErrorAction Stop).Source
$env:LUMACARVE_DATA_DIR = Join-Path $root 'LumaCarveData'
if (-not $env:LUMACARVE_INFERENCE_BACKEND) {
    $env:LUMACARVE_INFERENCE_BACKEND = 'disabled'
}

Write-Host 'LumaCarve | API http://127.0.0.1:8000 | Web http://127.0.0.1:5173/#/studio'
$server = Start-Process -FilePath $python -ArgumentList @(
    '-m', 'uvicorn', 'lumacarve_server.app:app', '--app-dir', $backend,
    '--host', '127.0.0.1', '--port', '8000'
) -PassThru -NoNewWindow
try {
    Push-Location $frontend
    try { & $npm run dev -- --host 127.0.0.1 }
    finally { Pop-Location }
} finally {
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue }
}
