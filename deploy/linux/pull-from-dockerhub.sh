#!/usr/bin/env bash
# Pull sakura-backend from Docker Hub (SAKURA_BACKEND_IMAGE in .env).
#
# Usage:
#   export DOCKERHUB_USERNAME=sriabhi001
#   export DOCKERHUB_TOKEN=dckr_pat_...   # required for private repos
#   bash deploy/linux/pull-from-dockerhub.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

[ -f .env ] || { echo "[error] .env missing" >&2; exit 1; }

IMAGE="$(grep -E '^\s*SAKURA_BACKEND_IMAGE=' .env | head -1 | cut -d= -f2- | tr -d '\r' | xargs)"
[ -n "$IMAGE" ] || { echo "[error] SAKURA_BACKEND_IMAGE not set in .env" >&2; exit 1; }

if [ -n "${DOCKERHUB_TOKEN:-}" ] && [ -n "${DOCKERHUB_USERNAME:-}" ]; then
  echo "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin
fi

echo "[dockerhub] Pulling $IMAGE ..."
docker pull "$IMAGE"

echo "[dockerhub] Ready — start with: docker compose up -d --no-build"
