# Pull sakura-backend from GHCR (set SAKURA_BACKEND_IMAGE in .env).
#
# Usage:
#   export GHCR_USER=... GHCR_TOKEN=...   # read:packages for private images
#   bash deploy/linux/pull-from-ghcr.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

[ -f .env ] || { echo "[error] .env missing" >&2; exit 1; }

IMAGE="$(grep -E '^\s*SAKURA_BACKEND_IMAGE=' .env | head -1 | cut -d= -f2- | tr -d '\r' | xargs)"
[ -n "$IMAGE" ] || { echo "[error] SAKURA_BACKEND_IMAGE not set in .env" >&2; exit 1; }

if [ -n "${GHCR_TOKEN:-}" ] && [ -n "${GHCR_USER:-}" ]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
fi

echo "[ghcr] Pulling $IMAGE ..."
docker pull "$IMAGE"

echo "[ghcr] Image ready — start with: docker compose up -d --no-build"
echo "[ghcr] (nginx/redis still from Docker Hub unless you use the release zip for offline)"
