<#
.SYNOPSIS
    Build-time helper: vendor ollama.exe + the qwen2.5vl:7b model blobs into
    the installer payload so Sakura ships fully offline.

.DESCRIPTION
    Run this on a clean build machine (Windows) once per release. It:

      1. Verifies a working ollama.exe (downloaded, on PATH, or supplied via
         -OllamaExe).
      2. Sets OLLAMA_MODELS to a temporary staging directory and pulls the
         configured model tags into it (default: qwen2.5vl:7b + qwen2.5vl:3b).
      3. Copies ollama.exe and the staged blobs into
         <repo>/backend/resources/ollama/ which the installer packager picks
         up. The Sakura backend's ollama_sidecar.py looks here first.

    The pulled blobs are large (~6 GB for qwen2.5vl:7b Q4_K_M, ~3 GB for the
    3b lite fallback). Plan disk accordingly.

.PARAMETER OllamaExe
    Path to ollama.exe. If omitted, falls back to PATH or
    %LOCALAPPDATA%\Programs\Ollama\ollama.exe.

.PARAMETER Models
    Comma-separated list of model tags to pre-pull. Defaults to
    "qwen2.5vl:7b,qwen2.5vl:3b" (matches parsing.vlm.providers.ollama.model
    + lite_model in backend/config/config.yaml).

.PARAMETER OutDir
    Override the resources output directory. Defaults to
    <repo>/backend/resources/ollama relative to this script.

.EXAMPLE
    pwsh ./prepare_ollama_resources.ps1
    pwsh ./prepare_ollama_resources.ps1 -Models "qwen2.5vl:7b" -OutDir D:\sakura-installer\ollama
#>

[CmdletBinding()]
param(
    [string] $OllamaExe,
    [string] $Models = "qwen2.5vl:7b,qwen2.5vl:3b",
    [string] $OutDir
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$backendRoot = Split-Path -Parent $scriptRoot
$repoRoot = Split-Path -Parent $backendRoot

if (-not $OutDir) {
    $OutDir = Join-Path $backendRoot "resources\ollama"
}

if (-not $OllamaExe) {
    $OllamaExe = (Get-Command ollama.exe -ErrorAction SilentlyContinue).Source
    if (-not $OllamaExe) {
        $candidate = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
        if (Test-Path $candidate) { $OllamaExe = $candidate }
    }
}

if (-not $OllamaExe -or -not (Test-Path $OllamaExe)) {
    Write-Error "ollama.exe not found. Install Ollama from https://ollama.com/download/windows or pass -OllamaExe."
}

Write-Host "[prep] Using ollama.exe: $OllamaExe"
Write-Host "[prep] Output directory:  $OutDir"
Write-Host "[prep] Models:            $Models"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$modelsStaging = Join-Path $OutDir "models"
New-Item -ItemType Directory -Force -Path $modelsStaging | Out-Null

Copy-Item -Path $OllamaExe -Destination (Join-Path $OutDir "ollama.exe") -Force
Write-Host "[prep] Copied ollama.exe -> $OutDir\ollama.exe"

$env:OLLAMA_MODELS = $modelsStaging
$env:OLLAMA_HOST   = "127.0.0.1:11434"

$serverProc = $null
try {
    Write-Host "[prep] Starting transient ollama serve against $modelsStaging ..."
    $serverProc = Start-Process -FilePath $OllamaExe -ArgumentList "serve" -PassThru -NoNewWindow `
        -RedirectStandardOutput (Join-Path $OutDir "_serve.log") `
        -RedirectStandardError  (Join-Path $OutDir "_serve.err.log")

    # Wait up to 30s for the daemon to bind 11434.
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        try {
            $null = Test-NetConnection -ComputerName 127.0.0.1 -Port 11434 -InformationLevel Quiet -WarningAction SilentlyContinue
            if ($?) { break }
        } catch {}
        Start-Sleep -Milliseconds 500
    }

    foreach ($tag in ($Models -split ",")) {
        $tag = $tag.Trim()
        if (-not $tag) { continue }
        Write-Host "[prep] Pulling $tag ..."
        & $OllamaExe pull $tag
        if ($LASTEXITCODE -ne 0) {
            Write-Error "ollama pull $tag failed with exit code $LASTEXITCODE"
        }
    }
} finally {
    if ($serverProc -and -not $serverProc.HasExited) {
        Write-Host "[prep] Stopping transient ollama serve ..."
        try { $serverProc | Stop-Process -Force } catch {}
    }
}

$totalBytes = (Get-ChildItem -Recurse -File -Path $modelsStaging | Measure-Object -Property Length -Sum).Sum
$totalGb = [math]::Round($totalBytes / 1GB, 2)
Write-Host "[prep] Staged blobs total size: $totalGb GB at $modelsStaging"
Write-Host "[prep] Done. Bundle the contents of $OutDir into the installer payload."
Write-Host "[prep] At runtime the backend will set OLLAMA_MODELS to its install-local equivalent and exec the bundled ollama.exe."
