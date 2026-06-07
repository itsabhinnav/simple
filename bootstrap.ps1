# Sakura Unified Bootstrap Script (Windows)
# This script handles EVERYTHING: dependency checks, building, and deployment.

$ErrorActionPreference = "Stop"
Write-Host "--- Sakura Unified Bootstrap (Windows) ---" -ForegroundColor Cyan

# 1. Dependency Checks
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Error: Docker Desktop is required. Please install it."
    exit 1
}

try {
    cmd /c "docker info >nul 2>nul"
    if ($LASTEXITCODE -ne 0) { throw "Docker daemon is not responding." }
} catch {
    Write-Error "Error: Docker Desktop is not running. Please start Docker Desktop and retry."
    exit 1
}

$composeCommand = @("docker", "compose")
docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $composeCommand = @("docker-compose")
    } else {
        Write-Error "Error: Docker Compose is required."
        exit 1
    }
}

# 2. Local IP Detection
$localIp = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -notlike '169.254.*' -and
        $_.InterfaceAlias -notmatch 'vEthernet|Loopback' -and
        $_.PrefixOrigin -ne 'WellKnown'
    } |
    Sort-Object -Property InterfaceMetric |
    Select-Object -First 1).IPAddress
if (!$localIp) { $localIp = "localhost" }
Write-Host "[INFO] Detected Local IP: $localIp" -ForegroundColor Gray

# 3. Environment & Secret Setup
if (!(Test-Path .env)) {
    Write-Host "[INFO] Generating secure keys..." -ForegroundColor Gray
    
    $jwtSecret = [Convert]::ToBase64String((1..32 | ForEach-Object { [byte](Get-Random -Minimum 0 -Maximum 255) }))
    $encryptionKeyBytes = (1..32 | ForEach-Object { [byte](Get-Random -Minimum 0 -Maximum 255) })
    $encryptionKey = [Convert]::ToBase64String($encryptionKeyBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_') + "="

    $envLines = @(
        "ENVIRONMENT=production"
        "FLASK_ENV=production"
        "HOST=0.0.0.0"
        "PORT=5000"
        "JWT_SECRET_KEY=$jwtSecret"
        "ENCRYPTION_KEY=$encryptionKey"
        "ALLOWED_ORIGINS=http://${localIp}:5000,http://localhost:5000"
        "FORCE_HTTPS=false"
        "# strict | allow_lan | off  (off is refused in production)"
        "ENABLE_NETWORK_RESTRICTIONS=strict"
        "# AI assistant - external LLM providers are refused unless flipped on."
        "SAKURA_LLM_ALLOW_EXTERNAL=false"
        "SAKURA_LLM_ALLOW_REMOTE_OLLAMA=false"
        "# Bundled Ollama daemon (desktop installer only). Containers stay off by default."
        "SAKURA_DISABLE_OLLAMA_SIDECAR=true"
        "# RAG live indexer thread - disable only when debugging cold-start CPU."
        "SAKURA_DISABLE_LIVE_INDEXER=false"
    )
    Set-Content -Path .env -Value ($envLines -join "`n") -Encoding ascii
    Write-Host "[SUCCESS] .env file created." -ForegroundColor Green
}

# 4. Deployment
Write-Host "[INFO] Building and Starting Sakura Unified Stack..." -ForegroundColor Gray
Write-Host "This may take several minutes on first run..." -ForegroundColor Gray

# Use Docker Compose with a specific project name to avoid conflicts
if ($composeCommand.Length -eq 1) {
    & $composeCommand[0] up -d --build
} else {
    & $composeCommand[0] $composeCommand[1] up -d --build
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error: Docker Compose failed to build or start Sakura."
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "--- Deployment Complete ---" -ForegroundColor Cyan
Write-Host "Sakura is now served via Flask on:" -ForegroundColor Gray
Write-Host "URL: http://${localIp}:5000" -ForegroundColor White
Write-Host "---------------------------" -ForegroundColor Cyan
Write-Host "[HINT] Both frontend and API are now on port 5000." -ForegroundColor Gray
