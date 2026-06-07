#!/bin/bash

# Sakura Unified Bootstrap Script (Linux/macOS)
# This script handles dependency checks, environment setup, building, and startup.

set -e

echo "--- Sakura Unified Bootstrap (Linux/macOS) ---"

# 1. Dependency Checks
command -v docker >/dev/null 2>&1 || { echo "Error: Docker is required. Please install it." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Error: Python 3 is required for initial setup." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "Error: Docker daemon is not responding. Please start Docker and retry." >&2; exit 1; }

if docker compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker-compose)
else
  echo "Error: Docker Compose is required." >&2
  exit 1
fi

# 2. Local IP Detection
LOCAL_IP=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^169\.254\.' | head -n 1)
[ -z "$LOCAL_IP" ] && LOCAL_IP="localhost"
echo "[INFO] Detected Local IP: $LOCAL_IP"

# 3. Environment & Secret Setup
if [ ! -f .env ]; then
  echo "[INFO] Generating secure keys..."
  JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
  ENCRYPTION_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")

  cat <<EOF > .env
ENVIRONMENT=production
FLASK_ENV=production
HOST=0.0.0.0
PORT=5000
JWT_SECRET_KEY=$JWT_SECRET
ENCRYPTION_KEY=$ENCRYPTION_KEY
ALLOWED_ORIGINS=http://$LOCAL_IP:5000,http://localhost:5000
FORCE_HTTPS=false
# strict | allow_lan | off  (off is refused in production)
ENABLE_NETWORK_RESTRICTIONS=strict
# AI assistant — external LLM providers are refused unless flipped on.
SAKURA_LLM_ALLOW_EXTERNAL=false
SAKURA_LLM_ALLOW_REMOTE_OLLAMA=false
# Bundled Ollama daemon (desktop installer only). Containers stay off by default.
SAKURA_DISABLE_OLLAMA_SIDECAR=true
# RAG live indexer thread — disable only when debugging cold-start CPU.
SAKURA_DISABLE_LIVE_INDEXER=false
EOF
  chmod 600 .env 2>/dev/null || true
  echo "[SUCCESS] .env file created."
fi

# 4. Deployment
echo "[INFO] Building and starting Sakura Unified Stack..."
echo "This may take several minutes on first run..."

"${DOCKER_COMPOSE[@]}" up -d --build

echo ""
echo "--- Deployment Complete ---"
echo "Sakura is now served via Flask on:"
echo "URL: http://$LOCAL_IP:5000"
echo "---------------------------"
echo "[HINT] Both frontend and API are now on port 5000."
