# Sakura

Requirements and test-case management app: Flask + SQLite backend, Angular SPA served on the same origin as `/api/*`.

**Scripts, flags, Docker, and environment variables:** [`COMMANDS.md`](COMMANDS.md)

---

## Prerequisites

| Tool | Version | Required for |
|------|---------|--------------|
| Python | 3.10+ | Native setup |
| Node.js + npm | 18+ | Native setup (frontend build) |
| Docker + Compose | current | Docker LAN deployment |

SQLite is embedded — no separate database server.

---

## First run

**Interactive wizard (recommended)** — prompts for native vs Docker, security, TLS, and optional IAM:

```bash
./setup.sh
```
```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

**Docker LAN only:**

```bash
./bootstrap.sh
```
```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1
```

**New Windows PC (clone → Docker build → test → CI zip):** [`deploy/windows/NEW-PC-SETUP.md`](deploy/windows/NEW-PC-SETUP.md)

| Result | URL |
|--------|-----|
| Native setup | `http://<host>:5000/` |
| Docker LAN | `https://<lan-ip>/` |

---

## After setup

```bash
./start.sh              # restart without rebuild
./clean_db.sh --force   # wipe SQLite (stop server first)
```

Full command reference: [`COMMANDS.md`](COMMANDS.md)
