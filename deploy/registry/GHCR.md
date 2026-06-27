# Container registry (GHCR) — share images across Windows and Linux

**Do not commit Docker images to git.** A single `sakura-backend` image is ~1 GB+; git is for source code, not binary layers.

Use **GitHub Container Registry (GHCR)** instead — it lives next to your repo on GitHub:

| Store | Use for |
|-------|---------|
| **Git** | Source, compose files, deploy scripts |
| **GHCR** (`ghcr.io`) | Built `linux/amd64` Docker images |
| **Release zip** (`build-and-export.ps1`) | Air-gapped LAN with no registry access |

One image works on **both** Windows Docker Desktop and Linux servers (same `linux/amd64` container).

---

## Automatic push (CI)

On every push to `main` / `master`, GitHub Actions builds and pushes:

```
ghcr.io/<owner>/<repo>:latest
ghcr.io/<owner>/<repo>:<git-sha>
```

See [`.github/workflows/main.yml`](../../.github/workflows/main.yml) and [`GITHUB-ACTIONS.md`](GITHUB-ACTIONS.md) for setup (private GHCR + optional enterprise registry).

---

## One-time: make the package visible

1. GitHub → your repo → **Packages** (or the package under your profile)
2. **Package settings** → change visibility (private/internal/public) for your org policy
3. For private packages, collaborators need `read:packages` (classic PAT) or appropriate org role

---

## Set image name in `.env`

Lowercase owner/repo (GHCR requirement):

```env
# Example — replace with your GitHub org/user and repo name
SAKURA_BACKEND_IMAGE=ghcr.io/your-org/simple:latest
```

`docker-compose.yml` uses this variable for the backend service.

---

## Push from Windows (developer machine)

After building locally:

```powershell
# 1. Create a GitHub PAT with write:packages (Settings → Developer settings → PAT)
$env:GHCR_TOKEN = "<your-pat>"
$env:GHCR_USER = "<your-github-username>"

# 2. Set image in .env (see above), then:
powershell -ExecutionPolicy Bypass -File deploy\windows\push-to-ghcr.ps1 -Tag 1.0.0
```

Also pushes `:latest` when `-Tag` is not `latest`.

---

## Pull on Windows or Linux (no rebuild)

```bash
# .env must contain SAKURA_BACKEND_IMAGE=ghcr.io/...
export GHCR_TOKEN=...   # read:packages for private images
export GHCR_USER=...

bash deploy/linux/pull-from-ghcr.sh
```

```powershell
$env:GHCR_TOKEN = "..."
$env:GHCR_USER = "..."
powershell -ExecutionPolicy Bypass -File deploy\windows\pull-from-ghcr.ps1
```

Then start the stack:

```bash
docker compose pull nginx redis    # public images (skip if LAN blocks Hub — use release zip)
docker compose up -d --no-build
```

---

## Login manually

```bash
echo $GHCR_TOKEN | docker login ghcr.io -u $GHCR_USER --password-stdin
```

```powershell
$env:GHCR_TOKEN | docker login ghcr.io -u $env:GHCR_USER --password-stdin
```

---

## Which method to use?

| Situation | Method |
|-----------|--------|
| Team has GitHub + internet | **GHCR** pull (this doc) |
| LAN blocks registry, has file share | **Release zip** ([RUNBOOK-OPTION-A.md](../ci/RUNBOOK-OPTION-A.md)) |
| LAN can build once | Source zip ([RUNBOOK-OPTION-B.md](../ci/RUNBOOK-OPTION-B.md)) |
| Storing blobs in git | **Never** — use GHCR or release artifacts |

---

## GitHub Releases (optional)

For air-gapped sites that cannot reach GHCR, attach `sakura-docker-release-*.zip` to a **GitHub Release** (Assets tab). That is file storage on GitHub, not a git commit — still better than checking images into the repo.
