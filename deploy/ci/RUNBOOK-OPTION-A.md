# Option A — Pre-built images (developer builds on Windows + Docker)

**You receive:** `sakura-docker-release-<version>.zip` from the Sakura developer.

**You need on the Linux LAN server:** Docker Engine + Compose only. No git, Python, Node, npm, pip, or registry access at deploy time.

**Restricted / filtered internet:** This bundle is the correct path when the LAN server cannot reach Docker Hub, npm, or PyPI. All libraries are already inside the images. CI only runs `docker load` + `docker compose up --no-build`.

---

## What is in the zip

| File / folder | Purpose |
|---------------|---------|
| `sakura-images.tar` | Pre-built `sakura-backend`, `nginx`, `redis` images |
| `docker-compose.yml` | Stack definition |
| `deploy/` | nginx config, TLS scripts, ops helpers |
| `.env.example` | Template — copy to `.env` and fill secrets |
| `RELEASE.txt` | Version + build metadata |

---

## Deploy steps (Linux LAN server)

```bash
# 1. Unzip the release
unzip sakura-docker-release-*.zip -d /opt/sakura
cd /opt/sakura/sakura-docker-release-*

# 2. Create secrets (generate on THIS server — do not reuse dev secrets)
cp .env.example .env
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(48))"
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
# Paste output into .env; also set ALLOWED_ORIGINS=https://<your-lan-hostname>
chmod 600 .env

# 3. Load images and start
bash deploy/linux/import-and-deploy.sh --lan-ip <server-lan-ip>

# 4. Verify
bash deploy/linux/docker-stack.sh health
curl -k https://127.0.0.1/health
```

**URL:** `https://<lan-ip>/`

---

## Restricted network / blocked registries

Use this table when the Linux host has limited or filtered internet:

| Step | Needs outbound internet? | Notes |
|------|--------------------------|-------|
| Install Docker (one-time) | Maybe | Use internal mirror or offline `.deb`/`.rpm` packages from your platform team |
| Unzip release | No | Copy via USB, SFTP, or internal file share |
| `docker load` | **No** | Images are in `sakura-images.tar` |
| `docker compose up --no-build` | **No** | No pulls, no npm, no pip |
| Generate TLS (`generate-tls.sh`) | No | Needs `openssl` only (usually preinstalled) |
| Generate `.env` secrets | No* | `python3` one-liners below, or ask developer to pre-generate |

\*If `python3` is not installed and cannot be added, generate secrets on any trusted admin machine and paste into `.env`:

```bash
# JWT (any machine with openssl)
echo "JWT_SECRET_KEY=$(openssl rand -base64 48 | tr -d '/+=' | head -c 64)"

# ENCRYPTION_KEY — use python3 once on a machine that has cryptography,
# or ask the Sakura developer to include two values in a sealed envelope
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

**Runtime egress:** The app runs with `ENABLE_NETWORK_RESTRICTIONS=strict` — containers do not call external APIs. Blocked outbound traffic from the server is expected and OK after deploy.

**Do NOT use Option B (build on server)** when npm, pip, apt, or Docker Hub are blocked — the build will fail. Ask the developer for Option A instead.

---

## Day-2 operations

```bash
bash deploy/linux/docker-stack.sh status
bash deploy/linux/docker-stack.sh logs backend
bash deploy/linux/docker-stack.sh down
bash deploy/linux/docker-stack.sh restart
```

---

## Updating to a new release

1. Stop: `docker compose down`
2. Unzip new release (or replace `sakura-images.tar` + `RELEASE.txt`)
3. `docker load -i sakura-images.tar`
4. `docker compose up -d --no-build`

Data persists in Docker volumes `sakura-data`, `sakura-uploads`, `sakura-redis`.

---

## Optional profiles

Only use these if the developer included IAM images (`-IncludeIamProfile` when building the zip):

```bash
docker compose --profile iam up -d --no-build          # Keycloak — set KEYCLOAK_ADMIN_PASSWORD in .env first
docker compose --profile edge-auth up -d --no-build    # Authelia
```

If profiles were not bundled, `docker compose` will try to pull from quay.io/docker.io and **will fail** on blocked networks.

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| `sakura-images.tar not found` | Run from inside the unzipped release directory |
| Health check fails | `docker compose logs backend nginx` |
| Wrong architecture | Ask developer to rebuild with `-Platform linux/amd64` or `linux/arm64` matching `uname -m` |
| TLS browser warning | Expected with self-signed certs; replace `deploy/lan/nginx/certs/` with internal CA certs |

---

## Developer builds this zip (Windows + Docker Desktop)

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\build-and-export.ps1 -Version 1.2.0
# Output: dist\release\sakura-docker-release-1.2.0.zip
```

Docker Desktop must be running in **Linux containers** mode.
