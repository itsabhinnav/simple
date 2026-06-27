#!/usr/bin/env bash
# Host-level egress firewall for a Sakura LAN server (Linux).
# Drops all outbound traffic except RFC-1918 + loopback.
# Run as root after verifying internal subnet below matches your LAN.
set -euo pipefail

LAN_CIDR="${SAKURA_LAN_CIDR:-192.168.0.0/16}"
LOOPBACK="127.0.0.0/8"

echo "[info] Applying OUTPUT rules: allow $LAN_CIDR + $LOOPBACK, drop everything else"

iptables -C OUTPUT -d "$LOOPBACK" -j ACCEPT 2>/dev/null || iptables -A OUTPUT -d "$LOOPBACK" -j ACCEPT
iptables -C OUTPUT -d "$LAN_CIDR" -j ACCEPT 2>/dev/null || iptables -A OUTPUT -d "$LAN_CIDR" -j ACCEPT
iptables -C OUTPUT -d 10.0.0.0/8 -j ACCEPT 2>/dev/null || iptables -A OUTPUT -d 10.0.0.0/8 -j ACCEPT
iptables -C OUTPUT -d 172.16.0.0/12 -j ACCEPT 2>/dev/null || iptables -A OUTPUT -d 172.16.0.0/12 -j ACCEPT
iptables -C OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null \
  || iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -C OUTPUT -j DROP 2>/dev/null || iptables -A OUTPUT -j DROP

echo "[ok] Host egress locked to private ranges. Verify with: iptables -L OUTPUT -n -v"
