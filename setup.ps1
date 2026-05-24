# =============================================================================
# Sakura - one-shot setup & launch script (Windows / PowerShell).
#
# What it does:
#  1. Verifies Python 3.10+ and Node 18+ are present.
#  2. Creates/refreshes a Python virtualenv at .venv and installs backend deps.
#  3. Installs frontend deps with npm ci (or npm install on first run).
#  4. Builds the Angular app in production mode (static, no SSR) and copies
#     the bundle to backend\static so Flask serves it on the same origin as
#     /api.
#  5. Materialises .env from .env.example with freshly generated secrets if no
#     .env exists yet.
#  6. Starts the backend via backend\run_server.py (Waitress under the hood).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1 -NoStart
# =============================================================================

[CmdletBinding()]
param(
    [switch]$NoStart,
    [switch]$SkipFrontendInstall
)

$ErrorActionPreference = 'Stop'
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

function Log     { param($msg) Write-Host "[sakura] $msg" -ForegroundColor Cyan }
function Warn    { param($msg) Write-Host "[sakura] $msg" -ForegroundColor Yellow }
function Fail    { param($msg) Write-Host "[sakura] $msg" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
# 1. Dependency checks
# ---------------------------------------------------------------------------
function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command python)) { Fail "Python 3.10+ is required but was not found in PATH." }
if (-not (Test-Command node))   { Fail "Node.js 18+ is required but was not found in PATH." }
if (-not (Test-Command npm))    { Fail "npm is required but was not found in PATH." }

# Resolve a concrete npm executable. On Windows npm ships as npm.cmd, and
# calling it through PowerShell's `&` operator with unquoted arguments has
# been observed to mangle args (e.g. `npm ci` -> npm receiving "pm"), so we
# always invoke the .cmd shim through cmd.exe to bypass PowerShell parsing.
$NpmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
if (-not $NpmCmd) { $NpmCmd = Get-Command npm -ErrorAction SilentlyContinue }
if (-not $NpmCmd) { Fail "Could not resolve npm executable." }
$NpmPath = $NpmCmd.Source

# Note: do not wrap `cmd /c npm ...` in a PowerShell function — PS captures
# every stdout line as a return value, which polluted $LASTEXITCODE checks.
# We invoke cmd /c directly and read $LASTEXITCODE in-place instead.

$pyVersion = (& python -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')") 2>$null
$pyParts = $pyVersion -split '\.'
if ([int]$pyParts[0] -lt 3 -or ([int]$pyParts[0] -eq 3 -and [int]$pyParts[1] -lt 10)) {
    Fail "Python 3.10+ required, found $pyVersion"
}

$nodeMajor = (& node -p "process.versions.node.split('.')[0]") 2>$null
if ([int]$nodeMajor -lt 18) {
    Fail "Node.js 18+ required, found $(node --version)"
}

# ---------------------------------------------------------------------------
# 2. Python virtualenv
# ---------------------------------------------------------------------------
$VenvDir = Join-Path $RootDir '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'

if (-not (Test-Path $VenvPython)) {
    Log "Creating Python virtualenv at .venv"
    # --upgrade-deps was added in Python 3.9 and makes the freshly created
    # venv ship with up-to-date pip/setuptools. If the flag isn't supported
    # we fall back to a plain `python -m venv` invocation.
    & python -m venv --upgrade-deps $VenvDir 2>$null
    if (($LASTEXITCODE -ne 0) -or (-not (Test-Path $VenvPython))) {
        & python -m venv $VenvDir
    }
    if (-not (Test-Path $VenvPython)) { Fail "Failed to create virtualenv at $VenvDir." }
}

# Some Python distributions (Microsoft Store builds, slimmed-down installs,
# distros without python3-venv on Linux) leave the venv without pip. Detect
# that and try to repair it via ensurepip, then get-pip.py from PyPA.
#
# Native-command stderr can be promoted to a terminating error under
# $ErrorActionPreference='Stop' on PS 7.3+, so every pip-check is wrapped
# in a try/catch with a per-call EAP override and we only trust $LASTEXITCODE.

function Test-VenvPip {
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $global:LASTEXITCODE = 0
    try {
        & $VenvPython -m pip --version *> $null
    } catch {
        $global:LASTEXITCODE = 1
    } finally {
        $ErrorActionPreference = $oldEap
    }
    return ($LASTEXITCODE -eq 0)
}

function Invoke-VenvBootstrap([string[]]$Args) {
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $global:LASTEXITCODE = 0
    try {
        & $VenvPython @Args
    } catch {
        # Swallow - we only judge success by $LASTEXITCODE / a follow-up probe.
    } finally {
        $ErrorActionPreference = $oldEap
    }
}

function Ensure-Pip {
    if (Test-VenvPip) { return }

    Warn "pip is missing from the venv; attempting to bootstrap it via ensurepip"
    Invoke-VenvBootstrap @('-m', 'ensurepip', '--upgrade', '--default-pip')
    if (Test-VenvPip) { return }

    Warn "ensurepip failed; downloading get-pip.py from https://bootstrap.pypa.io"
    $getPip = Join-Path $env:TEMP "sakura-get-pip.py"
    try {
        Invoke-WebRequest -UseBasicParsing -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile $getPip
    } catch {
        Fail "Could not download get-pip.py: $($_.Exception.Message)`nInstall pip manually with: $VenvPython -m ensurepip --upgrade"
    }
    Invoke-VenvBootstrap @($getPip)
    Remove-Item -Force $getPip -ErrorAction SilentlyContinue

    if (-not (Test-VenvPip)) { Fail "Bootstrapping pip into the venv failed." }
}

Ensure-Pip

Log "Installing backend Python dependencies"
& $VenvPython -m pip install --upgrade pip setuptools wheel | Out-Null
& $VenvPython -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { Fail "Failed to install backend dependencies." }

# ---------------------------------------------------------------------------
# 3. Frontend deps + build
# ---------------------------------------------------------------------------
Push-Location frontend
try {
    if (-not $SkipFrontendInstall) {
        # `.package-lock.json` is written by npm at the end of a successful
        # install. Using it as the sentinel avoids the "half-deleted
        # node_modules" trap where Test-Path 'node_modules' is still true.
        $installSentinel = Join-Path 'node_modules' '.package-lock.json'
        if ((Test-Path 'package-lock.json') -and (Test-Path $installSentinel)) {
            Log "Skipping npm install (node_modules already populated)"
        } else {
            if (Test-Path 'package-lock.json') {
                Log "Installing frontend npm dependencies (npm ci)"
                cmd /c "`"$NpmPath`" ci"
                if ($LASTEXITCODE -ne 0) {
                    Warn "npm ci failed (exit $LASTEXITCODE); falling back to npm install"
                    cmd /c "`"$NpmPath`" install"
                }
            } else {
                Log "Installing frontend npm dependencies (npm install)"
                cmd /c "`"$NpmPath`" install"
            }
            if ($LASTEXITCODE -ne 0) { Fail "npm install failed (exit $LASTEXITCODE)." }
        }
    }

    Log "Building Angular frontend (production, static SPA)"
    cmd /c "`"$NpmPath`" run build"
    if ($LASTEXITCODE -ne 0) { Fail "Angular build failed (exit $LASTEXITCODE)." }
} finally {
    Pop-Location
}

$StaticDir = Join-Path $RootDir 'backend\static'
Log "Publishing frontend bundle to backend\static"
if (Test-Path $StaticDir) { Remove-Item -Recurse -Force $StaticDir }
New-Item -ItemType Directory -Path $StaticDir | Out-Null
Copy-Item -Recurse -Force 'frontend\dist\frontend\browser\*' $StaticDir

$indexHtml    = Join-Path $StaticDir 'index.html'
$indexCsrHtml = Join-Path $StaticDir 'index.csr.html'
if ((-not (Test-Path $indexHtml)) -and (Test-Path $indexCsrHtml)) {
    Copy-Item $indexCsrHtml $indexHtml
}

# ---------------------------------------------------------------------------
# 4. .env bootstrap
# ---------------------------------------------------------------------------
$EnvFile    = Join-Path $RootDir '.env'
$EnvExample = Join-Path $RootDir '.env.example'

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Log "Creating .env from .env.example with freshly generated secrets"
        $jwt = (& $VenvPython -c "import secrets;print(secrets.token_urlsafe(48))").Trim()
        $enc = (& $VenvPython -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())").Trim()

        $content = Get-Content $EnvExample -Raw
        $content = $content -replace '(?m)^JWT_SECRET_KEY=.*$',  ("JWT_SECRET_KEY=" + $jwt)
        $content = $content -replace '(?m)^ENCRYPTION_KEY=.*$', ("ENCRYPTION_KEY=" + $enc)
        Set-Content -Path $EnvFile -Value $content -Encoding UTF8
    } else {
        Warn ".env.example missing; .env was not created"
    }
}

Log "Setup complete"

# ---------------------------------------------------------------------------
# 5. Launch
# ---------------------------------------------------------------------------
if (-not $NoStart) {
    $hostBind = if ($env:HOST) { $env:HOST } else { '0.0.0.0' }
    $portBind = if ($env:PORT) { $env:PORT } else { '5000' }
    Log "Starting backend on ${hostBind}:${portBind}"
    & $VenvPython backend\run_server.py
    exit $LASTEXITCODE
} else {
    Log "Skipping launch (-NoStart). Start manually with: .\.venv\Scripts\python.exe backend\run_server.py"
}
