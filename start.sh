#!/usr/bin/env bash
# =============================================================================
# Sakura - launch the backend (no install, no build).
#
# Use this AFTER setup.sh has run at least once. It only:
#  1. Verifies the .venv exists.
#  2. Verifies the Angular bundle has been published to backend/static.
#  3. Starts backend/run_server.py via the venv Python.
#
# Re-run setup.sh instead if you changed code or dependencies.
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

log()  { printf '\033[1;36m[sakura]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[sakura]\033[0m %s\n' "$*" >&2; exit 1; }

VENV_PY="$ROOT_DIR/.venv/bin/python"
[ -x "$VENV_PY" ] || die "Virtualenv not found at .venv. Run ./setup.sh first."

[ -f "$ROOT_DIR/backend/static/index.html" ] \
  || die "Frontend bundle not found at backend/static/index.html. Run ./setup.sh first."

log "Starting backend on ${HOST:-0.0.0.0}:${PORT:-5000}"
exec "$VENV_PY" backend/run_server.py
