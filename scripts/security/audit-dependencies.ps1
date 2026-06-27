# Dependency audit for the target machine (pip + npm). Invoked from setup.ps1.
param(
    [string]$RootDir = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [string]$VenvPython = "",
    [switch]$Strict,
    [switch]$SkipNpm,
    [switch]$SkipPip
)

$ErrorActionPreference = 'Continue'

function Write-Audit { param($msg) Write-Host "[audit] $msg" -ForegroundColor Cyan }
function Write-AuditWarn { param($msg) Write-Host "[audit] $msg" -ForegroundColor Yellow }
function Write-AuditFail { param($msg) Write-Host "[audit] $msg" -ForegroundColor Red }

$ReportDir = Join-Path $RootDir "reports\security"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$SummaryPath = Join-Path $ReportDir "audit-summary-$Stamp.txt"

$exitCode = 0
$summary = @("Sakura dependency audit - $Stamp", "")

if (-not $VenvPython) {
    $VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
}

if (-not $SkipPip) {
    Write-Audit "Python: scanning installed packages in venv"
    if (-not (Test-Path $VenvPython)) {
        Write-AuditWarn "Venv Python not found - skipping pip audit"
        $summary += "pip-audit: SKIPPED (no venv)"
    } else {
        $pipProxy = @()
        if ($env:HTTPS_PROXY) { $pipProxy += @('--proxy', $env:HTTPS_PROXY) }
        elseif ($env:HTTP_PROXY) { $pipProxy += @('--proxy', $env:HTTP_PROXY) }

        & $VenvPython -m pip @pipProxy install -q pip-audit 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-AuditWarn "Could not install pip-audit (network or mirror required once)"
            $summary += "pip-audit: SKIPPED (install failed)"
        } else {
            $pipJson = Join-Path $ReportDir "pip-audit-$Stamp.json"
            $pipTxt = Join-Path $ReportDir "pip-audit-$Stamp.txt"
            & $VenvPython -m pip_audit --format json --output $pipJson 2>&1 | Tee-Object -FilePath $pipTxt
            $pipExit = $LASTEXITCODE
            if ($pipExit -ne 0) {
                Write-AuditWarn "pip-audit reported known vulnerabilities (see $pipTxt)"
                $summary += "pip-audit: FAIL ($pipTxt)"
                if ($Strict) { $exitCode = 1 }
            } else {
                Write-Audit "pip-audit: no known CVEs in installed packages"
                $summary += "pip-audit: PASS"
            }
        }
    }
}

if (-not $SkipNpm) {
    Write-Audit "npm: scanning frontend production dependencies"
    $frontend = Join-Path $RootDir "frontend"
    if (-not (Test-Path (Join-Path $frontend "package.json"))) {
        Write-AuditWarn "frontend/package.json missing - skipping npm audit"
        $summary += "npm-audit: SKIPPED (no frontend)"
    } else {
        Push-Location $frontend
        try {
            $npmProdJson = Join-Path $ReportDir "npm-audit-prod-$Stamp.json"
            $npmProdTxt = Join-Path $ReportDir "npm-audit-prod-$Stamp.txt"
            $npmDevTxt = Join-Path $ReportDir "npm-audit-dev-$Stamp.txt"

            npm audit --omit=dev --json 2>&1 | Out-File -FilePath $npmProdJson -Encoding utf8
            npm audit --omit=dev 2>&1 | Tee-Object -FilePath $npmProdTxt
            $npmExit = $LASTEXITCODE
            npm audit 2>&1 | Out-File -FilePath $npmDevTxt -Encoding utf8

            if ($npmExit -ne 0) {
                Write-AuditWarn "npm audit (production) reported issues (see $npmProdTxt)"
                $summary += "npm-audit (prod): FAIL ($npmProdTxt)"
                if ($Strict) { $exitCode = 1 }
            } else {
                Write-Audit "npm audit (production): no reported vulnerabilities"
                $summary += "npm-audit (prod): PASS"
            }
            $summary += "npm-audit (dev toolchain): $npmDevTxt"
        } finally {
            Pop-Location
        }
    }
}

$telemetryPattern = 'posthog|segment|sentry|mixpanel|amplitude|@sentry|firebase|bugsnag|datadog|hotjar|fullstory|google-analytics'
$pkgJson = Join-Path $RootDir "frontend\package.json"
if (Test-Path $pkgJson) {
    $manifest = Get-Content $pkgJson -Raw
    if ($manifest -match $telemetryPattern) {
        Write-AuditWarn "frontend/package.json matches telemetry SDK name pattern - review manually"
        $summary += "telemetry-manifest-check: REVIEW"
        if ($Strict) { $exitCode = 1 }
    } else {
        $summary += "telemetry-manifest-check: PASS (no known SDK names in package.json)"
    }
}

$summary += ""
$summary += "Reports directory: $ReportDir"
$summary | Set-Content -Path $SummaryPath -Encoding UTF8
Write-Audit "Summary written to $SummaryPath"

if ($exitCode -ne 0 -and $Strict) {
    Write-AuditFail "Audit failed (-AuditStrict). Fix issues or re-run with -SkipAudit."
}
exit $exitCode
