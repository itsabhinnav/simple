# =============================================================================
# Sakura - reset the local SQLite database.
#
# Removes the runtime database artefacts produced by the backend so the next
# server start brings up an empty, freshly initialised schema. The Flask app
# rebuilds the table layout via HybridDatabaseService on startup and
# re-provisions the master admin from .env, so there is no separate
# "re-init" step.
#
# The legacy -WithRemote flag was removed: the remote/Git database mirror
# was deleted, and backend\data\remote\* no longer exists.
#
# By default this script deletes the SQLite primary DB and the RAG vector
# sidecar. Pass -WithUploads to also blow away uploaded spec files.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\clean_db.ps1
#   powershell -ExecutionPolicy Bypass -File .\clean_db.ps1 -Force
#   powershell -ExecutionPolicy Bypass -File .\clean_db.ps1 -WithUploads
# =============================================================================

[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$WithUploads,
    # No-op kept so old call sites don't break with an "unknown parameter".
    [switch]$WithRemote
)

$ErrorActionPreference = 'Stop'
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

function Log  { param($msg) Write-Host "[sakura] $msg" -ForegroundColor Cyan }
function Warn { param($msg) Write-Host "[sakura] $msg" -ForegroundColor Yellow }
function Fail { param($msg) Write-Host "[sakura] $msg" -ForegroundColor Red; exit 1 }

if ($WithRemote) {
    Warn "-WithRemote is a no-op (remote/Git sync was removed)."
}

$LocalWalDir = Join-Path $RootDir 'backend\data\local\dev\database'
$LocalDb     = Join-Path $LocalWalDir 'sakura_db.db'
$VectorDir   = Join-Path $RootDir 'backend\data\local\dev\vectors'
$UploadsDir  = Join-Path $RootDir 'backend\uploads'

$targets = @()
if (Test-Path $LocalDb) { $targets += $LocalDb }
foreach ($side in @('sakura_db.db-wal', 'sakura_db.db-shm', 'sakura_db.db-journal')) {
    $p = Join-Path $LocalWalDir $side
    if (Test-Path $p) { $targets += $p }
}
# RAG vector index sidecar (sqlite-vec); rebuilt on next start by the live indexer.
if (Test-Path $VectorDir) {
    foreach ($vec in @('sakura_vec.db', 'sakura_vec.db-wal', 'sakura_vec.db-shm', 'sakura_vec.db-journal')) {
        $p = Join-Path $VectorDir $vec
        if (Test-Path $p) { $targets += $p }
    }
}
if ($WithUploads -and (Test-Path $UploadsDir)) { $targets += $UploadsDir }

if (-not $targets) {
    Log "Nothing to clean. Local DB and selected optional paths are already absent."
    exit 0
}

Log "The following paths will be removed:"
foreach ($t in $targets) {
    $size = 0
    try {
        if (Test-Path $t -PathType Container) {
            $size = (Get-ChildItem $t -Recurse -Force -ErrorAction SilentlyContinue |
                     Measure-Object -Property Length -Sum).Sum
        } else {
            $size = (Get-Item $t -Force).Length
        }
    } catch { $size = 0 }
    $kb = if ($size) { [math]::Round($size / 1KB, 1) } else { 0 }
    Write-Host ("  - {0}   ({1} KB)" -f $t, $kb)
}

if (-not $WithUploads) { Warn "Pass -WithUploads to also delete backend\uploads (uploaded spec files)." }

if (-not $Force) {
    $resp = Read-Host "Type 'DELETE' to confirm"
    if ($resp -ne 'DELETE') {
        Warn "Aborted."
        exit 1
    }
}

foreach ($t in $targets) {
    try {
        if (Test-Path $t -PathType Container) {
            Remove-Item -Recurse -Force -LiteralPath $t
        } else {
            Remove-Item -Force -LiteralPath $t
        }
        Log "Removed $t"
    } catch {
        Warn "Failed to remove ${t}: $($_.Exception.Message)"
    }
}

Log "Database cleaned. Start the server (start.ps1) - the schema will be"
Log "recreated, the master admin (.env) re-provisioned, and the RAG vector"
Log "index rebuilt automatically by the live indexer."
