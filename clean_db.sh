#!/usr/bin/env bash
# =============================================================================
# Sakura - reset the local SQLite database.
#
# Removes the runtime database artefacts produced by the backend so the next
# server start brings up an empty, freshly initialised schema. The Flask app
# rebuilds the table layout via HybridDatabaseService on startup and
# re-provisions the master admin from .env, so there is no separate
# "re-init" step.
#
# The legacy --with-remote flag was removed: the remote/Git database mirror
# was deleted, and backend/data/remote/* no longer exists.
#
# By default only the SQLite primary DB + the RAG vector sidecar are removed.
# Pass --with-uploads to also delete uploaded spec files.
#
# Usage:
#   ./clean_db.sh
#   ./clean_db.sh --force
#   ./clean_db.sh --with-uploads
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

log()  { printf '\033[1;36m[sakura]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[sakura]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[sakura]\033[0m %s\n' "$*" >&2; exit 1; }

FORCE=0
WITH_UPLOADS=0
for arg in "$@"; do
  case "$arg" in
    -f|--force)        FORCE=1 ;;
    --with-uploads)    WITH_UPLOADS=1 ;;
    --with-remote)     warn "--with-remote is a no-op (remote/Git sync was removed)." ;;
    -h|--help)         sed -n '2,22p' "$0"; exit 0 ;;
    *) die "Unknown argument: $arg" ;;
  esac
done

LOCAL_DIR="$ROOT_DIR/backend/data/local/dev/database"
LOCAL_DB="$LOCAL_DIR/sakura_db.db"
VECTOR_DIR="$ROOT_DIR/backend/data/local/dev/vectors"
UPLOADS_DIR="$ROOT_DIR/backend/uploads"

targets=()
[ -f "$LOCAL_DB" ] && targets+=("$LOCAL_DB")
for side in sakura_db.db-wal sakura_db.db-shm sakura_db.db-journal; do
  [ -f "$LOCAL_DIR/$side" ] && targets+=("$LOCAL_DIR/$side")
done
# RAG vector index sidecar (sqlite-vec). Rebuilt automatically by the live
# indexer on the next start once it sees database_metadata.version bump.
if [ -d "$VECTOR_DIR" ]; then
  for vec in sakura_vec.db sakura_vec.db-wal sakura_vec.db-shm sakura_vec.db-journal; do
    [ -f "$VECTOR_DIR/$vec" ] && targets+=("$VECTOR_DIR/$vec")
  done
fi
[ "$WITH_UPLOADS" -eq 1 ] && [ -d "$UPLOADS_DIR" ] && targets+=("$UPLOADS_DIR")

if [ "${#targets[@]}" -eq 0 ]; then
  log "Nothing to clean. Local DB and selected optional paths are already absent."
  exit 0
fi

log "The following paths will be removed:"
for t in "${targets[@]}"; do
  size=$(du -sh "$t" 2>/dev/null | awk '{print $1}')
  printf '  - %s   (%s)\n' "$t" "${size:-?}"
done

[ "$WITH_UPLOADS" -eq 0 ] && warn "Pass --with-uploads to also delete backend/uploads (uploaded spec files)."

if [ "$FORCE" -eq 0 ]; then
  read -r -p "Type 'DELETE' to confirm: " resp
  if [ "$resp" != "DELETE" ]; then
    warn "Aborted."
    exit 1
  fi
fi

for t in "${targets[@]}"; do
  if rm -rf -- "$t"; then
    log "Removed $t"
  else
    warn "Failed to remove $t"
  fi
done

log "Database cleaned. Start the server (./start.sh) - the schema will be"
log "recreated, the master admin (.env) re-provisioned, and the RAG vector"
log "index rebuilt automatically by the live indexer."
