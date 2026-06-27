# Pack a source release for CI to build on a Linux Docker host (Option B).
# No Docker required on the developer Windows machine.
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File deploy\windows\pack-source-release.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\windows\pack-source-release.ps1 -Version 1.2.0
#
# Output: dist\release\sakura-source-release-<version>.zip
param(
    [string]$Version = "",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $OutputDir) { $OutputDir = Join-Path $Root "dist\release" }

if (-not $Version) {
    $Version = (git -C $Root rev-parse --short HEAD 2>$null)
    if (-not $Version) { $Version = (Get-Date -Format "yyyyMMdd") }
}

$ReleaseName = "sakura-source-release-$Version"
$Stage = Join-Path $OutputDir $ReleaseName
$ZipPath = Join-Path $OutputDir "$ReleaseName.zip"

$include = @(
    "docker-compose.yml",
    "Dockerfile.unified",
    ".env.example",
    "backend",
    "frontend",
    "deploy"
)

$excludeDirNames = @(
    "node_modules", ".angular", "dist", "__pycache__", ".pytest_cache",
    ".venv", "venv", ".git", "data", "reports", "uploads"
)

Write-Host "[release] Packing source bundle — version $Version" -ForegroundColor Cyan

if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

function Copy-FilteredTree {
    param([string]$Src, [string]$Dst)
    New-Item -ItemType Directory -Force -Path $Dst | Out-Null
    Get-ChildItem -LiteralPath $Src -Force | ForEach-Object {
        if ($excludeDirNames -contains $_.Name) { return }
        if ($_.Name -match '\.(db|db-wal|db-shm|pyc)$') { return }
        $target = Join-Path $Dst $_.Name
        if ($_.PSIsContainer) {
            Copy-FilteredTree -Src $_.FullName -Dst $target
        } else {
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
        }
    }
}

foreach ($item in $include) {
    $src = Join-Path $Root $item
    if (-not (Test-Path $src)) { throw "Missing required path: $item" }
    $dst = Join-Path $Stage $item
    if ((Get-Item $src).PSIsContainer) {
        Copy-FilteredTree -Src $src -Dst $dst
    } else {
        Copy-Item $src $dst -Force
    }
}

$meta = @(
    "Sakura source release bundle",
    "Version: $Version",
    "Packed: $(Get-Date -Format o)",
    "Packed on: $env:COMPUTERNAME ($env:OS)",
    "",
    "CI team: unzip on Linux Docker host and run deploy/linux/build-on-server.sh",
    "See deploy/ci/RUNBOOK-OPTION-B.md in this zip."
) -join "`n"
Set-Content -Path (Join-Path $Stage "RELEASE.txt") -Value $meta -Encoding UTF8

if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $ZipPath -Force

Write-Host "[release] Done: $ZipPath" -ForegroundColor Green
Write-Host "[release] CI builds images on the Linux server — internet required at build time." -ForegroundColor Green
