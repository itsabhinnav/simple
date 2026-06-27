#!/usr/bin/env bash
# One-shot Linux Docker LAN deployment for Sakura.
#
# Prerequisites: Docker Engine + Compose (see install-docker.sh).
#
# Usage:
#   ./deploy/linux/deploy.sh              # interactive wizard (bootstrap)
#   ./deploy/linux/deploy.sh --quick      # use existing .env, build + start
#   ./deploy/linux/deploy.sh --lan-ip IP  # regenerate TLS SAN for IP
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

QUICK=0
LAN_IP=""

while [ $# -gt 0 ]; do
  case "$1" in
    --quick) QUICK=1; shift ;;
    --lan-ip) LAN_IP="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "[error] Unknown argument: $1" >&2; exit 1 ;;
  esac
done

command -v docker >/dev/null 2>&1 || {
  echo "[error] Docker not found. Install with: sudo deploy/linux/install-docker.sh" >&2
  exit 1
}
docker info >/dev/null 2>&1 || {
  echo "[error] Docker daemon not running. Start with: sudo systemctl start docker" >&2
  exit 1
}

if [ "$QUICK" -eq 0 ]; then
  exec "$ROOT/bootstrap.sh"
fi

[ -f .env ] || {
  echo "[error] .env missing. Run without --quick or copy .env.example." >&2
  exit 1
}

if [ -z "$LAN_IP" ]; then
  LAN_IP="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -Ev '^(169\.254\.|127\.)' | head -n 1 || true)"
fi
LAN_IP="${LAN_IP:-localhost}"

bash deploy/lan/scripts/generate-tls.sh "$LAN_IP"
exec bash deploy/linux/docker-stack.sh up --build
