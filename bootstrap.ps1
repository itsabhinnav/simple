# Sakura Docker bootstrap (Windows) — interactive LAN deployment wizard.
$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

Write-Host "--- Sakura Docker Bootstrap (Windows) ---" -ForegroundColor Cyan

if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker Desktop is required. Install Docker Desktop and retry."
    exit 1
}
cmd /c "docker info >nul 2>nul"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker Desktop is not running. Start Docker Desktop and retry."
    exit 1
}

$composeCommand = @("docker", "compose")
docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $composeCommand = @("docker-compose")
    } else {
        Write-Error "Docker Compose is required."
        exit 1
    }
}

. (Join-Path $RootDir 'scripts\setup-wizard.ps1')

$reconfigure = $false
if (Test-Path (Join-Path $RootDir '.env')) {
    $raw = Read-Host "Existing .env found. Reconfigure? [y/N]"
    $reconfigure = $raw -match '^[yY]'
}

if (-not (Test-Path (Join-Path $RootDir '.env')) -or $reconfigure) {
    $cfg = Invoke-SakuraSetupWizard -PythonExe "python"
    if ($null -eq $cfg) { exit 0 }
    if (-not $cfg.DockerMode) {
        Write-Host "[info] Native mode selected — run setup.ps1 instead for venv build." -ForegroundColor Yellow
        Write-SakuraEnvFile -Path (Join-Path $RootDir '.env') -Lines $cfg.EnvLines
        Write-Host "  .\.venv\Scripts\python.exe backend\run_server.py" -ForegroundColor Gray
        exit 0
    }
    Write-SakuraEnvFile -Path (Join-Path $RootDir '.env') -Lines $cfg.EnvLines
} else {
    Write-Host "[info] Using existing .env (run bootstrap.ps1 and choose reconfigure to change)." -ForegroundColor Gray
    $cfg = [PSCustomObject]@{ DockerMode = $true; LanIp = (Get-LanIpAddress); ComposeProfiles = @() }
}

$tlsScript = Join-Path $RootDir 'deploy\lan\scripts\generate-tls.ps1'
if (Test-Path $tlsScript) { & $tlsScript $cfg.LanIp }

Write-Host "[info] Building and starting Sakura stack ..." -ForegroundColor Gray
$profileArgs = @()
if ($cfg.ComposeProfiles) {
    foreach ($p in $cfg.ComposeProfiles) { $profileArgs += @('--profile', $p) }
}
if ($composeCommand.Length -eq 1) {
    & $composeCommand[0] @profileArgs up -d --build
} else {
    & $composeCommand[0] $composeCommand[1] @profileArgs up -d --build
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "--- Deployment Complete ---" -ForegroundColor Cyan
Write-Host "  URL: https://$($cfg.LanIp)/" -ForegroundColor White
Write-Host "  API: https://$($cfg.LanIp)/api/" -ForegroundColor White
Write-Host "---------------------------" -ForegroundColor Cyan
