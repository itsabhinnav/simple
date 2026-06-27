#!/usr/bin/env bash
# Install Docker Engine + Compose plugin on common Linux distros.
# Run with sudo or as root. Re-login (or newgrp docker) after install.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "[error] Run as root: sudo $0" >&2
  exit 1
fi

log()  { printf '[install-docker] %s\n' "$*"; }
warn() { printf '[install-docker] WARN: %s\n' "$*" >&2; }

detect_os() {
  if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    printf '%s' "${ID:-unknown}"
    return
  fi
  printf 'unknown'
}

OS="$(detect_os)"
log "Detected OS: $OS"

install_debian() {
  apt-get update -qq
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
    curl -fsSL https://download.docker.com/linux/"$OS"/gpg \
      | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
  fi
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/$OS \
    $(. /etc/os-release && echo "${VERSION_CODENAME:-stable}") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

install_rhel() {
  if command -v dnf >/dev/null 2>&1; then PKG=dnf; else PKG=yum; fi
  $PKG install -y yum-utils
  $PKG config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
  $PKG install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
}

case "$OS" in
  debian|ubuntu)
    install_debian
    ;;
  rhel|centos|rocky|almalinux|fedora)
    install_rhel
    ;;
  *)
    warn "Unsupported distro '$OS'. Install Docker manually: https://docs.docker.com/engine/install/"
    exit 1
    ;;
esac

systemctl enable docker 2>/dev/null || true
systemctl start docker 2>/dev/null || true

INVOKER="${SUDO_USER:-${USER:-}}"
if [ -n "$INVOKER" ] && [ "$INVOKER" != "root" ]; then
  if getent group docker >/dev/null 2>&1; then
    usermod -aG docker "$INVOKER" 2>/dev/null || true
    log "Added user '$INVOKER' to the docker group — log out and back in to use docker without sudo."
  fi
fi

docker --version
docker compose version
log "Docker Engine + Compose plugin installed."
