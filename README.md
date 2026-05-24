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

## Docker (optional)

A unified container image is also available for environments where Docker is
preferred over a native install. See `Dockerfile.unified`, `docker-compose.yml`
and `bootstrap.sh` / `bootstrap.ps1` for the existing flow; that path is
unchanged.

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
