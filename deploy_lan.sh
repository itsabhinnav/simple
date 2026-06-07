#!/usr/bin/env bash
# =============================================================================
# Sakura LAN Deployment (Linux / macOS)
#
# Brings up the unified single-image stack (Flask backend + bundled Angular
# SPA served on the same port) on the host's primary LAN interface so other
# machines on the network can reach it at http://<lan-ip>:5000/.
#
# Differences vs. the old split-image deployment:
#   * No separate Nginx container — the Flask app serves the SPA itself.
#   * No port 80 hop — there is a single listener on PORT (default 5000).
#   * No Postgres profile — local-only SQLite is the only supported mode.
# =============================================================================
set -euo pipefail

echo "--- Sakura LAN Deployment (Linux/macOS) ---"

# ---------------------------------------------------------------------------
# 1. Dependency probes
# ---------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || { echo "[error] docker is required." >&2; exit 1; }
docker info >/dev/null 2>&1       || { echo "[error] docker daemon is not responding." >&2; exit 1; }

if docker compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker-compose)
else
  echo "[error] docker compose plugin or docker-compose v1 is required." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. LAN IP detection
# ---------------------------------------------------------------------------
LOCAL_IP=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -Ev '^(169\.254\.|127\.|::1$)' | head -n 1)
[ -z "${LOCAL_IP:-}" ] && LOCAL_IP="localhost"
PORT_BIND="${PORT:-5000}"
echo "[info] Detected LAN IP : $LOCAL_IP"
echo "[info] Host port       : $PORT_BIND"

# ---------------------------------------------------------------------------
# 3. .env bootstrap with freshly generated secrets
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
  echo "[info] Generating secure keys + .env ..."
  JWT_SECRET=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))" 2>/dev/null \
               || openssl rand -base64 48)
  ENCRYPTION_KEY=$(python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())" 2>/dev/null \
                   || openssl rand -base64 32)

  cat > .env <<EOF
ENVIRONMENT=production
FLASK_ENV=production
HOST=0.0.0.0
PORT=$PORT_BIND
JWT_SECRET_KEY=$JWT_SECRET
ENCRYPTION_KEY=$ENCRYPTION_KEY
ALLOWED_ORIGINS=http://$LOCAL_IP:$PORT_BIND,http://localhost:$PORT_BIND
FORCE_HTTPS=false
# LAN deployment: relax the loopback-only restrictor so RFC-1918 peers can hit the API.
ENABLE_NETWORK_RESTRICTIONS=allow_lan
# AI assistant defaults — keep external providers off; bundle a local Ollama
# if you want VLM (see backend/scripts/prepare_ollama_resources.ps1).
SAKURA_LLM_ALLOW_EXTERNAL=false
SAKURA_LLM_ALLOW_REMOTE_OLLAMA=false
SAKURA_DISABLE_OLLAMA_SIDECAR=true
SAKURA_DISABLE_LIVE_INDEXER=false
EOF
  chmod 600 .env 2>/dev/null || true
  echo "[ok] .env created."
else
  echo "[info] Using existing .env file."
fi

# ---------------------------------------------------------------------------
# 4. Firewall (best-effort)
# ---------------------------------------------------------------------------
if command -v ufw >/dev/null 2>&1; then
  echo "[info] Opening UFW port $PORT_BIND/tcp for Sakura ..."
  sudo ufw allow "$PORT_BIND/tcp" comment 'Sakura' || true
fi

# ---------------------------------------------------------------------------
# 5. Build + launch
# ---------------------------------------------------------------------------
echo "[info] Building and starting Sakura unified stack ..."
"${DOCKER_COMPOSE[@]}" up -d --build

cat <<EOF

--- Deployment Complete ---
Sakura (frontend + API) is now serving on:
  URL: http://$LOCAL_IP:$PORT_BIND/
  API: http://$LOCAL_IP:$PORT_BIND/api/
---------------------------
EOF
