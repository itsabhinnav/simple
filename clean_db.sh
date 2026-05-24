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
# By default only the SQLite database files are removed. Pass flags to also
# delete the cloned Git workspace and/or uploaded spec files.
#
# Usage:
#   ./clean_db.sh
#   ./clean_db.sh --force
#   ./clean_db.sh --with-remote --with-uploads
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

log()  { printf '\033[1;36m[sakura]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[sakura]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[sakura]\033[0m %s\n' "$*" >&2; exit 1; }

FORCE=0
WITH_REMOTE=0
WITH_UPLOADS=0
for arg in "$@"; do
  case "$arg" in
    -f|--force)        FORCE=1 ;;
    --with-remote)     WITH_REMOTE=1 ;;
    --with-uploads)    WITH_UPLOADS=1 ;;
    -h|--help)         sed -n '2,18p' "$0"; exit 0 ;;
    *) die "Unknown argument: $arg" ;;
  esac
done

LOCAL_DB="$ROOT_DIR/backend/data/local/dev/database/sakura_db.db"
LOCAL_DIR="$ROOT_DIR/backend/data/local/dev/database"
REMOTE_DIR="$ROOT_DIR/backend/data/remote/dev"
UPLOADS_DIR="$ROOT_DIR/backend/uploads"

targets=()
[ -f "$LOCAL_DB" ] && targets+=("$LOCAL_DB")
for side in sakura_db.db-wal sakura_db.db-shm sakura_db.db-journal; do
  [ -f "$LOCAL_DIR/$side" ] && targets+=("$LOCAL_DIR/$side")
done
[ "$WITH_REMOTE" -eq 1 ] && [ -d "$REMOTE_DIR" ] && targets+=("$REMOTE_DIR")
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

[ "$WITH_REMOTE"  -eq 0 ] && warn "Pass --with-remote to also delete backend/data/remote/dev (Git workspace)."
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
log "recreated and the master admin (.env) will be re-provisioned automatically."
