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
# 0. Corporate proxy detection
# ---------------------------------------------------------------------------
# pip and npm read HTTP_PROXY / HTTPS_PROXY / NO_PROXY env vars when present,
# but expect different casing depending on the tool. Normalise whichever the
# user has set and re-export BOTH upper- and lower-case variants so every
# child process picks them up consistently.
mask_proxy() {
  printf '%s' "$1" | sed -E 's#(://)[^:@/]+:[^@/]+@#\1***:***@#'
}

HTTPS_PROXY="${HTTPS_PROXY:-${https_proxy:-}}"
HTTP_PROXY="${HTTP_PROXY:-${http_proxy:-}}"
NO_PROXY="${NO_PROXY:-${no_proxy:-}}"

if [ -n "$HTTPS_PROXY$HTTP_PROXY" ]; then
  log "Detected corporate proxy:"
  [ -n "$HTTPS_PROXY" ] && log "  HTTPS_PROXY = $(mask_proxy "$HTTPS_PROXY")"
  [ -n "$HTTP_PROXY"  ] && log "  HTTP_PROXY  = $(mask_proxy "$HTTP_PROXY")"
  [ -n "$NO_PROXY"    ] && log "  NO_PROXY    = $NO_PROXY"

  [ -n "$HTTPS_PROXY" ] && export HTTPS_PROXY https_proxy="$HTTPS_PROXY"
  [ -n "$HTTP_PROXY"  ] && export HTTP_PROXY  http_proxy="$HTTP_PROXY"
  [ -n "$NO_PROXY"    ] && export NO_PROXY    no_proxy="$NO_PROXY"
fi

PIP_PROXY_ARGS=()
if [ -n "$HTTPS_PROXY" ]; then PIP_PROXY_ARGS=(--proxy "$HTTPS_PROXY")
elif [ -n "$HTTP_PROXY" ]; then PIP_PROXY_ARGS=(--proxy "$HTTP_PROXY")
fi

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
VENV_PY="$VENV_DIR/bin/python"

if [ ! -x "$VENV_PY" ]; then
  log "Creating Python virtualenv at .venv"
  # --upgrade-deps was added in Python 3.9 and primes the venv with up-to-date
  # pip/setuptools. Fall back to a plain `python3 -m venv` if unsupported.
  python3 -m venv --upgrade-deps "$VENV_DIR" 2>/dev/null \
    || python3 -m venv "$VENV_DIR" \
    || die "Failed to create virtualenv. On Debian/Ubuntu, install python3-venv:\n  sudo apt-get install -y python3-venv"
fi
[ -x "$VENV_PY" ] || die "Virtualenv created but $VENV_PY is missing."

# Some Python distributions ship a venv without pip (most notably Debian-based
# systems before python3-venv is installed). Repair it via ensurepip, falling
# back to get-pip.py from PyPA on the rare systems where ensurepip is absent.
ensure_pip() {
  if "$VENV_PY" -m pip --version >/dev/null 2>&1; then return; fi
  warn "pip is missing from the venv; attempting to bootstrap via ensurepip"
  "$VENV_PY" -m ensurepip --upgrade --default-pip >/dev/null 2>&1 || true
  if "$VENV_PY" -m pip --version >/dev/null 2>&1; then return; fi

  warn "ensurepip failed; downloading get-pip.py from https://bootstrap.pypa.io"
  local tmp curl_proxy wget_proxy
  tmp=$(mktemp -t sakura-get-pip.XXXXXX.py)
  curl_proxy=()
  wget_proxy=()
  if [ -n "$HTTPS_PROXY" ]; then
    curl_proxy=(--proxy "$HTTPS_PROXY")
    wget_proxy=(-e use_proxy=yes -e "https_proxy=$HTTPS_PROXY")
  elif [ -n "$HTTP_PROXY" ]; then
    curl_proxy=(--proxy "$HTTP_PROXY")
    wget_proxy=(-e use_proxy=yes -e "http_proxy=$HTTP_PROXY")
  fi
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "${curl_proxy[@]}" https://bootstrap.pypa.io/get-pip.py -o "$tmp" \
      || { rm -f "$tmp"; die "Could not download get-pip.py. Install pip manually."; }
  elif command -v wget >/dev/null 2>&1; then
    wget -q "${wget_proxy[@]}" https://bootstrap.pypa.io/get-pip.py -O "$tmp" \
      || { rm -f "$tmp"; die "Could not download get-pip.py. Install pip manually."; }
  else
    rm -f "$tmp"; die "Need curl or wget to bootstrap pip."
  fi
  "$VENV_PY" "$tmp" || { rm -f "$tmp"; die "get-pip.py failed."; }
  rm -f "$tmp"
  "$VENV_PY" -m pip --version >/dev/null 2>&1 \
    || die "Bootstrapping pip into the venv failed."
}

ensure_pip

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

log "Installing backend Python dependencies"
python -m pip "${PIP_PROXY_ARGS[@]}" install --upgrade pip setuptools wheel >/dev/null
python -m pip "${PIP_PROXY_ARGS[@]}" install -r backend/requirements.txt

# ---------------------------------------------------------------------------
# 3. Frontend deps + build
# ---------------------------------------------------------------------------
if [ "$SKIP_FRONTEND_INSTALL" -eq 0 ]; then
  # .package-lock.json is written by npm at the end of a successful install,
  # so it is a much better "is this install actually complete?" signal than
  # `-d node_modules` (which is also true for a half-deleted tree).
  if [ -f frontend/package-lock.json ] && [ -f frontend/node_modules/.package-lock.json ]; then
    log "Skipping npm install (node_modules already populated; pass --skip-frontend-install to force-skip)"
  else
    log "Installing frontend npm dependencies"
    if [ -f frontend/package-lock.json ]; then
      (cd frontend && (npm ci || npm install))
    else
      (cd frontend && npm install)
    fi
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
