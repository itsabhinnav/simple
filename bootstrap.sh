#!/usr/bin/env bash
# Sakura Docker bootstrap (Linux/macOS) — interactive LAN deployment wizard.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "--- Sakura Docker Bootstrap (Linux) ---"
echo "[info] Ops helpers: deploy/linux/docker-stack.sh, deploy/linux/prerequisites.sh"

command -v docker >/dev/null 2>&1 || { echo "[error] docker is required." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "[error] docker daemon is not responding." >&2; exit 1; }

if docker compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker-compose)
else
  echo "[error] docker compose is required." >&2
  exit 1
fi

# shellcheck source=scripts/setup-wizard.sh
source "$ROOT_DIR/scripts/setup-wizard.sh"

RECONFIGURE=0
if [ -f .env ]; then
  read -r -p "Existing .env found. Reconfigure? [y/N] " ans
  case "$ans" in [yY]*) RECONFIGURE=1 ;; esac
fi

if [ ! -f .env ] || [ "$RECONFIGURE" -eq 1 ]; then
  if run_sakura_setup_wizard; then
    write_sakura_env_file "$ROOT_DIR/.env"
    if [ "$SAKURA_WIZ_DOCKER" -ne 1 ]; then
      echo "[info] Native mode selected — run ./setup.sh instead for venv build."
      exit 0
    fi
  else
    exit 0
  fi
else
  echo "[info] Using existing .env (re-run and choose reconfigure to change)."
  SAKURA_WIZ_LAN_IP=$(_detect_lan_ip)
  SAKURA_WIZ_PROFILES=""
fi

if [ -x deploy/lan/scripts/generate-tls.sh ]; then
  bash deploy/lan/scripts/generate-tls.sh "$SAKURA_WIZ_LAN_IP"
fi

echo "[info] Building and starting Sakura stack ..."
profile_args=()
for p in ${SAKURA_WIZ_PROFILES:-}; do
  profile_args+=(--profile "$p")
done
"${DOCKER_COMPOSE[@]}" "${profile_args[@]}" up -d --build

echo ""
echo "--- Deployment Complete ---"
echo "  URL: https://${SAKURA_WIZ_LAN_IP}/"
echo "  API: https://${SAKURA_WIZ_LAN_IP}/api/"
echo "---------------------------"
