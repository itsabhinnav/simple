# Option B — Source release (CI builds on Linux Docker host)

> **Not suitable** when the Linux host blocks Docker Hub, npm, PyPI, or apt mirrors. Use **Option A** (pre-built image zip) instead.

**You receive:** `sakura-source-release-<version>.zip` from the Sakura developer.

**You need on the Linux LAN server:** Docker Engine + Compose + **outbound network at build time** (pulls base images, npm, pip).

No Flask or Angular knowledge required — only Docker.

---

## What is in the zip

| File / folder | Purpose |
|---------------|---------|
| `Dockerfile.unified` | Multi-stage build (frontend + backend → one image) |
| `docker-compose.yml` | Stack definition |
| `backend/`, `frontend/` | Source used only inside `docker build` |
| `deploy/` | nginx config, TLS scripts, ops helpers |
| `.env.example` | Template for runtime secrets |
| `RELEASE.txt` | Version metadata |

---

## Deploy steps (Linux LAN server)

```bash
# 1. Unzip
unzip sakura-source-release-*.zip -d /opt/sakura
cd /opt/sakura/sakura-source-release-*

# 2. Secrets on this server
cp .env.example .env
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(48))"
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
# Paste into .env; set ALLOWED_ORIGINS=https://<your-lan-hostname>
chmod 600 .env

# 3. Build + start (10–20 min first time depending on network)
bash deploy/linux/build-on-server.sh --lan-ip <server-lan-ip>

# 4. Verify
bash deploy/linux/docker-stack.sh health
```

**URL:** `https://<lan-ip>/`

---

## Alternative: clone from git instead of zip

If your pipeline prefers git tags:

```bash
git clone <repo-url> && cd Simple
git checkout v1.2.0
cp .env.example .env   # fill secrets
bash deploy/linux/build-on-server.sh --lan-ip <ip>
```

Same Docker commands — the zip is just a frozen snapshot without git access.

---

## Day-2 operations

Same as Option A — use `deploy/linux/docker-stack.sh`.

---

## Updating

```bash
docker compose down
# unzip new release OR git pull + checkout new tag
bash deploy/linux/build-on-server.sh --lan-ip <ip>
```

Rebuild pulls fresh base layers; allow egress during build.

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| Build fails on npm/pip | Check proxy: set `HTTP_PROXY` / `HTTPS_PROXY` in environment before build (see COMMANDS.md) |
| Out of disk | Need ~2 GB free for build |
| Health check fails | `docker compose logs backend` — first boot runs DB migration |

---

## Developer packs this zip (Windows, no Docker)

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\pack-source-release.ps1 -Version 1.2.0
# Output: dist\release\sakura-source-release-1.2.0.zip
```

Or CI checks out the git tag directly — no zip needed.
