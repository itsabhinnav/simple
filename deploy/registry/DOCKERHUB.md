# Docker Hub — `sriabhi001/simple`

Published image: **[hub.docker.com/r/sriabhi001/simple](https://hub.docker.com/r/sriabhi001/simple)**

Same `linux/amd64` image runs on Windows Docker Desktop and Linux LAN servers.

---

## GitHub Actions (automatic)

On every push to `main`/`master` (after tests pass), the pipeline pushes to:

```
sriabhi001/simple:latest
sriabhi001/simple:sha-<commit>
sriabhi001/simple:v1.0.0        # when you push git tag v1.0.0
```

### Required repository secrets

GitHub → **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|--------|--------|
| `DOCKERHUB_USERNAME` | `sriabhi001` |
| `DOCKERHUB_TOKEN` | Access token from [Docker Hub → Account Settings → Security → New Access Token](https://hub.docker.com/settings/security) |

Token permissions: **Read & Write** (or Read, Write & Delete).

Push to `main` after adding secrets to trigger the first publish.

---

## Deploy from Docker Hub

`.env` on Windows or Linux:

```env
SAKURA_BACKEND_IMAGE=sriabhi001/simple:latest
```

```bash
# Public image — no login required
docker pull sriabhi001/simple:latest
docker compose up -d --no-build
```

**Private repository** (Docker Hub paid plan):

```bash
export DOCKERHUB_USERNAME=sriabhi001
export DOCKERHUB_TOKEN=dckr_pat_...
bash deploy/linux/pull-from-dockerhub.sh
docker compose up -d --no-build
```

```powershell
$env:DOCKERHUB_USERNAME = "sriabhi001"
$env:DOCKERHUB_TOKEN = "dckr_pat_..."
powershell -ExecutionPolicy Bypass -File deploy\windows\pull-from-dockerhub.ps1
docker compose up -d --no-build
```

---

## Manual push from Windows

```powershell
# .env
# SAKURA_BACKEND_IMAGE=sriabhi001/simple:latest

$env:DOCKERHUB_USERNAME = "sriabhi001"
$env:DOCKERHUB_TOKEN = "dckr_pat_..."
powershell -ExecutionPolicy Bypass -File deploy\windows\push-to-dockerhub.ps1 -Tag 1.0.0
```

---

## LAN / air-gapped note

Docker Hub requires outbound internet at **pull** time. If the LAN server cannot reach `registry-1.docker.io`, use the **release zip** ([RUNBOOK-OPTION-A.md](../ci/RUNBOOK-OPTION-A.md)) instead.

---

## Change repository name

Edit `DOCKERHUB_IMAGE` in [`.github/workflows/main.yml`](../../.github/workflows/main.yml) and `SAKURA_BACKEND_IMAGE` in `.env`.
