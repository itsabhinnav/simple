#!/usr/bin/env bash
# Dependency audit for the target machine (pip + npm). Invoked from setup.sh.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV_PY="${VENV_PY:-$ROOT/.venv/bin/python}"
STRICT=0
SKIP_NPM=0
SKIP_PIP=0

while [ $# -gt 0 ]; do
  case "$1" in
    --strict) STRICT=1 ;;
    --skip-npm) SKIP_NPM=1 ;;
    --skip-pip) SKIP_PIP=1 ;;
    --root) ROOT="$2"; shift ;;
    --venv-python) VENV_PY="$2"; shift ;;
  esac
  shift
done

audit_log()  { printf '\033[1;36m[audit]\033[0m %s\n' "$*"; }
audit_warn() { printf '\033[1;33m[audit]\033[0m %s\n' "$*"; }
audit_fail() { printf '\033[1;31m[audit]\033[0m %s\n' "$*"; }

REPORT_DIR="$ROOT/reports/security"
mkdir -p "$REPORT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
SUMMARY="$REPORT_DIR/audit-summary-$STAMP.txt"
EXIT_CODE=0

{
  echo "Sakura dependency audit — $STAMP"
  echo
} > "$SUMMARY"

# --- Python ---
if [ "$SKIP_PIP" -eq 0 ]; then
  audit_log "Python: scanning installed packages in venv"
  if [ ! -x "$VENV_PY" ]; then
    audit_warn "Venv Python not found at $VENV_PY — skipping pip audit"
    echo "pip-audit: SKIPPED (no venv)" >> "$SUMMARY"
  else
    PIP_PROXY=()
    [ -n "${HTTPS_PROXY:-}" ] && PIP_PROXY=(--proxy "$HTTPS_PROXY")
    [ -n "${HTTP_PROXY:-}" ] && [ ${#PIP_PROXY[@]} -eq 0 ] && PIP_PROXY=(--proxy "$HTTP_PROXY")

    if ! "$VENV_PY" -m pip "${PIP_PROXY[@]}" install -q pip-audit 2>/dev/null; then
      audit_warn "Could not install pip-audit (network/mirror required once)"
      echo "pip-audit: SKIPPED (install failed)" >> "$SUMMARY"
    else
      PIP_JSON="$REPORT_DIR/pip-audit-$STAMP.json"
      PIP_TXT="$REPORT_DIR/pip-audit-$STAMP.txt"
      if "$VENV_PY" -m pip_audit --format json --output "$PIP_JSON" >"$PIP_TXT" 2>&1; then
        audit_log "pip-audit: no known CVEs in installed packages"
        echo "pip-audit: PASS" >> "$SUMMARY"
      else
        audit_warn "pip-audit reported known vulnerabilities (see $PIP_TXT)"
        echo "pip-audit: FAIL ($PIP_TXT)" >> "$SUMMARY"
        [ "$STRICT" -eq 1 ] && EXIT_CODE=1
      fi
    fi
  fi
fi

# --- npm ---
if [ "$SKIP_NPM" -eq 0 ]; then
  audit_log "npm: scanning frontend production dependencies"
  if [ ! -f "$ROOT/frontend/package.json" ]; then
    audit_warn "frontend/package.json missing — skipping npm audit"
    echo "npm-audit: SKIPPED (no frontend)" >> "$SUMMARY"
  else
    (
      cd "$ROOT/frontend"
      NPM_PROD_JSON="$REPORT_DIR/npm-audit-prod-$STAMP.json"
      NPM_PROD_TXT="$REPORT_DIR/npm-audit-prod-$STAMP.txt"
      NPM_DEV_TXT="$REPORT_DIR/npm-audit-dev-$STAMP.txt"
      npm audit --omit=dev --json >"$NPM_PROD_JSON" 2>&1 || true
      npm audit --omit=dev >"$NPM_PROD_TXT" 2>&1 || true
      npm audit >"$NPM_DEV_TXT" 2>&1 || true
      if npm audit --omit=dev >/dev/null 2>&1; then
        audit_log "npm audit (production): no reported vulnerabilities"
        echo "npm-audit (prod): PASS" >> "$SUMMARY"
      else
        audit_warn "npm audit (production) reported issues (see $NPM_PROD_TXT)"
        echo "npm-audit (prod): FAIL ($NPM_PROD_TXT)" >> "$SUMMARY"
        [ "$STRICT" -eq 1 ] && EXIT_CODE=1
      fi
      echo "npm-audit (dev toolchain): $NPM_DEV_TXT" >> "$SUMMARY"
    )
  fi
fi

# --- Telemetry manifest check ---
if [ -f "$ROOT/frontend/package.json" ]; then
  if grep -Eiq 'posthog|segment|sentry|mixpanel|amplitude|@sentry|firebase|bugsnag|datadog|hotjar|fullstory|google-analytics' \
      "$ROOT/frontend/package.json"; then
    audit_warn "frontend/package.json matches telemetry SDK name pattern — review manually"
    echo "telemetry-manifest-check: REVIEW" >> "$SUMMARY"
    [ "$STRICT" -eq 1 ] && EXIT_CODE=1
  else
    echo "telemetry-manifest-check: PASS (no known SDK names in package.json)" >> "$SUMMARY"
  fi
fi

{
  echo
  echo "Reports directory: $REPORT_DIR"
} >> "$SUMMARY"

audit_log "Summary written to $SUMMARY"
if [ "$EXIT_CODE" -ne 0 ] && [ "$STRICT" -eq 1 ]; then
  audit_fail "Audit failed (--audit-strict). Fix issues or re-run with --skip-audit."
fi
exit "$EXIT_CODE"
