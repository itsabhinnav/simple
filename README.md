# Sakura

Sakura is a thick-client web application that pairs a Flask + SQLite backend
with an Angular standalone frontend. The Angular bundle is built as a pure
static SPA and served by the Flask backend on the same origin as the REST API,
so a single process handles both the UI and `/api/*` traffic.

This README documents the *deployment* workflow. For architectural details
see [`AGENTS.md`](AGENTS.md), [`backend/AGENTS.md`](backend/AGENTS.md) and
[`frontend/AGENTS.md`](frontend/AGENTS.md).

---

## Prerequisites

The host machine needs three things installed and on `PATH`:

| Tool       | Minimum version | Used for                                  |
|------------|-----------------|-------------------------------------------|
| Python     | 3.10            | Flask backend + WSGI server               |
| Node.js    | 18              | Building the Angular bundle               |
| npm        | bundled         | Installing frontend dependencies          |

No database server is required - the default configuration uses SQLite under
`backend/data/`. Docker is **not** required for the default flow.

---

## One-command deployment

After cloning the repository (or unzipping a downloaded archive), run the
matching script from the project root:

### Linux / macOS

```bash
chmod +x setup.sh
./setup.sh
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Each script performs the same steps:

1. Verifies the prerequisites above.
2. Creates an isolated Python virtualenv at `.venv/` and installs everything
   in `backend/requirements.txt`.
3. Installs npm dependencies for `frontend/` (skipped if `node_modules/`
   already exists; pass `--skip-frontend-install` / `-SkipFrontendInstall` to
   force the skip on subsequent runs).
4. Builds the Angular app in production mode and publishes the static bundle
   to `backend/static/`.
5. Generates `.env` from `.env.example` with strong random values for
   `JWT_SECRET_KEY` and `ENCRYPTION_KEY` when no `.env` is present.
6. Boots the backend via `backend/run_server.py`, which picks **Gunicorn** on
   Linux/macOS and **Waitress** on Windows.

Once the server is up, the application is available at:

```
http://<host>:5000/
```

The same port serves both the static frontend and the JSON API under `/api`.

Pass `--no-start` (Bash) or `-NoStart` (PowerShell) to perform the build
without launching the server.

### Restarting the server later

After the first successful `setup.sh` / `setup.ps1`, the `.venv/` and
`backend/static/` artefacts are already on disk. To start the server again
without re-running install or build, use the lightweight launcher scripts:

```bash
# Linux / macOS
./start.sh
```

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Or, if you prefer to invoke Python directly:

```bash
# Linux / macOS
.venv/bin/python backend/run_server.py
```

```powershell
# Windows
.\.venv\Scripts\python.exe backend\run_server.py
```

Stop the server with `Ctrl+C`. Re-run `setup.*` only when you change
dependencies (`backend/requirements.txt`, `frontend/package.json`) or the
frontend source (so the static bundle gets rebuilt).

---

## Setup script flags

| Flag (Bash / PowerShell)                          | Effect                                                                                              |
|---------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| `--no-start` / `-NoStart`                         | Install + build only; do not launch the server.                                                     |
| `--skip-frontend-install` / `-SkipFrontendInstall`| Skip `npm ci` / `npm install`; useful when `node_modules/` is known good.                           |
| `--insecure-ssl` / `-InsecureSsl`                 | Disable TLS verification for pip + npm + Node (for corporate MITM proxies).                         |
| `--clean-build` / `-CleanBuild`                   | Wipe `frontend/dist` and the Angular cache before rebuilding (use after switching SSR ↔ SPA mode).  |
| `PORT=<n>` env var                                | Override the bind port (default 5000). Setup also runs a non-fatal preflight on this port.          |
| `HOST=<addr>` env var                             | Override the bind address (default 0.0.0.0).                                                        |

---

## Things to watch out for

- **`setup.sh` line endings**: if you cloned on Windows with `core.autocrlf=true`
  and copied the tree to a Linux box, run `sed -i 's/\r$//' setup.sh start.sh clean_db.sh`
  before executing. Otherwise bash will report `bad interpreter: /usr/bin/env bash^M`.
- **Port already in use**: setup prints a warning naming the owning process;
  pick a free port with `PORT=5050 ./setup.sh` (or `$env:PORT="5050"`).
- **Corporate proxy with self-signed cert**: pair `HTTPS_PROXY=...` with
  `--insecure-ssl` so pip/npm accept the proxy's intercepted TLS.
- **Windows long paths**: nested `node_modules` can exceed 260 chars. Enable
  long paths once on the machine: `git config --global core.longpaths true`
  and run `New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name 'LongPathsEnabled' -Value 1 -PropertyType DWord -Force`.
- **Stale SSR artefacts after upgrading**: if you used an older SSR-based
  build of this project, run `setup.* -CleanBuild` once so `frontend/dist`
  doesn't keep a leftover `server/` folder.
- **SQLite is locked during a clean**: stop the server (`Ctrl+C`) before
  running `clean_db.*`, or Windows will refuse to delete the open file.
- **`.env` permissions on POSIX**: setup.sh chmods the generated `.env` to
  600. If you copy it across hosts, re-apply: `chmod 600 .env`.

---

## Corporate proxies

Both `setup.sh` and `setup.ps1` honour the standard proxy environment
variables for `pip`, `npm` and the get-pip.py bootstrap fallback. Set them
once in your shell (either casing works — the scripts normalise and
re-export both):

```bash
# Linux / macOS
export HTTPS_PROXY=http://user:pass@proxy.corp.local:8080
export HTTP_PROXY=$HTTPS_PROXY
export NO_PROXY=localhost,127.0.0.1,.corp.local
./setup.sh
```

```powershell
# Windows
$env:HTTPS_PROXY = "http://user:pass@proxy.corp.local:8080"
$env:HTTP_PROXY  = $env:HTTPS_PROXY
$env:NO_PROXY    = "localhost,127.0.0.1,.corp.local"
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

When a proxy is detected the script prints a masked banner (credentials are
hidden) and forwards it to `pip --proxy`, `Invoke-WebRequest -Proxy`, and the
child npm process via `HTTPS_PROXY` / `HTTP_PROXY` env vars.

---

## Resetting the local database

To wipe the SQLite database and let the backend re-create an empty schema on
the next start, use the bundled cleaner. By default it only touches the
local SQLite file (and its WAL / SHM sidecars) and prompts for confirmation
before deleting anything.

```bash
# Linux / macOS
./clean_db.sh                          # prompts before deleting
./clean_db.sh --force                  # skip prompt
./clean_db.sh --force --with-remote --with-uploads  # also wipe Git workspace + uploads
```

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File .\clean_db.ps1
powershell -ExecutionPolicy Bypass -File .\clean_db.ps1 -Force
powershell -ExecutionPolicy Bypass -File .\clean_db.ps1 -Force -WithRemote -WithUploads
```

After cleaning, run `./start.sh` (or `start.ps1`) — `HybridDatabaseService`
creates the tables on first connect and `provision_master_admin` recreates
the admin user from `.env`. **Stop the server before running the cleaner**;
SQLite holds an exclusive lock while the backend is up.

---

## Runtime configuration

All runtime knobs live in `.env` at the project root. Look at
[`.env.example`](.env.example) for the full list. The most important ones:

| Variable                       | Default        | Purpose                                                                 |
|--------------------------------|----------------|-------------------------------------------------------------------------|
| `HOST`                         | `0.0.0.0`      | Bind address for the WSGI server.                                       |
| `PORT`                         | `5000`         | TCP port shared by the SPA and `/api`.                                  |
| `JWT_SECRET_KEY`               | generated      | Signs JWTs issued by `/api/auth/*`.                                     |
| `ENCRYPTION_KEY`               | generated      | Fernet key for encrypting stored Git tokens.                            |
| `ALLOWED_ORIGINS`              | localhost only | Extra CORS origins; only needed for cross-host API calls.               |
| `ENABLE_NETWORK_RESTRICTIONS`  | `false`        | Enables the socket allow-list in `network_restrictor.py`.               |
| `ENVIRONMENT`                  | `production`   | `production` disables Flask debug; `development` enables it.            |

To rebuild after a code change and restart the server, simply re-run the
setup script. It is idempotent and safe to run repeatedly.

---

## Manual workflow (without the script)

If you prefer to drive each step yourself:

```bash
# 1. backend deps
python -m venv .venv
source .venv/bin/activate                # Windows: .\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

# 2. build the frontend
cd frontend
npm ci
npm run build
cd ..

# 3. publish to backend/static
rm -rf backend/static
mkdir backend/static
cp -R frontend/dist/frontend/browser/. backend/static/

# 4. start the production server
python backend/run_server.py
```

For day-to-day development against the Angular dev server (hot reload):

```bash
# Terminal 1 - backend on :5000
python backend/main.py

# Terminal 2 - Angular dev server on :4200 (talks to backend automatically)
cd frontend && npm run dev
```

The frontend resolves the API base URL from `window.location` at runtime, so
the dev server transparently targets `http://<hostname>:5000` while the
production bundle uses same-origin relative URLs.

---

## Portable Windows distribution (no Python on the target PC)

To deploy on a PC that does *not* have Python installed, build a
self-contained PyInstaller bundle. The bundle ships a Python interpreter, all
DLLs, the Angular SPA, and a seed copy of the SQLite database, so the only
prerequisite on the target machine is Windows itself.

### One-time build setup (developer machine)

Run the regular `setup.ps1` once so the venv and Angular bundle exist, then
install the extra build deps:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-portable.txt
```

### Build the bundle

```powershell
# One-folder build (faster startup, recommended for shipping to clients)
.\.venv\Scripts\python.exe build_portable.py

# One-file build (single .exe; slower first launch because it self-extracts)
.\.venv\Scripts\python.exe build_portable.py --onefile

# Zip the result for distribution
.\.venv\Scripts\python.exe build_portable.py --zip

# Pick a specific seed DB (the script otherwise auto-picks the largest
# existing sakura_db.db under data\)
.\.venv\Scripts\python.exe build_portable.py `
    --seed-db data\remote\data\remote\dev\database\sakura_db.db
```

The build script:

1. Builds the Angular frontend (skipped with `--skip-frontend`) and publishes
   it to `backend\static\`.
2. Picks the largest `sakura_db.db` found under `data\` and bundles it as the
   seed database (or use `--seed-db <path>` to point at a specific file).
3. Generates a fresh `sakura.spec` referencing `backend\portable_entry.py`
   as the entry point.
4. Invokes PyInstaller with `collect_all` for native packages
   (`cryptography`, `pydantic`, `flask`, `waitress`, `openpyxl`, ...) so all
   `.pyd` / `.dll` files travel with the exe.
5. Drops a `Start-Sakura.bat` launcher and a copy of `.env.example` next to
   the executable so end users can edit secrets without unpacking the
   bundle.

The output lands in `dist\Sakura\` (one-folder) or `dist\Sakura.exe`
(`--onefile`).

### What end users see

On first launch the bundled `portable_entry.py` copies the seed database to a
writable directory:

- next to the .exe by default (fully portable), or
- under `%LOCALAPPDATA%\Sakura\` if the install dir is read-only (e.g. when
  the bundle was extracted under `C:\Program Files\`).

The runtime database then lives at:

```
<install-folder>\data\local\dev\database\sakura_db.db
```

Delete that file to reset to the bundled snapshot. The exe also reads a
`.env` placed next to it, so port / secret overrides survive across
upgrades.

> **Why was the bundled DB showing 0 rows before?** PyInstaller extracts
> bundled resources into a read-only temp folder (`_MEIxxxxx`). The previous
> build never copied the seed DB out of that temp folder, so the running
> process happily created a fresh empty SQLite file in the working directory
> and reported 0 rows for every table. `backend\portable_entry.py` fixes
> this by seeding a writable copy on first launch and forcing the backend
> (via the `SAKURA_LOCAL_DB_PATH` env var) to use it instead of the bundled
> path.

---

## Python version compatibility

`backend/requirements.txt` uses compatible-version ranges (e.g.
`cryptography>=42.0.5`, `pydantic>=2.5,<3`) rather than exact pins so the
same file installs on Python 3.10 through 3.13+. Several of the packages
(`cryptography`, `psycopg2-binary`, `pydantic-core`) only publish prebuilt
wheels for a narrow band of Python versions per release; exact pins would
force a from-source build on newer interpreters and fail on any machine
without a C toolchain.

If `pip install` still fails on a machine whose Python version is too new
(or too old) for one of the packages:

- `setup.ps1` and `setup.sh` automatically retry with `--prefer-binary` and
  then fall back to installing packages one-by-one to surface the
  offender's name.
- For a reproducible deploy, freeze a successful install once
  (`pip freeze > requirements.lock.txt`) and ship the lock file alongside
  the repo so other machines install the exact same versions where wheels
  exist.
- As a last resort, install one of the Python versions known to have
  wheels for every dependency (3.11 or 3.12 are the safest choices today)
  and re-run `setup.ps1` with that interpreter on `PATH`.

---

## Docker (optional)

A unified container image is also available for environments where Docker is
preferred over a native install.

```bash
# Default - SQLite + volume-backed persistence
docker compose up -d --build

# With a corporate proxy (forwarded to apt, pip and npm during the build
# AND to the running container so it can reach the Git remote):
HTTP_PROXY=http://user:pass@proxy.corp.local:8080 \
HTTPS_PROXY=http://user:pass@proxy.corp.local:8080 \
NO_PROXY=localhost,127.0.0.1,.corp.local \
  docker compose up -d --build

# Optional Postgres add-on (mostly for shared deployments):
docker compose --profile postgres up -d --build
```

Highlights of the Docker setup:

- Multi-stage `Dockerfile.unified` builds the Angular SPA in Node 20, then
  copies the bundle into `backend/static/` inside a Python 3.10-slim runtime
  image. Single image, single port (`5000`).
- `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` are accepted as `--build-arg`s
  and re-exported at runtime — corporate networks work out of the box.
- Container uses `python backend/run_server.py` (Gunicorn), so the bootstrap
  path is identical to the native deployment (DB init + master admin
  provision on first boot).
- A `HEALTHCHECK` against `/health` is baked into both the Dockerfile and
  `docker-compose.yml`.
- Named volumes `sakura-data` and `sakura-uploads` keep the SQLite database
  and uploaded spec files across container recreations.
- `.dockerignore` strips dev artefacts (`.venv`, `node_modules`, `dist`,
  `__pycache__`, `data`, etc.) so build context stays small.

`bootstrap.sh` / `bootstrap.ps1` still drive `docker compose up -d --build`
for users who prefer a single script over invoking compose directly.

---

## Notes for AI assistants

When working on this project, you MUST:

1. Verify your answers by checking the actual code, configuration files, and
   project structure - do not hallucinate.
2. Report bugs and incomplete implementations honestly instead of glossing
   over them.
3. Validate before claiming completion (`npm run build`, backend smoke test,
   etc.).

This applies to both human contributors and Cursor itself.
