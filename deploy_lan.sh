#!/usr/bin/env bash
# Sakura LAN deployment — delegates to the interactive bootstrap wizard.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/bootstrap.sh" "$@"
