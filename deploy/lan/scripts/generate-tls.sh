#!/usr/bin/env bash
# Generate a self-signed TLS certificate for the LAN nginx reverse proxy.
# Replace with certificates from your internal CA for production deployments.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CERT_DIR="$ROOT/deploy/lan/nginx/certs"
LAN_IP="${1:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
LAN_IP="${LAN_IP:-localhost}"

mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 825 -newkey rsa:4096 \
  -keyout "$CERT_DIR/sakura.key" \
  -out "$CERT_DIR/sakura.crt" \
  -subj "/CN=Sakura/O=Enterprise LAN/C=XX" \
  -addext "subjectAltName=DNS:localhost,DNS:sakura,DNS:sakura.local,IP:127.0.0.1,IP:${LAN_IP}"

chmod 600 "$CERT_DIR/sakura.key"
echo "[ok] TLS material written to $CERT_DIR (SAN includes $LAN_IP)"
