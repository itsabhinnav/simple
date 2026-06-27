#!/usr/bin/env bash
# Manage the Sakura Docker LAN stack on Linux.
#
# Usage:
#   ./deploy/linux/docker-stack.sh up [--build] [--profile NAME ...]
#   ./deploy/linux/docker-stack.sh down
#   ./deploy/linux/docker-stack.sh restart
#   ./deploy/linux/docker-stack.sh logs [service]
#   ./deploy/linux/docker-stack.sh status
#   ./deploy/linux/docker-stack.sh health
#   ./deploy/linux/docker-stack.sh rebuild
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

log()  { printf '[docker-stack] %s\n' "$*"; }
die()  { printf '[docker-stack] %s\n' "$*" >&2; exit 1; }

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  die "docker compose is required. Run: sudo deploy/linux/install-docker.sh"
fi

[ -f .env ] || die ".env missing — run ./bootstrap.sh or copy .env.example and fill secrets."

profile_args=()
collect_profiles() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --profile) profile_args+=(--profile "$2"); shift 2 ;;
      *) break ;;
    esac
  done
}

cmd="${1:-status}"
shift || true

case "$cmd" in
  up)
    build=0
    while [ $# -gt 0 ]; do
      case "$1" in
        --build) build=1; shift ;;
        --profile) profile_args+=(--profile "$2"); shift 2 ;;
        *) die "Unknown option: $1" ;;
      esac
    done
    if [ ! -f deploy/lan/nginx/certs/sakura.crt ]; then
      log "TLS certs missing — generating self-signed material"
      bash deploy/lan/scripts/generate-tls.sh
    fi
    up_args=(-d)
    [ "$build" -eq 1 ] && up_args+=(--build)
    "${COMPOSE[@]}" "${profile_args[@]}" up "${up_args[@]}"
    log "Stack started. Run: $0 health"
    ;;
  down)
    "${COMPOSE[@]}" "${profile_args[@]}" down
    ;;
  restart)
    "${COMPOSE[@]}" "${profile_args[@]}" restart
    ;;
  logs)
    svc="${1:-}"
    if [ -n "$svc" ]; then
      "${COMPOSE[@]}" logs -f "$svc"
    else
      "${COMPOSE[@]}" logs -f
    fi
    ;;
  status|ps)
    "${COMPOSE[@]}" ps
    ;;
  health)
    code="$(curl -k -s -o /dev/null -w '%{http_code}' https://127.0.0.1/health 2>/dev/null || true)"
    if [ "$code" = "200" ]; then
      log "Health OK (https://127.0.0.1/health -> $code)"
      exit 0
    fi
    code80="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/health 2>/dev/null || true)"
    if [ "$code80" = "200" ]; then
      log "Health OK via HTTP redirect path (http://127.0.0.1/health -> $code80)"
      exit 0
    fi
    die "Health check failed (HTTPS=$code HTTP=$code80). Check: $0 logs backend"
    ;;
  rebuild)
    collect_profiles "$@"
    "${COMPOSE[@]}" "${profile_args[@]}" build --no-cache
    "${COMPOSE[@]}" "${profile_args[@]}" up -d
    ;;
  *)
    die "Unknown command: $cmd (try: up|down|restart|logs|status|health|rebuild)"
    ;;
esac
