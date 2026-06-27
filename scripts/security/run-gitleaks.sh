#!/usr/bin/env bash
# Scan the repository for accidentally committed secrets (Gitleaks).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

docker run --rm \
  -v "$ROOT:/repo:ro" \
  -v "$ROOT/.gitleaks.toml:/config.toml:ro" \
  zricethezav/gitleaks:latest \
  detect --source /repo --config /config.toml --verbose

echo "[ok] No secrets detected"
