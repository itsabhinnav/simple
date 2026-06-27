# Build (optional) and push sakura-backend to GitHub Container Registry.
#
# Prerequisites:
#   - SAKURA_BACKEND_IMAGE in .env  e.g. ghcr.io/your-org/simple:latest
#   - GHCR_USER + GHCR_TOKEN env vars (PAT with write:packages)
#
# Usage:
#   $env:GHCR_USER = "your-github-user"
#   $env:GHCR_TOKEN = "ghp_..."
#   powershell -ExecutionPolicy Bypass -File deploy\windows\push-to-ghcr.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\windows\push-to-ghcr.ps1 -Tag 1.0.0 -SkipBuild
param(
    [string]$Tag = "latest",
    [switch]$SkipBuild,
    [string]$Platform = "linux/amd64"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $Root

function Get-ImageBase {
    $envFile = Join-Path $Root ".env"
    if (-not (Test-Path $envFile)) { throw ".env missing — set SAKURA_BACKEND_IMAGE=ghcr.io/owner/repo:latest" }
    $line = Get-Content $envFile | Where-Object { $_ -match '^\s*SAKURA_BACKEND_IMAGE=' } | Select-Object -First 1
    if (-not $line) { throw "SAKURA_BACKEND_IMAGE not set in .env" }
    $ref = ($line -replace '^\s*SAKURA_BACKEND_IMAGE=', '').Trim()
    if ($ref -notmatch '^ghcr\.io/') { throw "SAKURA_BACKEND_IMAGE must be ghcr.io/... (lowercase). Got: $ref" }
    return ($ref -replace ':.*$', '')
}

try {
    $user = $env:GHCR_USER
    $token = $env:GHCR_TOKEN
    if (-not $user -or -not $token) {
        throw "Set GHCR_USER and GHCR_TOKEN (PAT with write:packages) before pushing."
    }

    $base = Get-ImageBase
    $targetImage = "${base}:$Tag"

    $token | docker login ghcr.io -u $user --password-stdin | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker login ghcr.io failed" }

    if (-not $SkipBuild) {
        Write-Host "(ghcr) Building $targetImage ($Platform) ..." -ForegroundColor Cyan
        docker buildx build --platform $Platform -f Dockerfile.unified -t $targetImage --load .
        if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
    } else {
        docker image inspect $targetImage 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            docker image inspect sakura-backend:latest 2>$null | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "No local image — run without -SkipBuild" }
            docker tag sakura-backend:latest $targetImage
        }
    }

    Write-Host "(ghcr) Pushing $targetImage ..." -ForegroundColor Cyan
    docker push $targetImage
    if ($LASTEXITCODE -ne 0) { throw "docker push failed" }

    if ($Tag -ne "latest") {
        docker tag $targetImage "${base}:latest"
        docker push "${base}:latest"
    }

    Write-Host "(ghcr) Done: $targetImage" -ForegroundColor Green
    Write-Host "(ghcr) Pull elsewhere: deploy/windows/pull-from-ghcr.ps1 or deploy/linux/pull-from-ghcr.sh" -ForegroundColor Green
} finally {
    Pop-Location
}
