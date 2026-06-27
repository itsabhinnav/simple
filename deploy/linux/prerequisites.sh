#!/usr/bin/env bash
# Verify a Linux host is ready to run the Sakura Docker stack.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ok=0
warn=0
fail=0

pass() { printf '  [ok]   %s\n' "$*"; ok=$((ok + 1)); }
note() { printf '  [warn] %s\n' "$*"; warn=$((warn + 1)); }
bad()  { printf '  [fail] %s\n' "$*"; fail=$((fail + 1)); }

printf '=== Sakura Linux Docker prerequisites ===\n\n'

if command -v docker >/dev/null 2>&1; then
  pass "docker CLI found ($(docker --version 2>/dev/null | head -1))"
else
  bad "docker CLI missing — run: sudo deploy/linux/install-docker.sh"
fi

if docker info >/dev/null 2>&1; then
  pass "docker daemon responding"
else
  bad "docker daemon not reachable (start with: sudo systemctl start docker)"
fi

if docker compose version >/dev/null 2>&1; then
  pass "docker compose plugin found"
elif command -v docker-compose >/dev/null 2>&1; then
  pass "docker-compose standalone found"
else
  bad "docker compose missing"
fi

if command -v openssl >/dev/null 2>&1; then
  pass "openssl found (TLS cert generation)"
else
  note "openssl missing — install: sudo apt-get install -y openssl"
fi

if [ -f .env ]; then
  pass ".env present"
  grep -q '^JWT_SECRET_KEY=.\+' .env 2>/dev/null && pass "JWT_SECRET_KEY set" || bad "JWT_SECRET_KEY empty in .env"
  grep -q '^ENCRYPTION_KEY=.\+' .env 2>/dev/null && pass "ENCRYPTION_KEY set" || bad "ENCRYPTION_KEY empty in .env"
else
  note ".env missing — run ./bootstrap.sh or ./deploy/linux/deploy.sh"
fi

if [ -f deploy/lan/nginx/certs/sakura.crt ]; then
  pass "TLS cert deploy/lan/nginx/certs/sakura.crt"
else
  note "TLS cert missing — run: deploy/lan/scripts/generate-tls.sh"
fi

free_kb="$(df -k "$ROOT" 2>/dev/null | awk 'NR==2 {print $4}')"
if [ -n "${free_kb:-}" ] && [ "$free_kb" -lt 2097152 ]; then
  note "Less than 2 GB free disk — image build may fail"
else
  pass "Sufficient disk space for build"
fi

mem_kb="$(grep MemAvailable /proc/meminfo 2>/dev/null | awk '{print $2}')"
if [ -n "${mem_kb:-}" ] && [ "$mem_kb" -lt 2097152 ]; then
  note "Less than 2 GB RAM available — build may be slow"
else
  pass "Memory looks adequate"
fi

printf '\nSummary: %s ok, %s warn, %s fail\n' "$ok" "$warn" "$fail"
[ "$fail" -eq 0 ]
