#!/usr/bin/env bash
# Run OWASP Dependency-Check against the backend (offline-capable when DB is cached).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REPORT_DIR="$ROOT/reports/security"
mkdir -p "$REPORT_DIR"

docker run --rm \
  -v "$ROOT/backend:/src:ro" \
  -v "$REPORT_DIR:/report" \
  -v dependency-check-data:/usr/share/dependency-check/data \
  owasp/dependency-check:latest \
  --scan /src \
  --project Sakura \
  --format HTML \
  --format JSON \
  --out /report \
  --noupdate

echo "[ok] Reports written to $REPORT_DIR"
