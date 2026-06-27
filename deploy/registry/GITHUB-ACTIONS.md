# GitHub Actions — auto-build & Docker Hub publish

Pipeline: [`.github/workflows/main.yml`](../../.github/workflows/main.yml)

Published to: **[hub.docker.com/r/sriabhi001/simple](https://hub.docker.com/r/sriabhi001/simple)**

Full pull/deploy guide: [`DOCKERHUB.md`](DOCKERHUB.md)

---

## Required secrets (one-time)

GitHub → **Settings → Secrets and variables → Actions**

| Secret | Value |
|--------|--------|
| `DOCKERHUB_USERNAME` | `sriabhi001` |
| `DOCKERHUB_TOKEN` | [Docker Hub access token](https://hub.docker.com/settings/security) (Read & Write) |

Without these secrets the `build-and-push` job fails with a clear error.

---

## What runs on each push to `main`

1. Backend `pytest`
2. Frontend production build + `npm audit`
3. Docker compose smoke test
4. Build `linux/amd64` → push `sriabhi001/simple:latest` (+ `sha-*`, branch, version tags)

PRs: tests only, no push.

---

## Deploy `.env`

```env
SAKURA_BACKEND_IMAGE=sriabhi001/simple:latest
```

```bash
docker pull sriabhi001/simple:latest
docker compose up -d --no-build
```

---

## Version tags

```bash
git tag v1.0.0 && git push origin v1.0.0
```

Publishes `sriabhi001/simple:v1.0.0`
