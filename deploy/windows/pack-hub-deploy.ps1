# Pack minimal Docker Hub deploy bundle for CI (no source code, no image tar).
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File deploy\windows\pack-hub-deploy.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\windows\pack-hub-deploy.ps1 -Version 1.0.0
#
# Output: dist\release\sakura-hub-deploy-<version>.zip
param(
    [string]$Version = "",
    [string]$OutputDir = "",
    [string]$HubImage = "sriabhi001/simple:latest"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $OutputDir) { $OutputDir = Join-Path $Root "dist\release" }

if (-not $Version) {
    $Version = (git -C $Root rev-parse --short HEAD 2>$null)
    if (-not $Version) { $Version = (Get-Date -Format "yyyyMMdd") }
}

$ReleaseName = "sakura-hub-deploy-$Version"
$Stage = Join-Path $OutputDir $ReleaseName
$ZipPath = Join-Path $OutputDir "$ReleaseName.zip"

$paths = @(
    @{ Src = "docker-compose.yml"; Dst = "docker-compose.yml" },
    @{ Src = ".env.example"; Dst = ".env.example" },
    @{ Src = "deploy\lan\nginx\nginx.conf"; Dst = "deploy\lan\nginx\nginx.conf" },
    @{ Src = "deploy\lan\nginx\certs\.gitkeep"; Dst = "deploy\lan\nginx\certs\.gitkeep" },
    @{ Src = "deploy\lan\scripts\generate-tls.sh"; Dst = "deploy\lan\scripts\generate-tls.sh" },
    @{ Src = "deploy\lan\scripts\generate-tls.ps1"; Dst = "deploy\lan\scripts\generate-tls.ps1" },
    @{ Src = "deploy\linux\pull-from-dockerhub.sh"; Dst = "deploy\linux\pull-from-dockerhub.sh" },
    @{ Src = "deploy\linux\deploy-from-dockerhub.sh"; Dst = "deploy\linux\deploy-from-dockerhub.sh" },
    @{ Src = "deploy\linux\docker-stack.sh"; Dst = "deploy\linux\docker-stack.sh" },
    @{ Src = "deploy\ci\RUNBOOK-OPTION-C-DOCKERHUB.md"; Dst = "deploy\ci\RUNBOOK-OPTION-C-DOCKERHUB.md" },
    @{ Src = "deploy\ci\HANDOFF-OPTION-C.md"; Dst = "deploy\ci\HANDOFF-OPTION-C.md" }
)

Write-Host ('[hub-deploy] Packing minimal Docker Hub bundle - version ' + $Version) -ForegroundColor Cyan

if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

foreach ($item in $paths) {
    $src = Join-Path $Root $item.Src
    if (-not (Test-Path $src)) { throw "Missing required path: $($item.Src)" }
    $dst = Join-Path $Stage $item.Dst
    $parent = Split-Path $dst -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Copy-Item -LiteralPath $src -Destination $dst -Force
}

$meta = @(
    'Sakura Docker Hub deploy bundle (minimal - no source code)'
    "Version: $Version"
    "Packed: $(Get-Date -Format o)"
    "Hub image: $HubImage"
    "Packed on: $env:COMPUTERNAME"
    ''
    'CI: unzip, copy .env.example to .env, fill secrets, then:'
    '  bash deploy/linux/deploy-from-dockerhub.sh --lan-ip SERVER_IP'
    ''
    'See deploy/ci/RUNBOOK-OPTION-C-DOCKERHUB.md in this zip.'
) -join "`n"
Set-Content -Path (Join-Path $Stage "RELEASE.txt") -Value $meta -Encoding UTF8

if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $ZipPath -Force

$sizeKb = [math]::Round((Get-Item $ZipPath).Length / 1KB, 1)
Write-Host ('[hub-deploy] Done: ' + $ZipPath + ' (' + $sizeKb + ' KB)') -ForegroundColor Green
Write-Host '[hub-deploy] Hand to CI with Hub URL: https://hub.docker.com/r/sriabhi001/simple' -ForegroundColor Green
