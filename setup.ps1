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
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Interactive
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1 -NonInteractive -NoStart
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1 -AuditStrict
# =============================================================================

[CmdletBinding()]
param(
    [switch]$NoStart,
    [switch]$SkipFrontendInstall,
    [switch]$Interactive,
    [switch]$NonInteractive,
    # Corporate MITM proxies often present a self-signed cert. -InsecureSsl
    # tells pip to add bootstrap-pypa hosts to --trusted-host and tells npm
    # to disable strict-ssl + Node TLS verification for this run.
    [switch]$InsecureSsl,
    # Force a clean frontend build by wiping frontend\dist and the Angular
    # CLI cache before invoking ng build. Useful when the previous build
    # used a different angular.json (SSR vs SPA).
    [switch]$CleanBuild,
    [switch]$SkipAudit,
    [switch]$AuditStrict
)

$ErrorActionPreference = 'Stop'
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

function Log     { param($msg) Write-Host "[sakura] $msg" -ForegroundColor Cyan }
function Warn    { param($msg) Write-Host "[sakura] $msg" -ForegroundColor Yellow }
function Fail    { param($msg) Write-Host "[sakura] $msg" -ForegroundColor Red; exit 1 }

function Read-YesNoBootstrap {
    param([string]$Prompt, [bool]$Default = $true)
    $hint = if ($Default) { "Y/n" } else { "y/N" }
    $raw = Read-Host "$Prompt [$hint]"
    if ([string]::IsNullOrWhiteSpace($raw)) { return $Default }
    return $raw -match '^[yY]'
}

# ---------------------------------------------------------------------------
# 0d. Interactive configuration wizard
# ---------------------------------------------------------------------------
$EnvFile = Join-Path $RootDir '.env'
$WizardCfg = $null
$RunWizard = $Interactive
if (-not $NonInteractive -and -not $RunWizard -and -not (Test-Path $EnvFile)) {
    $RunWizard = Read-YesNoBootstrap "No .env found. Run interactive setup wizard?" $true
}

if ($RunWizard) {
    . (Join-Path $RootDir 'scripts\setup-wizard.ps1')
    $WizardCfg = Invoke-SakuraSetupWizard -PythonExe $(if (Test-Path (Join-Path $RootDir '.venv\Scripts\python.exe')) { (Join-Path $RootDir '.venv\Scripts\python.exe') } else { 'python' })
    if ($null -eq $WizardCfg) { exit 0 }
    Write-SakuraEnvFile -Path $EnvFile -Lines $WizardCfg.EnvLines
    foreach ($line in $WizardCfg.EnvLines) {
        if ($line -match '^([^=+#][^=]*)=(.*)$') {
            Set-Item -Path "env:$($Matches[1].Trim())" -Value $Matches[2].Trim()
        }
    }
    if ($WizardCfg.DockerMode) {
        Log "Docker LAN mode selected — building stack via docker compose"
        $tlsScript = Join-Path $RootDir 'deploy\lan\scripts\generate-tls.ps1'
        if (Test-Path $tlsScript) { & $tlsScript $WizardCfg.LanIp }
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
            Fail "Docker is required for LAN deployment but was not found in PATH."
        }
        $profileArgs = @()
        foreach ($p in $WizardCfg.ComposeProfiles) { $profileArgs += @('--profile', $p) }
        docker compose @profileArgs up -d --build
        if ($LASTEXITCODE -ne 0) { Fail "docker compose failed (exit $LASTEXITCODE)" }
        Log "Deployment complete: https://$($WizardCfg.LanIp)/"
        exit 0
    }
}

# ---------------------------------------------------------------------------
# 0. Corporate proxy detection
# ---------------------------------------------------------------------------
# pip and npm both honour HTTP_PROXY / HTTPS_PROXY / NO_PROXY env vars when
# present, but they expect specific casing depending on the tool/platform. We
# normalise whichever the user has set and re-export BOTH the upper- and
# lower-case variants so every child process picks them up consistently.
function Mask-ProxyUrl([string]$url) {
    if (-not $url) { return '' }
    return ($url -replace '(://)([^:@/]+):([^@/]+)@', '$1***:***@')
}

$HttpsProxy = if ($env:HTTPS_PROXY) { $env:HTTPS_PROXY } else { $env:https_proxy }
$HttpProxy  = if ($env:HTTP_PROXY)  { $env:HTTP_PROXY }  else { $env:http_proxy }
$NoProxy    = if ($env:NO_PROXY)    { $env:NO_PROXY }    else { $env:no_proxy }

if ($HttpsProxy -or $HttpProxy) {
    Log "Detected corporate proxy:"
    if ($HttpsProxy) { Log "  HTTPS_PROXY = $(Mask-ProxyUrl $HttpsProxy)" }
    if ($HttpProxy)  { Log "  HTTP_PROXY  = $(Mask-ProxyUrl $HttpProxy)"  }
    if ($NoProxy)    { Log "  NO_PROXY    = $NoProxy" }

    if ($HttpsProxy) { $env:HTTPS_PROXY = $HttpsProxy; $env:https_proxy = $HttpsProxy }
    if ($HttpProxy)  { $env:HTTP_PROXY  = $HttpProxy;  $env:http_proxy  = $HttpProxy  }
    if ($NoProxy)    { $env:NO_PROXY    = $NoProxy;    $env:no_proxy    = $NoProxy    }
}

# ---------------------------------------------------------------------------
# 0b. Optional: SSL trust bypass for MITM proxies
# ---------------------------------------------------------------------------
$PipInsecureArgs = @()
if ($InsecureSsl) {
    Warn "-InsecureSsl enabled: skipping TLS verification for pip + npm (corporate MITM mode)"
    $PipInsecureArgs = @(
        '--trusted-host', 'pypi.org',
        '--trusted-host', 'pypi.python.org',
        '--trusted-host', 'files.pythonhosted.org',
        '--trusted-host', 'bootstrap.pypa.io'
    )
    $env:NODE_TLS_REJECT_UNAUTHORIZED = '0'
    $env:NPM_CONFIG_STRICT_SSL = 'false'
}

# ---------------------------------------------------------------------------
# 0c. Port preflight (non-fatal)
# ---------------------------------------------------------------------------
$portToCheck = if ($env:PORT) { [int]$env:PORT } else { 5000 }
try {
    $bound = Get-NetTCPConnection -State Listen -LocalPort $portToCheck -ErrorAction SilentlyContinue
    if ($bound) {
        $owners = $bound | ForEach-Object { (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName } | Sort-Object -Unique
        Warn "Port $portToCheck is already in use by: $(($owners -join ', '))"
        Warn "  -> The backend will fail to bind. Stop the other process or set `$env:PORT to a free port."
    }
} catch {
    # Get-NetTCPConnection may not be available on very old Windows; skip silently.
}

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
    $iwrArgs = @{ Uri = 'https://bootstrap.pypa.io/get-pip.py'; OutFile = $getPip; UseBasicParsing = $true }
    if ($HttpsProxy) { $iwrArgs['Proxy'] = $HttpsProxy }
    try {
        Invoke-WebRequest @iwrArgs
    } catch {
        Fail "Could not download get-pip.py: $($_.Exception.Message)`nInstall pip manually with: $VenvPython -m ensurepip --upgrade"
    }
    Invoke-VenvBootstrap @($getPip)
    Remove-Item -Force $getPip -ErrorAction SilentlyContinue

    if (-not (Test-VenvPip)) { Fail "Bootstrapping pip into the venv failed." }
}

Ensure-Pip

Log "Installing backend Python dependencies"
$PipProxyArgs = @()
if ($HttpsProxy) { $PipProxyArgs += @('--proxy', $HttpsProxy) }
elseif ($HttpProxy) { $PipProxyArgs += @('--proxy', $HttpProxy) }
$PipAllArgs = $PipProxyArgs + $PipInsecureArgs

& $VenvPython -m pip @PipAllArgs install --upgrade pip setuptools wheel | Out-Null
& $VenvPython -m pip @PipAllArgs install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) {
    # Common failure on machines whose Python version has no prebuilt wheel
    # for one of the pinned packages (e.g. psycopg2-binary or cryptography on
    # a brand-new Python release). Retry with --prefer-binary so pip skips
    # source builds, and as a last resort install one package at a time so
    # the offender is named explicitly.
    Warn "Initial pip install failed; retrying with --prefer-binary"
    & $VenvPython -m pip @PipAllArgs install --prefer-binary --upgrade -r backend\requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Warn "Bulk install still failing; trying package-by-package to surface the culprit"
        $reqLines = Get-Content backend\requirements.txt | Where-Object {
            $_ -and (-not $_.StartsWith('#'))
        }
        $failed = @()
        foreach ($line in $reqLines) {
            $pkg = $line.Trim()
            if (-not $pkg) { continue }
            & $VenvPython -m pip @PipAllArgs install --prefer-binary $pkg
            if ($LASTEXITCODE -ne 0) { $failed += $pkg }
        }
        if ($failed.Count -gt 0) {
            Fail ("Failed to install: {0}`nLikely cause: your Python ({1}) has no prebuilt wheel for one of these packages.`nFix options:`n  * Install Python 3.10/3.11/3.12 alongside the current one and re-run setup.ps1 with that interpreter on PATH.`n  * Edit backend\requirements.txt to drop the lower bound on the failing package (e.g. cryptography>=X)." -f ($failed -join ', '), $pyVersion)
        }
    }
}

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

    if ($CleanBuild) {
        Log "Cleaning previous Angular build artefacts (dist + .angular\cache)"
        if (Test-Path 'dist')              { Remove-Item -Recurse -Force 'dist' -ErrorAction SilentlyContinue }
        if (Test-Path '.angular\cache')    { Remove-Item -Recurse -Force '.angular\cache' -ErrorAction SilentlyContinue }
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
# 4. .env bootstrap (non-interactive fallback)
# ---------------------------------------------------------------------------
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
# 4a. Dependency audit (target system)
# ---------------------------------------------------------------------------
if (-not $SkipAudit) {
    Log "Running dependency audit (pip + npm) — reports/security/"
    $auditScript = Join-Path $RootDir 'scripts\security\audit-dependencies.ps1'
    if (Test-Path $auditScript) {
        $auditArgs = @{
            RootDir     = $RootDir
            VenvPython  = $VenvPython
            Strict      = $AuditStrict
        }
        & $auditScript @auditArgs
        if ($LASTEXITCODE -ne 0 -and $AuditStrict) {
            Fail "Dependency audit failed (-AuditStrict). See reports\security\"
        }
    } else {
        Warn "Audit script not found at $auditScript"
    }
}

# ---------------------------------------------------------------------------
# 4b. Optional runtime deps (Smart Import + local VLM)
# ---------------------------------------------------------------------------
# The Smart Import wizard's hybrid parser uses LibreOffice (soffice) + Poppler
# (pdftoppm) to render Excel/Word pages into PNG snapshots for the VLM. The
# in-app assistant talks to a local Ollama daemon. Both are OPTIONAL - when
# missing, parsing falls back to deterministic-only and the assistant
# degrades gracefully - but probing here lets the operator know what they're
# giving up.
$sofficeFound = (Test-Command soffice) -or `
                (Test-Path "C:\Program Files\LibreOffice\program\soffice.exe") -or `
                (Test-Path "C:\Program Files (x86)\LibreOffice\program\soffice.exe")
if (-not $sofficeFound) {
    Warn "LibreOffice ('soffice') not found - Smart Import will run without page snapshots."
    Warn "  Install: https://www.libreoffice.org/download/download/ or 'winget install TheDocumentFoundation.LibreOffice'"
}
if (-not (Test-Command pdftoppm)) {
    Warn "Poppler ('pdftoppm') not on PATH - needed alongside LibreOffice for visual previews."
    Warn "  Install: 'winget install oschwartz10612.Poppler' or https://github.com/oschwartz10612/poppler-windows/releases/"
}
$bundledOllama = Join-Path $RootDir 'backend\resources\ollama\ollama.exe'
if (-not (Test-Command ollama) -and -not (Test-Path $bundledOllama)) {
    Warn "Ollama not detected - in-app assistant VLM features will be unavailable."
    Warn "  Install from https://ollama.com/download/windows, then pre-pull a model:"
    Warn "    ollama pull qwen2.5vl:7b"
    Warn "  Or vendor the binary + blobs for offline use via:"
    Warn "    pwsh backend\scripts\prepare_ollama_resources.ps1"
}

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
