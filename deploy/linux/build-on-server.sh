#!/usr/bin/env bash
# Build Sakura Docker images on the Linux LAN host and start the stack (Option B).
# CI drops the source release zip here; no Flask/Angular knowledge required.
#
# Usage (inside unzipped source release):
#   cp .env.example .env    # fill JWT_SECRET_KEY + ENCRYPTION_KEY
#   bash deploy/linux/build-on-server.sh
#   bash deploy/linux/build-on-server.sh --lan-ip 192.168.1.50
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

[ -f Dockerfile.unified ] || { echo "[error] Dockerfile.unified missing — use full source release zip" >&2; exit 1; }
[ -f .env ] || {
  echo "[error] .env missing. Copy .env.example to .env and set JWT_SECRET_KEY + ENCRYPTION_KEY." >&2
  exit 1
}
grep -q '^JWT_SECRET_KEY=.\+' .env || { echo "[error] JWT_SECRET_KEY empty in .env" >&2; exit 1; }
grep -q '^ENCRYPTION_KEY=.\+' .env || { echo "[error] ENCRYPTION_KEY empty in .env" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || { echo "[error] docker not installed — run: sudo deploy/linux/install-docker.sh" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "[error] docker daemon not running" >&2; exit 1; }

if [ -z "$LAN_IP" ]; then
  LAN_IP="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -Ev '^(169\.254\.|127\.)' | head -n 1 || true)"
fi
LAN_IP="${LAN_IP:-localhost}"

if [ ! -f deploy/lan/nginx/certs/sakura.crt ]; then
  echo "[build] Generating self-signed TLS for $LAN_IP ..."
  bash deploy/lan/scripts/generate-tls.sh "$LAN_IP"
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
else
  COMPOSE=(docker-compose)
fi

echo "[build] Building images (requires outbound network for base images + npm/pip) ..."
"${COMPOSE[@]}" build

echo "[build] Starting stack ..."
"${COMPOSE[@]}" up -d

echo "[build] Waiting for health ..."
for i in $(seq 1 60); do
  code="$(curl -k -s -o /dev/null -w '%{http_code}' "https://127.0.0.1/health" 2>/dev/null || true)"
  if [ "$code" = "200" ]; then
    echo "[ok] Sakura is up — https://${LAN_IP}/"
    exit 0
  fi
  sleep 5
done

echo "[warn] Health check did not pass yet. Inspect: docker compose logs backend nginx" >&2
exit 1
