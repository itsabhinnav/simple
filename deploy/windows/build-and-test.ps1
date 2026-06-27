# Build linux/amd64 images and smoke-test on this machine (Windows Docker Desktop
# runs the same Linux images as the production LAN server).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File deploy\windows\build-and-test.ps1
param(
    [string]$Version = "local-test",
    [switch]$SkipExport,
    [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $Root
try {
    if (-not $SkipExport) {
        & (Join-Path $PSScriptRoot "build-and-export.ps1") -Version $Version -Platform linux/amd64
    }

    if (-not (Test-Path .env)) {
        Copy-Item .env.example .env
        Write-Host '.env created from example - fill JWT_SECRET_KEY and ENCRYPTION_KEY before production use.' -ForegroundColor Yellow
    }

    $cert = "deploy\lan\nginx\certs\sakura.crt"
    if (-not (Test-Path $cert)) {
        & powershell -ExecutionPolicy Bypass -File deploy\lan\scripts\generate-tls.ps1 127.0.0.1
    }

    Write-Host '(test) Starting stack (linux/amd64 on Docker Desktop)...' -ForegroundColor Cyan
    docker compose up -d --no-build
    if ($LASTEXITCODE -ne 0) {
        Write-Host '(test) Images missing - building then starting...' -ForegroundColor Yellow
        docker compose up -d --build
    }

    $ok = $false
    for ($i = 1; $i -le 40; $i++) {
        Start-Sleep -Seconds 3
        if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
            $code = curl.exe -k -s -o NUL -w '%{http_code}' 'https://127.0.0.1/health' 2>$null
            if ($code -eq '200') { $ok = $true; break }
        } else {
            try {
                [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
                $r = Invoke-WebRequest -Uri 'https://127.0.0.1/health' -UseBasicParsing -TimeoutSec 5
                if ($r.StatusCode -eq 200) { $ok = $true; break }
            } catch { }
        }
        Write-Host "(test) Waiting for health ($i/40)..." -ForegroundColor DarkGray
    }

    if ($ok) {
        Write-Host '(test) PASS - open https://127.0.0.1/ (same image as Linux LAN deploy)' -ForegroundColor Green
        docker compose ps
    } else {
        Write-Host '(test) FAIL - check: docker compose logs backend nginx' -ForegroundColor Red
        docker compose logs --tail 40 backend nginx
        exit 1
    }

    if (-not $KeepRunning) {
        Write-Host '(test) Leaving stack running. Stop with: docker compose down' -ForegroundColor Cyan
    }
} finally {
    Pop-Location
}
