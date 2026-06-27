# Pull sakura-backend from GHCR (set SAKURA_BACKEND_IMAGE in .env).
#
# Usage:
#   $env:GHCR_USER = "..."
#   $env:GHCR_TOKEN = "..."   # read:packages for private images
#   powershell -ExecutionPolicy Bypass -File deploy\windows\pull-from-ghcr.ps1
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $Root
try {
    & bash deploy/linux/pull-from-ghcr.sh
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
