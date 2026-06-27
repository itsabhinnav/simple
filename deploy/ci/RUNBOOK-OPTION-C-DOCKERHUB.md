# Option C — Docker Hub deploy (minimal zip, no source code)

**You receive:** `sakura-hub-deploy-<version>.zip` from the Sakura developer.

**App image:** [hub.docker.com/r/sriabhi001/simple](https://hub.docker.com/r/sriabhi001/simple) (`sriabhi001/simple:latest`)

**You need on the Linux LAN server:** Docker Engine + Compose, outbound access to `registry-1.docker.io` at deploy time, and secrets in `.env`.

**You do NOT need:** git clone, Python, Node, npm, pip, or Sakura source code.

---

## What is in the zip

| File / folder | Purpose |
|---------------|---------|
| `docker-compose.yml` | nginx + redis + backend wiring |
| `.env.example` | Copy to `.env` — fill secrets + `SAKURA_BACKEND_IMAGE` |
| `deploy/lan/nginx/` | nginx config + empty `certs/` |
| `deploy/lan/scripts/generate-tls.sh` | Self-signed TLS (replace with CA certs in production) |
| `deploy/linux/pull-from-dockerhub.sh` | Pull backend image from Hub |
| `deploy/linux/deploy-from-dockerhub.sh` | One-shot: TLS → pull → start |
| `deploy/linux/docker-stack.sh` | Health / logs / status |
| `RELEASE.txt` | Version metadata |

---

## Deploy steps (Linux LAN server)

```bash
# 1. Unzip
unzip sakura-hub-deploy-*.zip -d /opt/sakura
cd /opt/sakura/sakura-hub-deploy-*

# 2. Secrets (generate on THIS server)
cp .env.example .env
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(48))"
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
# Paste into .env. Also set:
#   SAKURA_BACKEND_IMAGE=sriabhi001/simple:latest
#   ALLOWED_ORIGINS=https://<your-lan-hostname-or-ip>
chmod 600 .env

# 3. Deploy (replace LAN IP)
bash deploy/linux/deploy-from-dockerhub.sh --lan-ip 10.0.1.50

# 4. Verify
bash deploy/linux/docker-stack.sh health
curl -k https://127.0.0.1/health
```

**URL:** `https://<lan-ip>/`

**First admin:** `docker compose exec backend cat /app/data/admin-credentials.txt` (delete file after saving password).

---

## Manual steps (equivalent)

```bash
bash deploy/lan/scripts/generate-tls.sh <lan-ip>
bash deploy/linux/pull-from-dockerhub.sh
docker compose pull nginx redis
docker compose up -d --no-build
```

---

## Restricted LAN (no Docker Hub)

Use **Option A** (release zip with `sakura-images.tar`) instead — see [RUNBOOK-OPTION-A.md](RUNBOOK-OPTION-A.md).

---

## Updates

```bash
docker pull sriabhi001/simple:latest
docker compose up -d --no-build
```

Pin a tag in `.env` if you need a fixed version: `SAKURA_BACKEND_IMAGE=sriabhi001/simple:v1.0.0`

---

## Developer — create this zip

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\pack-hub-deploy.ps1 -Version 1.0.0
# → dist\release\sakura-hub-deploy-1.0.0.zip
```
