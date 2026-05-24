# =============================================================================
# Sakura - launch the backend (no install, no build).
#
# Use this AFTER setup.ps1 has run at least once. It only:
#  1. Verifies the .venv exists.
#  2. Verifies the Angular bundle has been published to backend\static.
#  3. Starts backend\run_server.py via the venv Python.
#
# Re-run setup.ps1 instead if you changed code or dependencies.
# =============================================================================

$ErrorActionPreference = 'Stop'
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

function Log  { param($msg) Write-Host "[sakura] $msg" -ForegroundColor Cyan }
function Fail { param($msg) Write-Host "[sakura] $msg" -ForegroundColor Red; exit 1 }

$VenvPython = Join-Path $RootDir '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Fail "Virtualenv not found at .venv. Run setup.ps1 first."
}

$IndexHtml = Join-Path $RootDir 'backend\static\index.html'
if (-not (Test-Path $IndexHtml)) {
    Fail "Frontend bundle not found at backend\static\index.html. Run setup.ps1 first."
}

$hostBind = if ($env:HOST) { $env:HOST } else { '0.0.0.0' }
$portBind = if ($env:PORT) { $env:PORT } else { '5000' }
Log "Starting backend on ${hostBind}:${portBind}"
& $VenvPython backend\run_server.py
exit $LASTEXITCODE
