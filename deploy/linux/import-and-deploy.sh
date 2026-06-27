#!/usr/bin/env bash
# Load pre-built Sakura Docker images and start the LAN stack (Option A).
# No git, npm, or Python required on this host.
#
# Usage (inside unzipped release bundle):
#   cp .env.example .env    # fill JWT_SECRET_KEY + ENCRYPTION_KEY
#   bash deploy/linux/import-and-deploy.sh
#   bash deploy/linux/import-and-deploy.sh --lan-ip 192.168.1.50
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

LAN_IP=""
while [ $# -gt 0 ]; do
  case "$1" in
    --lan-ip) LAN_IP="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,10p' "$0"
      exit 0
      ;;
    *) echo "[error] Unknown argument: $1" >&2; exit 1 ;;
  esac
done

IMAGES_TAR="$ROOT/sakura-images.tar"
[ -f "$IMAGES_TAR" ] || { echo "[error] sakura-images.tar not found in $ROOT" >&2; exit 1; }

[ -f .env ] || {
  echo "[error] .env missing. Copy .env.example to .env and set JWT_SECRET_KEY + ENCRYPTION_KEY." >&2
  exit 1
}
grep -q '^JWT_SECRET_KEY=.\+' .env || { echo "[error] JWT_SECRET_KEY empty in .env" >&2; exit 1; }
grep -q '^ENCRYPTION_KEY=.\+' .env || { echo "[error] ENCRYPTION_KEY empty in .env" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || { echo "[error] docker not installed" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "[error] docker daemon not running" >&2; exit 1; }

echo "[import] Loading images from sakura-images.tar ..."
docker load -i "$IMAGES_TAR"

if [ -z "$LAN_IP" ]; then
  LAN_IP="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -Ev '^(169\.254\.|127\.)' | head -n 1 || true)"
fi
LAN_IP="${LAN_IP:-localhost}"

if [ ! -f deploy/lan/nginx/certs/sakura.crt ]; then
  echo "[import] Generating self-signed TLS for $LAN_IP ..."
  bash deploy/lan/scripts/generate-tls.sh "$LAN_IP"
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
else
  COMPOSE=(docker-compose)
fi

echo "[import] Starting stack (no rebuild) ..."
"${COMPOSE[@]}" up -d --no-build

echo "[import] Waiting for health ..."
for i in $(seq 1 30); do
  code="$(curl -k -s -o /dev/null -w '%{http_code}' "https://127.0.0.1/health" 2>/dev/null || true)"
  if [ "$code" = "200" ]; then
    echo "[ok] Sakura is up — https://${LAN_IP}/"
    exit 0
  fi
  sleep 3
done

echo "[warn] Health check did not pass yet. Inspect: docker compose logs backend nginx" >&2
exit 1
