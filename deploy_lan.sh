#!/bin/bash

# Sakura LAN Deployment Script for Linux
# This script sets up a secure production environment on a local LAN.

set -e

echo "--- Sakura LAN Deployment (Linux) ---"

# 1. Check for Dependencies
if ! [ -x "$(command -v docker)" ]; then
  echo "Error: docker is not installed." >&2
  exit 1
fi

if ! [ -x "$(command -v docker-compose)" ]; then
  if ! docker compose version > /dev/null 2>&1; then
    echo "Error: docker-compose is not installed." >&2
    exit 1
  fi
  DOCKER_COMPOSE="docker compose"
else
  DOCKER_COMPOSE="docker-compose"
fi

# 2. Get Local LAN IP
LOCAL_IP=$(hostname -I | awk '{print $1}')
echo "[INFO] Detected Local LAN IP: $LOCAL_IP"

# 3. Setup Environment Variables
if [ ! -f .env ]; then
  echo "[INFO] Generating secure keys and .env file..."
  
  # Generate keys using python (since it's a dependency for backend anyway)
  JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
  ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "manual-encryption-key-required-32chars")
  
  cat <<EOF > .env
ENVIRONMENT=production
JWT_SECRET_KEY=$JWT_SECRET
ENCRYPTION_KEY=$ENCRYPTION_KEY
ALLOWED_ORIGINS=http://$LOCAL_IP,http://localhost
FORCE_HTTPS=false
EOF
  echo "[INFO] .env file created with secure keys."
else
  echo "[INFO] Using existing .env file."
fi

# 4. Configure Firewall (UFW)
if [ -x "$(command -v ufw)" ]; then
  echo "[INFO] Configuring UFW firewall for port 80..."
  sudo ufw allow 80/tcp comment 'Sakura Frontend'
  # Port 5000 is internal to docker, no need to expose on host unless desired.
fi

# 5. Launch Application
echo "[INFO] Building and starting Sakura stack..."
$DOCKER_COMPOSE up -d --build

echo ""
echo "--- Deployment Complete ---"
echo "Sakura is now accessible on your LAN at:"
echo "URL: http://$LOCAL_IP"
echo "---------------------------"
