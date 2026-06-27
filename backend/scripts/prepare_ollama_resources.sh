#!/usr/bin/env bash
# Vendor ollama binary + model blobs into backend/resources/ollama for offline use.
# Linux equivalent of prepare_ollama_resources.ps1.
#
# Usage:
#   ./backend/scripts/prepare_ollama_resources.sh
#   OLLAMA_EXE=/usr/local/bin/ollama MODELS=qwen2.5vl:7b ./backend/scripts/prepare_ollama_resources.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="${OUT_DIR:-$BACKEND_ROOT/resources/ollama}"
MODELS="${MODELS:-qwen2.5vl:7b,qwen2.5vl:3b}"
OLLAMA_EXE="${OLLAMA_EXE:-}"

if [ -z "$OLLAMA_EXE" ]; then
  OLLAMA_EXE="$(command -v ollama 2>/dev/null || true)"
fi
[ -n "$OLLAMA_EXE" ] && [ -x "$OLLAMA_EXE" ] || {
  echo "[error] ollama not found. Install from https://ollama.com/download/linux or set OLLAMA_EXE." >&2
  exit 1
}

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

export OLLAMA_MODELS="$STAGE/models"
mkdir -p "$OUT_DIR/models"

IFS=',' read -ra TAGS <<< "$MODELS"
for tag in "${TAGS[@]}"; do
  tag="$(echo "$tag" | xargs)"
  [ -n "$tag" ] || continue
  echo "[info] Pulling $tag ..."
  "$OLLAMA_EXE" pull "$tag"
done

echo "[info] Copying ollama binary and models to $OUT_DIR"
mkdir -p "$OUT_DIR"
cp -f "$OLLAMA_EXE" "$OUT_DIR/ollama"
chmod +x "$OUT_DIR/ollama"
cp -a "$STAGE/models/." "$OUT_DIR/models/"

echo "[ok] Ollama resources staged under $OUT_DIR"
