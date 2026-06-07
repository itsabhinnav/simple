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
INSECURE_SSL=0
CLEAN_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --no-start)              START_AFTER_SETUP=0 ;;
    --skip-frontend-install) SKIP_FRONTEND_INSTALL=1 ;;
    # Corporate MITM proxies often present a self-signed cert. --insecure-ssl
    # tells pip to add bootstrap-pypa hosts to --trusted-host and tells npm
    # to disable strict-ssl + Node TLS verification for this run.
    --insecure-ssl)          INSECURE_SSL=1 ;;
    # Force a clean Angular build by removing dist/ and the Angular cache.
    --clean-build)           CLEAN_BUILD=1 ;;
    -h|--help)
      sed -n '2,22p' "$0"
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
# 0b. Optional: SSL trust bypass for MITM proxies
# ---------------------------------------------------------------------------
PIP_INSECURE_ARGS=()
if [ "$INSECURE_SSL" -eq 1 ]; then
  warn "--insecure-ssl enabled: skipping TLS verification for pip + npm (corporate MITM mode)"
  PIP_INSECURE_ARGS=(
    --trusted-host pypi.org
    --trusted-host pypi.python.org
    --trusted-host files.pythonhosted.org
    --trusted-host bootstrap.pypa.io
  )
  export NODE_TLS_REJECT_UNAUTHORIZED=0
  export NPM_CONFIG_STRICT_SSL=false
fi

# ---------------------------------------------------------------------------
# 0c. Port preflight (non-fatal)
# ---------------------------------------------------------------------------
PORT_CHECK="${PORT:-5000}"
port_in_use() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :$PORT_CHECK )" 2>/dev/null | tail -n +2 | grep -q .
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$PORT_CHECK" -sTCP:LISTEN >/dev/null 2>&1
  elif command -v netstat >/dev/null 2>&1; then
    netstat -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$PORT_CHECK\$"
  else
    return 1
  fi
}
if port_in_use; then
  warn "Port $PORT_CHECK is already in use; the backend will fail to bind."
  warn "  -> Stop the other process or run with: PORT=<free port> ./setup.sh"
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
python -m pip "${PIP_PROXY_ARGS[@]}" "${PIP_INSECURE_ARGS[@]}" install --upgrade pip setuptools wheel >/dev/null
if ! python -m pip "${PIP_PROXY_ARGS[@]}" "${PIP_INSECURE_ARGS[@]}" install -r backend/requirements.txt; then
  # The strict pin set can fail on Python versions for which one of the
  # packages has no prebuilt wheel. Retry with --prefer-binary, and as a
  # last resort install one package at a time so the offender is named.
  warn "Initial pip install failed; retrying with --prefer-binary"
  if ! python -m pip "${PIP_PROXY_ARGS[@]}" "${PIP_INSECURE_ARGS[@]}" install --prefer-binary --upgrade -r backend/requirements.txt; then
    warn "Bulk install still failing; trying package-by-package to surface the culprit"
    failed=()
    while IFS= read -r line; do
      pkg="${line%%#*}"
      pkg="${pkg##* }"
      pkg="${pkg// /}"
      [ -z "$pkg" ] && continue
      if ! python -m pip "${PIP_PROXY_ARGS[@]}" "${PIP_INSECURE_ARGS[@]}" install --prefer-binary "$line"; then
        failed+=("$line")
      fi
    done < <(grep -v '^[[:space:]]*#' backend/requirements.txt | sed '/^[[:space:]]*$/d')
    if [ "${#failed[@]}" -gt 0 ]; then
      printf '\n[sakura] Failed to install: %s\n' "${failed[*]}"
      printf '[sakura] Your Python (%s.%s) has no prebuilt wheel for one of these.\n' "$py_major" "$py_minor"
      printf '[sakura] Fix options:\n'
      printf '  * Install Python 3.10/3.11/3.12 alongside the current one and re-run setup.sh with that interpreter on PATH.\n'
      printf '  * Edit backend/requirements.txt to drop the lower bound on the failing package.\n'
      exit 1
    fi
  fi
fi

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

if [ "$CLEAN_BUILD" -eq 1 ]; then
  log "Cleaning previous Angular build artefacts (frontend/dist + .angular/cache)"
  rm -rf frontend/dist frontend/.angular/cache 2>/dev/null || true
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
    # .env carries JWT signing keys and the Fernet encryption key for stored
    # Git tokens. Lock it down so other users on the host cannot read it.
    chmod 600 .env 2>/dev/null || true
  else
    warn ".env.example missing; .env was not created"
  fi
fi

log "Setup complete"

# ---------------------------------------------------------------------------
# 4b. Optional runtime deps (Smart Import + local VLM)
# ---------------------------------------------------------------------------
# The Smart Import wizard's hybrid parser uses LibreOffice (soffice) + Poppler
# (pdftoppm) to render Excel/Word pages into PNG snapshots for the VLM. The
# in-app assistant talks to a local Ollama daemon. Both are OPTIONAL — when
# missing, parsing falls back to deterministic-only and the assistant
# degrades gracefully — but probing here lets the operator know what they're
# giving up.
if ! command -v soffice >/dev/null 2>&1; then
  warn "LibreOffice ('soffice') not on PATH — Smart Import will run without page snapshots."
  warn "  Install: sudo apt-get install -y libreoffice-core libreoffice-calc libreoffice-writer (Debian/Ubuntu)"
fi
if ! command -v pdftoppm >/dev/null 2>&1; then
  warn "Poppler ('pdftoppm') not on PATH — needed alongside LibreOffice for visual previews."
  warn "  Install: sudo apt-get install -y poppler-utils"
fi
if ! command -v ollama >/dev/null 2>&1 && [ ! -f "$ROOT_DIR/backend/resources/ollama/ollama" ]; then
  warn "Ollama not detected — in-app assistant VLM features will be unavailable."
  warn "  Install: https://ollama.com/download, then pre-pull a model (qwen2.5vl:7b)."
fi

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
