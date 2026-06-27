# Build Sakura Docker images on Windows (Docker Desktop / Linux containers)
# and pack a release bundle for the CI team to deploy on a Linux LAN host.
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File deploy\windows\build-and-export.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\windows\build-and-export.ps1 -Version 1.2.0 -Platform linux/amd64
#
# Output: dist\release\sakura-docker-release-<version>.zip
#   Contains pre-built images + compose + deploy/ + CI runbook (no app secrets).
param(
    [string]$Version = "",
    [string]$Platform = "linux/amd64",
    [string]$OutputDir = "",
    [switch]$SkipBuild,
    [switch]$SkipPull,
    [switch]$IncludeIamProfile
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $OutputDir) { $OutputDir = Join-Path $Root "dist\release" }

function Require-Docker {
    docker version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw @"
Docker is not running. Start Docker Desktop (Linux containers mode) and retry.
This script produces Linux images for a Linux LAN server - Windows containers must be OFF.
"@
    }
    $serverOs = (docker version --format "{{.Server.Os}}" 2>$null)
    if ($serverOs -ne "linux") {
        throw "Docker server OS is '$serverOs'. Switch Docker Desktop to Linux containers."
    }
}

if (-not $Version) {
    $Version = (git -C $Root rev-parse --short HEAD 2>$null)
    if (-not $Version) { $Version = (Get-Date -Format "yyyyMMdd") }
}

$ReleaseName = "sakura-docker-release-$Version"
$Stage = Join-Path $OutputDir $ReleaseName
$ImagesTar = Join-Path $Stage "sakura-images.tar"
$ZipPath = Join-Path $OutputDir "$ReleaseName.zip"

Write-Host "(release) Sakura Docker export - version $Version" -ForegroundColor Cyan
Write-Host "(release) Platform target: $Platform" -ForegroundColor Cyan

Require-Docker
Push-Location $Root
try {
    if (-not $SkipBuild) {
        Write-Host "(release) Building sakura-backend:latest ($Platform)..." -ForegroundColor Cyan
        docker buildx version *> $null
        if ($LASTEXITCODE -eq 0) {
            docker buildx build --platform $Platform -f Dockerfile.unified -t sakura-backend:latest --load .
        } else {
            if ($Platform -ne "linux/amd64") {
                throw "docker buildx is required when Platform is not the host default. Install/buildx or use -Platform linux/amd64."
            }
            docker compose build backend
        }
        if ($LASTEXITCODE -ne 0) { throw "Image build failed." }
    }

    if (-not $SkipPull) {
        Write-Host "(release) Pulling nginx + redis base images..." -ForegroundColor Cyan
        docker compose pull nginx redis 2>$null
        if ($LASTEXITCODE -ne 0) {
            docker pull nginx:1.27-alpine
            docker pull redis:7-alpine
        }
        if ($IncludeIamProfile) {
            Write-Host "(release) Pulling optional IAM profile images..." -ForegroundColor Cyan
            docker pull quay.io/keycloak/keycloak:26.0.7
            docker pull authelia/authelia:4.38
        }
    }

    $imageRefs = @(
        "sakura-backend:latest",
        "nginx:1.27-alpine",
        "redis:7-alpine"
    )
    if ($IncludeIamProfile) {
        $imageRefs += @(
            "quay.io/keycloak/keycloak:26.0.7",
            "authelia/authelia:4.38"
        )
    }

    if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
    New-Item -ItemType Directory -Force -Path $Stage | Out-Null

    Write-Host "(release) Saving images to sakura-images.tar..." -ForegroundColor Cyan
    docker save @imageRefs -o $ImagesTar
    if ($LASTEXITCODE -ne 0) { throw "docker save failed." }

    Copy-Item (Join-Path $Root "docker-compose.yml") $Stage
    Copy-Item (Join-Path $Root ".env.example") $Stage
    Copy-Item -Recurse (Join-Path $Root "deploy") $Stage

    $metaLines = @(
        "Sakura Docker release bundle",
        "Version: $Version",
        "Built: $(Get-Date -Format o)",
        "Platform: $Platform",
        "Built on: $env:COMPUTERNAME ($env:OS)",
        "Images: $($imageRefs -join ', ')",
        "Offline LAN deploy: YES - Linux host does not need npm/pip/Docker Hub at deploy time.",
        "IncludeIamProfile: $IncludeIamProfile",
        "",
        "CI team: see deploy/ci/RUNBOOK-OPTION-A.md in this zip."
    )
    $meta = $metaLines -join "`n"
    Set-Content -Path (Join-Path $Stage "RELEASE.txt") -Value $meta -Encoding UTF8

    if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
    Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $ZipPath -Force

    Write-Host "(release) Done: $ZipPath" -ForegroundColor Green
    Write-Host '(release) Hand zip to CI - deploy/linux/import-and-deploy.sh (RUNBOOK-OPTION-A.md)' -ForegroundColor Green
} finally {
    Pop-Location
}
