#!/usr/bin/env bash
# =============================================================================
# Sakura - one-shot setup & launch script (Linux / macOS).
#
# What it does:
#  1. Verifies Python 3.10+ and Node 18+ are present.
#  2. Creates/refreshes a Python virtualenv at .venv and installs backend deps.
#  3. Installs frontend deps with npm ci (or npm install on first run).
#  4. Builds the Angular app in production mode (static, no SSR) and copies the
#     bundle to backend/static so Flask serves it on the same origin as /api.
#  5. Materialises .env from .env.example with freshly generated secrets if no
#     .env exists yet.
#  6. Starts the backend via backend/run_server.py (Gunicorn under the hood).
#
# Re-running the script is safe: it skips work that is already done unless the
# inputs change. Pass --no-start to perform setup only.
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

START_AFTER_SETUP=1
SKIP_FRONTEND_INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --no-start)             START_AFTER_SETUP=0 ;;
    --skip-frontend-install) SKIP_FRONTEND_INSTALL=1 ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

log()  { printf '\033[1;36m[sakura]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[sakura]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[sakura]\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Dependency checks
# ---------------------------------------------------------------------------
need_cmd() { command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }
need_cmd python3
need_cmd node
need_cmd npm

py_major=$(python3 -c 'import sys;print(sys.version_info.major)')
py_minor=$(python3 -c 'import sys;print(sys.version_info.minor)')
if [ "$py_major" -lt 3 ] || { [ "$py_major" -eq 3 ] && [ "$py_minor" -lt 10 ]; }; then
  die "Python 3.10+ required, found ${py_major}.${py_minor}"
fi

node_major=$(node -p 'process.versions.node.split(".")[0]')
if [ "$node_major" -lt 18 ]; then
  die "Node.js 18+ required, found $(node --version)"
fi

# ---------------------------------------------------------------------------
# 2. Python virtualenv
# ---------------------------------------------------------------------------
VENV_DIR="$ROOT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
  log "Creating Python virtualenv at .venv"
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

log "Installing backend Python dependencies"
python -m pip install --upgrade pip setuptools wheel >/dev/null
python -m pip install -r backend/requirements.txt

# ---------------------------------------------------------------------------
# 3. Frontend deps + build
# ---------------------------------------------------------------------------
if [ "$SKIP_FRONTEND_INSTALL" -eq 0 ]; then
  if [ -f frontend/package-lock.json ] && [ -d frontend/node_modules ]; then
    log "Skipping npm install (node_modules already present; pass --skip-frontend-install to never re-check)"
  else
    log "Installing frontend npm dependencies"
    (cd frontend && (npm ci || npm install))
  fi
fi

log "Building Angular frontend (production, static SPA)"
(cd frontend && npm run build)

STATIC_DIR="backend/static"
log "Publishing frontend bundle to $STATIC_DIR"
rm -rf "$STATIC_DIR"
mkdir -p "$STATIC_DIR"
cp -R frontend/dist/frontend/browser/. "$STATIC_DIR/"
if [ ! -s "$STATIC_DIR/index.html" ] && [ -f "$STATIC_DIR/index.csr.html" ]; then
  cp "$STATIC_DIR/index.csr.html" "$STATIC_DIR/index.html"
fi

# ---------------------------------------------------------------------------
# 4. .env bootstrap
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    log "Creating .env from .env.example with freshly generated secrets"
    JWT_SECRET=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))")
    ENC_KEY=$(python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
    sed -e "s|^JWT_SECRET_KEY=.*$|JWT_SECRET_KEY=${JWT_SECRET}|" \
        -e "s|^ENCRYPTION_KEY=.*$|ENCRYPTION_KEY=${ENC_KEY}|" \
        .env.example > .env
  else
    warn ".env.example missing; .env was not created"
  fi
fi

log "Setup complete"

# ---------------------------------------------------------------------------
# 5. Launch
# ---------------------------------------------------------------------------
if [ "$START_AFTER_SETUP" -eq 1 ]; then
  HOST_DEFAULT="0.0.0.0"
  PORT_DEFAULT="5000"
  log "Starting backend on ${HOST:-$HOST_DEFAULT}:${PORT:-$PORT_DEFAULT}"
  exec python backend/run_server.py
else
  log "Skipping launch (--no-start). Start manually with: python backend/run_server.py"
fi
