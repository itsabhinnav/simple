# Pull from Docker Hub (SAKURA_BACKEND_IMAGE in .env).
param()

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $Root
try {
    bash deploy/linux/pull-from-dockerhub.sh
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
