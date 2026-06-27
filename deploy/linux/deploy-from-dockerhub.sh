#!/usr/bin/env bash
# Pull Sakura backend from Docker Hub and start the LAN stack (no local build).
#
# Prerequisites: Docker + Compose, .env with secrets, outbound access to Docker Hub.
#
# Usage:
#   cp .env.example .env   # fill JWT_SECRET_KEY, ENCRYPTION_KEY, ALLOWED_ORIGINS
#   bash deploy/linux/deploy-from-dockerhub.sh
#   bash deploy/linux/deploy-from-dockerhub.sh --lan-ip 10.0.1.50
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

LAN_IP=""
while [ $# -gt 0 ]; do
  case "$1" in
    --lan-ip) LAN_IP="$2"; shift 2 ;;
    *) echo "[error] unknown argument: $1" >&2; exit 1 ;;
  esac
done

[ -f .env ] || { echo "[error] .env missing — copy .env.example and set secrets" >&2; exit 1; }

if grep -qE '^\s*JWT_SECRET_KEY=\s*$' .env || grep -qE '^\s*ENCRYPTION_KEY=\s*$' .env; then
  echo "[error] JWT_SECRET_KEY and ENCRYPTION_KEY must be set in .env" >&2
  exit 1
fi

CERT_DIR="$ROOT/deploy/lan/nginx/certs"
if [ ! -f "$CERT_DIR/sakura.crt" ] || [ ! -f "$CERT_DIR/sakura.key" ]; then
  echo "[tls] Generating self-signed certificate..."
  bash deploy/lan/scripts/generate-tls.sh "${LAN_IP:-127.0.0.1}"
fi

bash deploy/linux/pull-from-dockerhub.sh

echo "[compose] Pulling nginx + redis..."
docker compose pull nginx redis 2>/dev/null || {
  docker pull nginx:1.27-alpine
  docker pull redis:7-alpine
}

echo "[compose] Starting stack (--no-build)..."
docker compose up -d --no-build

echo "[ok] Stack started. Check: bash deploy/linux/docker-stack.sh health"
echo "[ok] Open: https://${LAN_IP:-127.0.0.1}/"
