#!/usr/bin/env bash
# Sakura interactive setup wizard (bash).
# Source from setup.sh / bootstrap.sh:
#   source "$ROOT_DIR/scripts/setup-wizard.sh"
#   run_sakura_setup_wizard

_wizard_step() {
  local n="$1" total="$2" title="$3"
  printf '\n[%s/%s] %s\n' "$n" "$total" "$title"
  printf '%.0s-' {1..60}; printf '\n'
}

_wizard_choice() {
  local prompt="$1" default="$2"
  shift 2
  local options=("$@")
  local i choice
  for i in "${!options[@]}"; do
    local mark=""
    [ "$i" -eq "$default" ] && mark=" (default)"
    printf '  %s) %s%s\n' "$((i + 1))" "${options[$i]}" "$mark"
  done
  read -r -p "$prompt " choice
  if [ -z "$choice" ]; then echo "$default"; return; fi
  if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#options[@]}" ]; then
    echo "$((choice - 1))"
    return
  fi
  printf '[sakura] Invalid choice — using default.\n' >&2
  echo "$default"
}

_wizard_yesno() {
  local prompt="$1" default="$2" raw hint
  if [ "$default" = "1" ]; then hint="Y/n"; else hint="y/N"; fi
  read -r -p "$prompt [$hint] " raw
  if [ -z "$raw" ]; then [ "$default" = "1" ] && return 0 || return 1; fi
  [[ "$raw" =~ ^[Yy] ]]
}

_detect_lan_ip() {
  local ip
  ip=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -Ev '^(169\.254\.|127\.|::1$)' | head -n 1)
  [ -n "$ip" ] && printf '%s' "$ip" || printf 'localhost'
}

_new_sakura_secrets() {
  python3 -c "import secrets;print(secrets.token_urlsafe(48))" 2>/dev/null \
    || openssl rand -base64 48
}

_new_encryption_key() {
  python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())" 2>/dev/null \
    || openssl rand -base64 32
}

# Populates global wizard result variables (prefixed SAKURA_WIZ_).
run_sakura_setup_wizard() {
  local total=7
  printf '\n=== Sakura Setup Wizard ===\n'
  printf 'Answer each step; press Enter to accept the default.\n'

  _wizard_step 1 "$total" "Deployment mode"
  local mode_idx
  mode_idx=$(_wizard_choice "Select deployment" 1 \
    "Native — Python venv on this machine (dev / single-user)" \
    "Docker LAN — nginx TLS + isolated container network (enterprise)")
  SAKURA_WIZ_DOCKER=0
  [ "$mode_idx" -eq 1 ] && SAKURA_WIZ_DOCKER=1

  _wizard_step 2 "$total" "Network exposure"
  local bind_idx host_bind="127.0.0.1" lan_expose=0
  if [ "$SAKURA_WIZ_DOCKER" -eq 1 ]; then
    bind_idx=$(_wizard_choice "Who should reach Sakura?" 0 \
      "LAN clients via nginx HTTPS (recommended)" \
      "This machine only (localhost)")
    [ "$bind_idx" -eq 0 ] && lan_expose=1
    host_bind="0.0.0.0"
  else
    bind_idx=$(_wizard_choice "Bind address" 0 \
      "Localhost only (127.0.0.1 — safest for dev)" \
      "All interfaces (0.0.0.0 — reachable on LAN)")
    [ "$bind_idx" -eq 1 ] && { host_bind="0.0.0.0"; lan_expose=1; }
  fi

  _wizard_step 3 "$total" "Security posture"
  local restrict_idx restrictor="strict"
  restrict_idx=$(_wizard_choice "Outbound network restrictor" 0 \
    "strict — loopback only (recommended for on-prem)" \
    "allow_lan — RFC-1918 private ranges (requires explicit opt-in at boot)")
  [ "$restrict_idx" -eq 1 ] && restrictor="allow_lan"

  local require_auth=1 force_https=0
  _wizard_yesno "Require JWT on all /api/* routes?" 1 || require_auth=0
  if [ "$SAKURA_WIZ_DOCKER" -eq 1 ]; then
    force_https=1
  else
    _wizard_yesno "Enable FORCE_HTTPS (use with reverse proxy)?" 0 && force_https=1
  fi

  _wizard_step 4 "$total" "TLS / ports"
  SAKURA_WIZ_LAN_IP=$(_detect_lan_ip)
  local port="5000" https_port="443" http_port="80"
  if [ "$SAKURA_WIZ_DOCKER" -eq 1 ]; then
    read -r -p "HTTPS port [443]: " https_port
    https_port="${https_port:-443}"
    read -r -p "HTTP redirect port [80]: " http_port
    http_port="${http_port:-80}"
    port="$https_port"
  else
    read -r -p "Backend port [5000]: " port
    port="${port:-5000}"
  fi

  _wizard_step 5 "$total" "Optional features"
  local observability=1 ollama_sidecar=0 live_indexer=1
  _wizard_yesno "Enable local API observability (admin dashboard, no cloud)?" 1 || observability=0
  if [ "$SAKURA_WIZ_DOCKER" -eq 1 ]; then
    _wizard_yesno "Enable in-container Ollama sidecar? (requires model blobs)" 0 && ollama_sidecar=1
  else
    _wizard_yesno "Try to start bundled/local Ollama for the assistant?" 0 && ollama_sidecar=1
  fi
  _wizard_yesno "Enable RAG live indexer background thread?" 1 || live_indexer=0

  SAKURA_WIZ_PROFILES=""
  if [ "$SAKURA_WIZ_DOCKER" -eq 1 ]; then
    _wizard_step 6 "$total" "Docker IAM profiles (optional)"
    _wizard_yesno "Enable Keycloak IAM profile (--profile iam)?" 0 && SAKURA_WIZ_PROFILES="${SAKURA_WIZ_PROFILES} iam"
    _wizard_yesno "Enable Authelia edge-auth profile (--profile edge-auth)?" 0 && SAKURA_WIZ_PROFILES="${SAKURA_WIZ_PROFILES} edge-auth"
  else
    _wizard_step 6 "$total" "Docker IAM profiles"
    printf '  Skipped (native deployment).\n'
  fi

  _wizard_step 7 "$total" "Confirm"
  local jwt enc origins origins_line
  jwt=$(_new_sakura_secrets)
  enc=$(_new_encryption_key)

  if [ "$SAKURA_WIZ_DOCKER" -eq 1 ]; then
    if [ "$lan_expose" -eq 1 ]; then
      origins="https://${SAKURA_WIZ_LAN_IP},https://localhost"
    else
      origins="https://localhost"
    fi
  else
    if [ "$lan_expose" -eq 1 ]; then
      origins="http://${SAKURA_WIZ_LAN_IP}:${port},http://localhost:${port}"
    else
      origins="http://localhost:${port}"
    fi
  fi

  printf '  Mode           : %s\n' "$([ "$SAKURA_WIZ_DOCKER" -eq 1 ] && echo 'Docker LAN' || echo 'Native')"
  printf '  LAN IP         : %s\n' "$SAKURA_WIZ_LAN_IP"
  printf '  Restrictor     : %s\n' "$restrictor"
  printf '  Require auth   : %s\n' "$([ "$require_auth" -eq 1 ] && echo true || echo false)"
  if [ "$SAKURA_WIZ_DOCKER" -eq 1 ]; then
    printf '  HTTPS port     : %s\n' "$https_port"
    printf '  Compose profiles:%s\n' "${SAKURA_WIZ_PROFILES:- (none)}"
  else
    printf '  Host:Port      : %s:%s\n' "$host_bind" "$port"
  fi

  _wizard_yesno "Write .env and continue?" 1 || { printf 'Setup cancelled.\n'; return 1; }

  local disable_ollama="true" disable_indexer="false"
  [ "$ollama_sidecar" -eq 1 ] && disable_ollama="false"
  [ "$live_indexer" -eq 0 ] && disable_indexer="true"

  SAKURA_WIZ_ENV_FILE=$(mktemp)
  cat > "$SAKURA_WIZ_ENV_FILE" <<EOF
ENVIRONMENT=production
FLASK_ENV=production
HOST=$host_bind
PORT=$port
JWT_SECRET_KEY=$jwt
ENCRYPTION_KEY=$enc
ALLOWED_ORIGINS=$origins
FORCE_HTTPS=$([ "$force_https" -eq 1 ] && echo true || echo false)
ENABLE_NETWORK_RESTRICTIONS=$restrictor
SAKURA_LLM_ALLOW_EXTERNAL=false
SAKURA_LLM_ALLOW_REMOTE_OLLAMA=false
SAKURA_REQUIRE_AUTH=$([ "$require_auth" -eq 1 ] && echo true || echo false)
SAKURA_ENABLE_OBSERVABILITY=$([ "$observability" -eq 1 ] && echo true || echo false)
SAKURA_DISABLE_OLLAMA_SIDECAR=$disable_ollama
SAKURA_DISABLE_LIVE_INDEXER=$disable_indexer
EOF

  if [ "$SAKURA_WIZ_DOCKER" -eq 1 ]; then
    {
      echo "NGINX_HTTPS_PORT=$https_port"
      echo "NGINX_HTTP_PORT=$http_port"
    } >> "$SAKURA_WIZ_ENV_FILE"
    if [[ "$SAKURA_WIZ_PROFILES" == *iam* ]]; then
      local kc_pass
      read -r -p "Keycloak admin password (KEYCLOAK_ADMIN_PASSWORD): " kc_pass
      kc_pass="${kc_pass:-$(python3 -c "import secrets;print(secrets.token_urlsafe(24))" 2>/dev/null || openssl rand -base64 24)}"
      echo "KEYCLOAK_ADMIN_PASSWORD=$kc_pass" >> "$SAKURA_WIZ_ENV_FILE"
    fi
  fi

  SAKURA_WIZ_HOST=$host_bind
  SAKURA_WIZ_PORT=$port
  SAKURA_WIZ_HTTPS_PORT=$https_port
  SAKURA_WIZ_HTTP_PORT=$http_port
  return 0
}

write_sakura_env_file() {
  local dest="$1" src="${SAKURA_WIZ_ENV_FILE:-}"
  [ -n "$src" ] && [ -f "$src" ] || return 1
  if [ -f "$dest" ]; then
    printf '[sakura] .env exists — wizard will overwrite with new configuration.\n'
  fi
  cp "$src" "$dest"
  chmod 600 "$dest" 2>/dev/null || true
  rm -f "$src"
  printf '[sakura] Wrote %s\n' "$dest"
}
