# Build and push to Docker Hub (sriabhi001/simple).
#
# Usage:
#   $env:DOCKERHUB_USERNAME = "sriabhi001"
#   $env:DOCKERHUB_TOKEN = "dckr_pat_..."
#   powershell -ExecutionPolicy Bypass -File deploy\windows\push-to-dockerhub.ps1 -Tag 1.0.0
param(
    [string]$Tag = "latest",
    [string]$Image = "sriabhi001/simple",
    [switch]$SkipBuild,
    [string]$Platform = "linux/amd64"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $Root

try {
    $user = $env:DOCKERHUB_USERNAME
    $token = $env:DOCKERHUB_TOKEN
    if (-not $user -or -not $token) {
        throw "Set DOCKERHUB_USERNAME and DOCKERHUB_TOKEN before pushing."
    }

    $envFile = Join-Path $Root ".env"
    if (Test-Path $envFile) {
        $line = Get-Content $envFile | Where-Object { $_ -match '^\s*SAKURA_BACKEND_IMAGE=' } | Select-Object -First 1
        if ($line) {
            $fromEnv = ($line -replace '^\s*SAKURA_BACKEND_IMAGE=', '').Trim() -replace ':.*$', ''
            if ($fromEnv) { $Image = $fromEnv }
        }
    }

    $targetImage = "${Image}:$Tag"

    $token | docker login -u $user --password-stdin
    if ($LASTEXITCODE -ne 0) { throw "docker login failed" }

    if (-not $SkipBuild) {
        Write-Host "(dockerhub) Building $targetImage ($Platform) ..." -ForegroundColor Cyan
        docker buildx build --platform $Platform -f Dockerfile.unified -t $targetImage --load .
        if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
    } else {
        docker image inspect $targetImage 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            docker tag sakura-backend:latest $targetImage
        }
    }

    Write-Host "(dockerhub) Pushing $targetImage ..." -ForegroundColor Cyan
    docker push $targetImage
    if ($LASTEXITCODE -ne 0) { throw "docker push failed" }

    if ($Tag -ne "latest") {
        docker tag $targetImage "${Image}:latest"
        docker push "${Image}:latest"
    }

    Write-Host "(dockerhub) Done: https://hub.docker.com/r/$Image" -ForegroundColor Green
} finally {
    Pop-Location
}
