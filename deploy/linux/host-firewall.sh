#!/usr/bin/env bash
# Wrapper — apply host egress lock on Linux (see deploy/lan/scripts/host-firewall-linux.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "$ROOT/deploy/lan/scripts/host-firewall-linux.sh" "$@"
