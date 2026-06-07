# =============================================================================
# Sakura LAN Deployment (Windows)
#
# Brings up the unified single-image stack (Flask backend + bundled Angular
# SPA on the same port) so other machines on the LAN can reach Sakura at
# http://<lan-ip>:5000/.
#
# Differences vs. the old split-image deployment:
#   * No separate Nginx container - Flask serves the SPA itself.
#   * No port 80 hop - single listener on PORT (default 5000).
#   * No Postgres profile - local-only SQLite is the only supported mode.
# =============================================================================

$ErrorActionPreference = "Stop"
Write-Host "--- Sakura LAN Deployment (Windows) ---" -ForegroundColor Cyan

# 1. Dependency probes
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker Desktop is required and was not found in PATH."
    exit 1
}
try {
    cmd /c "docker info >nul 2>nul"
    if ($LASTEXITCODE -ne 0) { throw "Docker daemon is not responding." }
} catch {
    Write-Error "Docker Desktop is not running. Start Docker Desktop and retry."
    exit 1
}

$composeCommand = @("docker", "compose")
docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $composeCommand = @("docker-compose")
    } else {
        Write-Error "Docker Compose plugin or docker-compose v1 is required."
        exit 1
    }
}

# 2. LAN IP detection
$localIp = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -notlike '169.254.*' -and
        $_.IPAddress -ne '127.0.0.1' -and
        $_.InterfaceAlias -notmatch 'vEthernet|Loopback' -and
        $_.PrefixOrigin -ne 'WellKnown'
    } |
    Sort-Object -Property InterfaceMetric |
    Select-Object -First 1).IPAddress
if (!$localIp) { $localIp = 'localhost' }

$portBind = if ($env:PORT) { $env:PORT } else { '5000' }
Write-Host "[info] Detected LAN IP : $localIp"     -ForegroundColor Gray
Write-Host "[info] Host port       : $portBind"    -ForegroundColor Gray

# 3. .env bootstrap with freshly generated secrets
if (!(Test-Path .env)) {
    Write-Host "[info] Generating secure keys + .env ..." -ForegroundColor Gray

    if (Get-Command python -ErrorAction SilentlyContinue) {
        $jwtSecret     = (python -c "import secrets;print(secrets.token_urlsafe(48))").Trim()
        $encryptionKey = (python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())").Trim()
    } else {
        $jwtSecret     = [Convert]::ToBase64String((1..48 | ForEach-Object { [byte](Get-Random -Minimum 0 -Maximum 255) }))
        $bytes         = (1..32 | ForEach-Object { [byte](Get-Random -Minimum 0 -Maximum 255) })
        $encryptionKey = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_') + "="
    }

    $envLines = @(
        "ENVIRONMENT=production"
        "FLASK_ENV=production"
        "HOST=0.0.0.0"
        "PORT=$portBind"
        "JWT_SECRET_KEY=$jwtSecret"
        "ENCRYPTION_KEY=$encryptionKey"
        "ALLOWED_ORIGINS=http://${localIp}:$portBind,http://localhost:$portBind"
        "FORCE_HTTPS=false"
        "# LAN deployment: relax loopback-only restrictor so RFC-1918 peers can hit the API."
        "ENABLE_NETWORK_RESTRICTIONS=allow_lan"
        "# AI assistant defaults - keep external providers off; bundle a local Ollama"
        "# if you want VLM (see backend\scripts\prepare_ollama_resources.ps1)."
        "SAKURA_LLM_ALLOW_EXTERNAL=false"
        "SAKURA_LLM_ALLOW_REMOTE_OLLAMA=false"
        "SAKURA_DISABLE_OLLAMA_SIDECAR=true"
        "SAKURA_DISABLE_LIVE_INDEXER=false"
    )
    Set-Content -Path .env -Value ($envLines -join "`n") -Encoding ascii
    Write-Host "[ok] .env created." -ForegroundColor Green
} else {
    Write-Host "[info] Using existing .env file." -ForegroundColor Gray
}

# 4. Firewall (best-effort, requires admin)
$ruleName = "Sakura LAN Port $portBind"
if (!(Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    try {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound `
            -LocalPort $portBind -Protocol TCP -Action Allow -ErrorAction Stop | Out-Null
        Write-Host "[ok] Firewall rule '$ruleName' created." -ForegroundColor Green
    } catch {
        Write-Host "[warn] Could not create firewall rule (run as Administrator to enable)." -ForegroundColor Yellow
    }
}

# 5. Build + launch
Write-Host "[info] Building and starting Sakura unified stack ..." -ForegroundColor Gray
if ($composeCommand.Length -eq 1) {
    & $composeCommand[0] up -d --build
} else {
    & $composeCommand[0] $composeCommand[1] up -d --build
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker Compose failed (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "--- Deployment Complete ---" -ForegroundColor Cyan
Write-Host "Sakura (frontend + API) is serving on:" -ForegroundColor Gray
Write-Host "  URL: http://${localIp}:$portBind/"   -ForegroundColor White
Write-Host "  API: http://${localIp}:$portBind/api/" -ForegroundColor White
Write-Host "---------------------------" -ForegroundColor Cyan
