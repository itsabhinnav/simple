# Sakura — scripts & commands

Operational reference for setup, deployment, configuration, and maintenance.
For code layout see [`AGENTS.md`](AGENTS.md).

---

## Quick start

| Goal | Command |
|------|---------|
| **New Windows PC after clone** | [`deploy/windows/NEW-PC-SETUP.md`](deploy/windows/NEW-PC-SETUP.md) |
| First run (interactive wizard) | `./setup.sh` or `.\setup.ps1` |
| Docker LAN (interactive) | `./bootstrap.sh` or `.\bootstrap.ps1` |
| Start again after setup | `./start.sh` or `.\start.ps1` |
| Wipe local SQLite | `./clean_db.sh --force` or `.\clean_db.ps1 -Force` |

If no `.env` exists, `setup.*` offers a **7-step wizard** (deployment mode, network, security, TLS/ports, features, optional IAM, confirm).

---

## Setup scripts

### `setup.sh` / `setup.ps1`

Native install: Python venv, npm build, publish SPA to `backend/static/`, create `.env`, start server.

**Linux / macOS**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows**
```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

| Flag (Bash) | Flag (PowerShell) | Effect |
|-------------|-------------------|--------|
| `--interactive` | `-Interactive` | Force the setup wizard |
| `--non-interactive` | `-NonInteractive` | Skip wizard; use `.env.example` fallback if no `.env` |
| `--no-start` | `-NoStart` | Install + build only; do not launch |
| `--skip-frontend-install` | `-SkipFrontendInstall` | Skip `npm ci` / `npm install` |
| `--insecure-ssl` | `-InsecureSsl` | Trust MITM proxy certs for pip/npm |
| `--clean-build` | `-CleanBuild` | Delete `frontend/dist` and Angular cache before build |
| `--skip-audit` | `-SkipAudit` | Skip post-install pip/npm dependency audit |
| `--audit-strict` | `-AuditStrict` | Fail setup when audit reports vulnerabilities |

**Environment overrides (both platforms)**
```bash
PORT=5050 HOST=127.0.0.1 ./setup.sh
```
```powershell
$env:PORT = "5050"; $env:HOST = "127.0.0.1"; .\setup.ps1
```

**Wizard paths**
- **Native** — continues with venv + npm build; serves at `http://<host>:<port>/`
- **Docker LAN** — writes `.env`, generates TLS certs, runs `docker compose up -d --build`; serves at `https://<lan-ip>/`

Wizard implementation: [`scripts/setup-wizard.sh`](scripts/setup-wizard.sh), [`scripts/setup-wizard.ps1`](scripts/setup-wizard.ps1)

---

### `bootstrap.sh` / `bootstrap.ps1`

Docker-focused interactive wizard. Same 7 steps as setup; defaults to Docker LAN stack (nginx TLS + internal network).

```bash
./bootstrap.sh
```
```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1
```

If `.env` already exists, prompts to reconfigure. Native mode selected in the wizard prints a hint to run `setup.*` instead.

---

### `deploy_lan.sh` / `deploy_lan.ps1`

Thin wrappers — delegate to `bootstrap.*`.

---

### `start.sh` / `start.ps1`

Start the backend only (no install/build). Requires prior successful `setup.*`.

```bash
./start.sh
```
```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Direct equivalent:
```bash
.venv/bin/python backend/run_server.py
```
```powershell
.\.venv\Scripts\python.exe backend\run_server.py
```

---

### `clean_db.sh` / `clean_db.ps1`

Delete local SQLite and sidecar files. **Stop the server first.**

```bash
./clean_db.sh                  # prompts
./clean_db.sh --force
./clean_db.sh --force --with-uploads
```
```powershell
.\clean_db.ps1
.\clean_db.ps1 -Force
.\clean_db.ps1 -Force -WithUploads
```

---

## CI team handoff (developer → ops)

Two supported paths. CI only needs Docker on the **Linux LAN server** — no Flask/Angular skills.

| | Option A — pre-built images | Option B — build on Linux |
|--|----------------------------|---------------------------|
| **Developer machine** | Windows + Docker Desktop | Windows **without** Docker (or any OS) |
| **Developer delivers** | `sakura-docker-release-<ver>.zip` | `sakura-source-release-<ver>.zip` or git tag |
| **Linux server needs internet** | At deploy: **no** (images included) | At **build**: **yes** — blocked registries will fail |
| **Restricted / filtered LAN** | **Use this** | Avoid — needs Docker Hub + npm + pip + apt |
| **CI runbook** | [`deploy/ci/RUNBOOK-OPTION-A.md`](deploy/ci/RUNBOOK-OPTION-A.md) | [`deploy/ci/RUNBOOK-OPTION-B.md`](deploy/ci/RUNBOOK-OPTION-B.md) |
| **CI one-liner** | `bash deploy/linux/import-and-deploy.sh` | `bash deploy/linux/build-on-server.sh` |

**Developer — Option A (build on Windows + Docker):**
```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\build-and-export.ps1 -Version 1.2.0
# → dist\release\sakura-docker-release-1.2.0.zip  (hand to CI)
```

**Developer — Option B (pack source, no Docker on Windows):**
```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\pack-source-release.ps1 -Version 1.2.0
# → dist\release\sakura-source-release-1.2.0.zip  (hand to CI)
```

**CI — after unzip on Linux:** copy `.env.example` → `.env`, fill `JWT_SECRET_KEY` + `ENCRYPTION_KEY`, run the script from the matching runbook.

**Option C — Docker Hub (CI default):** [`deploy/registry/DOCKERHUB.md`](deploy/registry/DOCKERHUB.md) — `sriabhi001/simple:latest`

Pack minimal CI zip (no source): `powershell -ExecutionPolicy Bypass -File deploy\windows\pack-hub-deploy.ps1 -Version 1.0.0` → [`deploy/ci/HANDOFF-OPTION-C.md`](deploy/ci/HANDOFF-OPTION-C.md) | [`deploy/ci/RUNBOOK-OPTION-C-DOCKERHUB.md`](deploy/ci/RUNBOOK-OPTION-C-DOCKERHUB.md)

**Option D — GHCR:** [`deploy/registry/GHCR.md`](deploy/registry/GHCR.md)

---

## Docker

### Stack layout

```
LAN clients → nginx :443 (TLS) → backend :5000 (internal network only)
                                 redis :6379 (internal, Celery broker)
```

Backend is **not** published to the host; only nginx ports `80` / `443` are exposed.

### Compose commands

```bash
# Interactive (recommended)
./bootstrap.sh

# Manual
./deploy/lan/scripts/generate-tls.sh          # self-signed cert → deploy/lan/nginx/certs/
docker compose up -d --build
docker compose logs -f backend
docker compose down
```

**Optional profiles**

| Profile | Adds | Enable |
|---------|------|--------|
| `iam` | Keycloak OIDC | `docker compose --profile iam up -d --build` |
| `edge-auth` | Authelia forward-auth | `docker compose --profile edge-auth up -d --build` |

Set `KEYCLOAK_ADMIN_PASSWORD` in `.env` before using `iam`.

**URLs after deploy**
```
https://<lan-ip>/          UI + API (same origin)
https://<lan-ip>/api/      API prefix
https://<lan-ip>/health    health check (via nginx)
```

Replace self-signed certs in `deploy/lan/nginx/certs/` with your internal CA material for production.

### Corporate proxy (image build only)

```bash
HTTP_PROXY=http://user:pass@proxy.corp:8080 \
HTTPS_PROXY=http://user:pass@proxy.corp:8080 \
NO_PROXY=localhost,127.0.0.1,.corp.local \
  docker compose up -d --build
```

Runtime containers do not use outbound proxies in the default production posture.

---

## LAN deploy helpers

| Script | Purpose |
|--------|---------|
| `deploy/linux/install-docker.sh` | Install Docker Engine + Compose on Debian/Ubuntu/RHEL |
| `deploy/linux/prerequisites.sh` | Pre-flight checks before deploy |
| `deploy/linux/deploy.sh` | One-shot deploy (`--quick` skips wizard) |
| `deploy/linux/docker-stack.sh` | Stack ops: `up`, `down`, `logs`, `health`, `rebuild` |
| `deploy/linux/host-firewall.sh` | Wrapper for host egress lock |
| `deploy/lan/scripts/generate-tls.sh` | Self-signed `sakura.crt` / `sakura.key` |
| `deploy/lan/scripts/generate-tls.ps1` | Windows equivalent |
| `deploy/lan/scripts/host-firewall-linux.sh` | iptables OUTPUT: allow RFC-1918 + loopback, drop rest |
| `deploy/windows/build-and-export.ps1` | Option A: build images on Windows → release zip for CI |
| `deploy/windows/pack-source-release.ps1` | Option B: pack source zip for CI build on Linux |
| `deploy/linux/import-and-deploy.sh` | Option A: `docker load` + `compose up --no-build` |
| `deploy/linux/build-on-server.sh` | Option B: `compose build` + `up` on Linux |
| `deploy/ci/RUNBOOK-OPTION-A.md` | Ops runbook — pre-built images |
| `deploy/ci/RUNBOOK-OPTION-B.md` | Ops runbook — build on server |
| `deploy/windows/push-to-dockerhub.ps1` | Push backend image to Docker Hub |
| `deploy/windows/pull-from-dockerhub.ps1` | Pull from Docker Hub (Windows) |
| `deploy/linux/pull-from-dockerhub.sh` | Pull from Docker Hub (Linux) |
| `deploy/registry/DOCKERHUB.md` | Docker Hub `sriabhi001/simple` — CI + deploy |
| `deploy/registry/GITHUB-ACTIONS.md` | CI pipeline secrets & behaviour |
| `deploy/registry/GHCR.md` | GHCR alternative registry |

```bash
# Linux Docker deploy (production host)
sudo deploy/linux/install-docker.sh
deploy/linux/prerequisites.sh
./bootstrap.sh                              # or: deploy/linux/deploy.sh --quick

# Stack management
deploy/linux/docker-stack.sh status
deploy/linux/docker-stack.sh logs backend
deploy/linux/docker-stack.sh health
```

---

## Security scanning

Runs automatically at the end of **`setup.sh` / `setup.ps1`** (unless skipped).

| Flag (Bash) | Flag (PowerShell) | Effect |
|-------------|-------------------|--------|
| `--skip-audit` | `-SkipAudit` | Skip post-install audit |
| `--audit-strict` | `-AuditStrict` | Fail setup if vulnerabilities found |

Reports land in `reports/security/`:
- `pip-audit-<timestamp>.json` / `.txt` — installed Python packages (via `pip-audit`)
- `npm-audit-prod-<timestamp>.json` / `.txt` — frontend production deps
- `npm-audit-dev-<timestamp>.txt` — dev toolchain (informational)
- `audit-summary-<timestamp>.txt` — pass/fail overview

**Manual re-run**

```bash
bash scripts/security/audit-dependencies.sh --root . --venv-python .venv/bin/python
bash scripts/security/audit-dependencies.sh --strict   # exit 1 on findings
```
```powershell
powershell -File scripts\security\audit-dependencies.ps1 -RootDir . -Strict
```

**Requires one-time network** (or internal PyPI/npm mirror) to install `pip-audit` and refresh advisory databases.

### Docker-based scans (optional)

```bash
# Secret scan (uses .gitleaks.toml)
./scripts/security/run-gitleaks.sh

# OWASP dependency CVE scan → reports/security/
./scripts/security/run-dependency-check.sh
```

---

## Environment variables (`.env`)

Copy [`.env.example`](.env.example). Setup wizard generates secrets automatically.

| Variable | Default | Notes |
|----------|---------|-------|
| `HOST` | `127.0.0.1` (native) / `0.0.0.0` (Docker backend) | Bind address |
| `PORT` | `5000` | Backend port (native); nginx uses `NGINX_*` in Docker |
| `JWT_SECRET_KEY` | *(required)* | ≥32 bytes entropy |
| `ENCRYPTION_KEY` | *(required)* | Fernet key |
| `ALLOWED_ORIGINS` | — | Comma-separated CORS origins; no `*` |
| `ENABLE_NETWORK_RESTRICTIONS` | `strict` | `strict` \| `allow_lan` \| `off` (`off` refused in production) |
| `FORCE_HTTPS` | `true` | Flask-Talisman; nginx terminates TLS in Docker |
| `SAKURA_REQUIRE_AUTH` | `true` | JWT required on `/api/*` except auth routes |
| `SAKURA_LLM_ALLOW_EXTERNAL` | `false` | Blocks OpenAI/Anthropic in production |
| `SAKURA_LLM_ALLOW_REMOTE_OLLAMA` | `false` | Ollama must stay on loopback |
| `SAKURA_ENABLE_OBSERVABILITY` | `true` | Local admin metrics at `/api/admin/observability` |
| `SAKURA_DISABLE_OLLAMA_SIDECAR` | `true` | In-container Ollama daemon |
| `SAKURA_DISABLE_LIVE_INDEXER` | `false` | RAG background indexer |
| `NGINX_HTTPS_PORT` | `443` | Docker nginx HTTPS host port |
| `NGINX_HTTP_PORT` | `80` | Docker nginx HTTP → HTTPS redirect |

Generate secrets manually:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Manual build & run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd frontend && npm ci && npm run build && cd ..
rm -rf backend/static && mkdir -p backend/static
cp -R frontend/dist/frontend/browser/. backend/static/

cp .env.example .env   # fill JWT_SECRET_KEY + ENCRYPTION_KEY
python backend/run_server.py
```

**Dev mode (hot reload frontend)**
```bash
# Terminal 1
FLASK_ENV=development python backend/main.py

# Terminal 2
cd frontend && npm run dev    # http://localhost:4200 → API on :5000
```

---

## Backend utilities

Run from repo root with venv active:

```bash
# Reset DB + seed sample data
python backend/scripts/reset_and_seed_all.py

# Network connection monitor (host-level)
python backend/scripts/monitor_network.py

# Ollama model bundling (Windows offline installer prep)
pwsh backend/scripts/prepare_ollama_resources.ps1
```

**Run backend tests**
```bash
cd backend
python -m pytest tests/unit/test_network_restrictor.py tests/unit/test_security_posture.py -q
```

---

## Corporate proxy (native setup)

```bash
export HTTPS_PROXY=http://user:pass@proxy.corp:8080
export HTTP_PROXY=$HTTPS_PROXY
export NO_PROXY=localhost,127.0.0.1,.corp.local
./setup.sh --insecure-ssl
```

---

## Portable Windows bundle (optional)

For targets without Python installed:

```powershell
# After setup.ps1
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-portable.txt
.\.venv\Scripts\python.exe build_portable.py
.\.venv\Scripts\python.exe build_portable.py --zip
```

Output: `dist\Sakura\` or `dist\Sakura.exe`. See `build_portable.py --help` for `--onefile`, `--seed-db`, `--skip-frontend`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `bad interpreter: ...^M` on Linux | `sed -i 's/\r$//' setup.sh start.sh clean_db.sh` |
| Port in use | `PORT=5050 ./setup.sh` or stop the owning process |
| Docker nginx fails healthcheck | Ensure `deploy/lan/nginx/certs/sakura.crt` exists (`generate-tls.*`) |
| SQLite locked on clean | Stop backend (`Ctrl+C`) before `clean_db.*` |
| pip install fails on new Python | Re-run setup (retries with `--prefer-binary`) or use Python 3.11/3.12 |
| `.env` permissions (POSIX) | `chmod 600 .env` |

---

## API endpoints (operator)

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /health` | No | Liveness |
| `POST /api/auth/login` | No | JWT login |
| `GET /api/admin/observability` | Admin JWT | Local request metrics |
| `GET /api/admin/network/egress-log` | Admin JWT | Socket egress audit log |
