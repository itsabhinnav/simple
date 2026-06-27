# New Windows PC — after git clone

Use this guide when you clone the Sakura repo on a fresh Windows machine (developer build box or CI prep workstation).

For the full command reference see [`COMMANDS.md`](../../COMMANDS.md). For Linux CI deploy see [`deploy/ci/RUNBOOK-OPTION-A.md`](../ci/RUNBOOK-OPTION-A.md).

---

## Prerequisites (install once)

| Tool | Required for | Notes |
|------|--------------|-------|
| **Git** | Clone | Already used |
| **Docker Desktop** | Docker LAN build + test | **Linux containers** mode (default). Start Docker before any compose command. |
| **Python 3.10+** | `.env` secret generation, optional native dev | Not required for Docker-only workflow |
| **Node.js 18+** | Optional native frontend dev | Not required for Docker-only workflow |

Corporate network: set `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` before build if Docker/npm/pip need a proxy.

---

## 1. Clone the repository

```powershell
git clone <your-remote-url>
cd Simple
```

---

## 2. Create local secrets (not in git)

`.env` is never committed. Create it on every new machine:

```powershell
copy .env.example .env
```

Generate values and paste into `.env`:

```powershell
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

Also set:

```env
ALLOWED_ORIGINS=https://localhost
ENVIRONMENT=production
ENABLE_NETWORK_RESTRICTIONS=strict
SAKURA_REQUIRE_AUTH=true
```

---

## 3. Generate TLS certificates (nginx)

Required before the Docker stack can serve HTTPS:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\lan\scripts\generate-tls.ps1 127.0.0.1
```

Writes `deploy\lan\nginx\certs\sakura.crt` and `sakura.key`. Uses Docker `alpine/openssl` when local openssl is missing.

**Browser warning on https://127.0.0.1/** is expected (self-signed). For production LAN, replace these files with your internal CA certificates.

---

## 4. Build, test, and run (Docker — recommended)

One command builds the **linux/amd64** image (same image for Docker Desktop on Windows and the Linux LAN server), starts the stack, and checks health:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\build-and-test.ps1 -Version 1.0.0
```

Open: **https://127.0.0.1/**

First boot creates a master admin — credentials are written inside the backend container at `/app/data/admin-credentials.txt`:

```powershell
docker compose exec backend cat /app/data/admin-credentials.txt
```

Delete that file after saving the password to your password manager.

---

## 5. Export release zip for CI (Linux LAN server)

When the stack is healthy, package pre-built images for ops (no npm/pip/Docker Hub needed on the LAN host at deploy time):

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\build-and-export.ps1 -Version 1.0.0
```

Output:

```
dist\release\sakura-docker-release-1.0.0.zip
```

Hand to CI with [`deploy/ci/RUNBOOK-OPTION-A.md`](../ci/RUNBOOK-OPTION-A.md).

### Option: Docker Hub (CI publishes automatically)

Repository: [hub.docker.com/r/sriabhi001/simple](https://hub.docker.com/r/sriabhi001/simple)

```env
SAKURA_BACKEND_IMAGE=sriabhi001/simple:latest
```

```powershell
docker pull sriabhi001/simple:latest
docker compose up -d --no-build
```

CI setup: add `DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN` secrets — see [`deploy/registry/DOCKERHUB.md`](../registry/DOCKERHUB.md).

### Option: GitHub Container Registry (alternative)

**Do not put images in git.** Push to GHCR (same image for Windows Docker Desktop and Linux):

```env
# .env — lowercase path matching your GitHub org/repo
SAKURA_BACKEND_IMAGE=ghcr.io/your-org/simple:latest
```

```powershell
$env:GHCR_USER = "your-github-username"
$env:GHCR_TOKEN = "ghp_..."   # PAT: write:packages
powershell -ExecutionPolicy Bypass -File deploy\windows\push-to-ghcr.ps1 -Tag 1.0.0
```

On another machine after clone:

```powershell
$env:GHCR_TOKEN = "ghp_..."   # read:packages
powershell -ExecutionPolicy Bypass -File deploy\windows\pull-from-ghcr.ps1
docker compose up -d --no-build
```

Full guide: [`deploy/registry/GHCR.md`](../registry/GHCR.md). CI also pushes on every `main` merge.

Optional IAM images (Keycloak + Authelia) in release zip:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\build-and-export.ps1 -Version 1.0.0 -IncludeIamProfile
```

---

## 6. Day-2 Docker commands

```powershell
docker compose ps
docker compose logs -f backend
docker compose restart
docker compose down                 # stop — data volumes kept
docker compose up -d --no-build      # start again
```

| Command | Data |
|---------|------|
| `docker compose down` | **Keeps** DB, uploads, Redis data |
| `docker compose down -v` | **Wipes** all volumes — do not use in production |

Data persists in volumes: `simple_sakura-data`, `simple_sakura-uploads`, `simple_sakura-redis`.

---

## Alternative: native dev (no Docker)

For backend/frontend code changes with hot reload:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -AuditStrict
```

- Backend: `http://127.0.0.1:5000/`
- Frontend (second terminal): `cd frontend` → `npm run dev` → `http://localhost:4200`

---

## Alternative: interactive wizard

Same as bootstrap — walks through Docker LAN vs native:

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1
```

---

## What is not in git (create on each PC)

| Item | How |
|------|-----|
| `.env` | Copy from `.env.example`, fill secrets |
| `deploy/lan/nginx/certs/*` | `generate-tls.ps1` |
| `dist/release/*.zip` | `build-and-export.ps1` |
| Docker volumes | Created on first `docker compose up` |
| `.venv/`, `node_modules/` | Created by `setup.ps1` if using native path |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Docker daemon not running` | Start Docker Desktop, wait until ready |
| nginx restart loop | Run `generate-tls.ps1` — certs missing |
| `Not secure` in browser | Normal for self-signed certs; use internal CA in production |
| Port 80/443 in use | Set `NGINX_HTTP_PORT` / `NGINX_HTTPS_PORT` in `.env` |
| Build fails behind proxy | Set `HTTP_PROXY` / `HTTPS_PROXY` env vars, rebuild |
| Health check fails | `docker compose logs backend nginx` |

---

## Quick copy-paste (shortest path)

```powershell
git clone <url>
cd Simple
copy .env.example .env
# fill JWT_SECRET_KEY + ENCRYPTION_KEY in .env
powershell -ExecutionPolicy Bypass -File deploy\windows\build-and-test.ps1 -Version 1.0.0
```
