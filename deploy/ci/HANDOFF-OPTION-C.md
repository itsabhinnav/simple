# Option C — Docker Hub minimal handoff

Minimal CI deploy: **no git clone, no source code, no local build** — only compose/nginx/scripts + pull from Docker Hub.

**App image:** [hub.docker.com/r/sriabhi001/simple](https://hub.docker.com/r/sriabhi001/simple)

Full runbook: [RUNBOOK-OPTION-C-DOCKERHUB.md](RUNBOOK-OPTION-C-DOCKERHUB.md)

---

## Create the zip (developer — Windows)

```powershell
cd C:\workspace\sources\Simple
powershell -ExecutionPolicy Bypass -File deploy\windows\pack-hub-deploy.ps1 -Version 1.0.0
```

Output: `dist\release\sakura-hub-deploy-1.0.0.zip` (~12 KB)

---

## Give CI

1. **`sakura-hub-deploy-1.0.0.zip`**
2. **Hub link:** https://hub.docker.com/r/sriabhi001/simple
3. **Runbook:** `deploy/ci/RUNBOOK-OPTION-C-DOCKERHUB.md` (inside the zip)

---

## CI steps (Linux)

```bash
unzip sakura-hub-deploy-*.zip -d /opt/sakura && cd /opt/sakura/sakura-hub-deploy-*
cp .env.example .env   # JWT_SECRET_KEY, ENCRYPTION_KEY, ALLOWED_ORIGINS
bash deploy/linux/deploy-from-dockerhub.sh --lan-ip <server-ip>
```

Set in `.env` before deploy:

```env
SAKURA_BACKEND_IMAGE=sriabhi001/simple:latest
JWT_SECRET_KEY=<generate on server>
ENCRYPTION_KEY=<generate on server>
ALLOWED_ORIGINS=https://<server-ip-or-hostname>
```

Generate secrets:

```bash
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(48))"
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

Verify:

```bash
bash deploy/linux/docker-stack.sh health
curl -k https://127.0.0.1/health
```

Open: `https://<server-ip>/`

First admin credentials:

```bash
docker compose exec backend cat /app/data/admin-credentials.txt
```

---

## Updates

```bash
docker pull sriabhi001/simple:latest
docker compose up -d --no-build
```

---

## When not to use Option C

If the LAN server **cannot reach Docker Hub** at deploy time, use **Option A** (pre-built image tar in zip) — see [RUNBOOK-OPTION-A.md](RUNBOOK-OPTION-A.md).
