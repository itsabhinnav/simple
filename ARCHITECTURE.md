# Sakura — Architecture

## 1. Stack Decisions

| Layer       | Choice                                  | Rationale                                                                 |
|-------------|-----------------------------------------|---------------------------------------------------------------------------|
| Backend     | Python 3 + Flask 3.1, Flask-CORS        | Lightweight, blueprint-based, easy to embed alongside SQLite + GitPython. |
| Persistence | SQLite file synced through Git remote   | Auditable history, no DB server, offline-first reads.                     |
| Auth        | PyJWT (HS256) + bcrypt-style hashing    | Stateless tokens stored in `localStorage`; guards on the client.          |
| Frontend    | Angular 20 standalone + Signals         | Modern reactive primitives without NgModule boilerplate.                  |
| Styling     | Vanilla CSS + CSS custom properties     | No utility framework; theme tokens via `var(--color-*)`.                  |
| Build       | `@angular/build` (esbuild) / `ng serve` | Fast HMR; production bundle has size budgets enforced.                    |
| Server-side | Express + `@angular/ssr` (optional)     | Available via `serve:ssr:frontend` script; not used in dev.               |
| Security    | `network_restrictor.py` socket patch    | Blocks egress beyond localhost / whitelisted Git hosts.                   |

## 2. Folder Structure

```
Simple/
├── AGENTS.md                 ← root agent guide
├── PRD.md                    ← product spec (this set)
├── ARCHITECTURE.md           ← this file
├── README.md
├── .cursorrules              ← universal agent directives
├── .cursor/rules/
│   ├── backend.mdc           ← scoped to backend/**
│   └── frontend.mdc          ← scoped to frontend/**
├── backend/
│   ├── main.py               ← Flask entry point, blueprint registration
│   ├── requirements.txt
│   ├── samples/              ← CSV/XLSX seed fixtures (test cases)
│   ├── scripts/              ← seeders, migrations, network monitors
│   ├── data/local/dev/database/
│   │   └── sakura_db.db      ← local SQLite cache
│   └── src/
│       ├── controllers/      ← HTTP blueprints (see API contract below)
│       ├── services/         ← business logic + hybrid DB orchestration
│       │   ├── hybrid_database_service.py
│       │   ├── git_database_service.py
│       │   ├── local_database_service.py
│       │   └── <entity>_service.py
│       ├── repositories/     ← SQL data-access mapping
│       ├── schemas/          ← request/response shapes (pydantic-style)
│       ├── infrastructure/   ← DI, config, logging, network restrictor
│       └── middleware/       ← auth, CORS, error handlers, rate limiting
└── frontend/
    ├── package.json
    └── src/
        ├── index.css         ← global theme tokens
        └── app/
            ├── app.ts        ← root standalone component
            ├── app.routes.ts ← route table + guards
            ├── app-settings.ts
            ├── components/   ← per-feature standalone components
            ├── services/     ← HTTP clients + state (signals)
            └── guards/       ← AuthGuard, AdminGuard
```

## 3. Runtime Topology

```
Browser (Angular SPA, :4200 dev / served from Flask static in prod)
   │   HTTP/JSON
   ▼
Flask app (:5000)
   │
   ├── middleware: CORS, auth, validation, rate limit, logging
   ├── controllers (blueprints) ──► services ──► repositories ──┐
   │                                                             ▼
   │                                              Local SQLite (sakura_db.db)
   │                                                             │
   └── HybridDatabaseService ──► GitDatabaseService ──► Git remote (e.g. gitlab.com)
                       ▲                    │
                       └── background _sync_worker (daemon thread)
```

- **Reads**: controllers → services → `LocalDatabaseService` → SQLite.
- **Writes**: controllers → services → `HybridDatabaseService` → SQLite → bump `database_metadata` version → copy file into Git workspace → commit + push (using user's decrypted `git_token_encrypted` when available).
- **Startup sync**: clone/fetch remote → compare local vs. remote `database_metadata` version → copy whichever is newer → start background sync worker.

## 4. Dependency Injection

All service wiring lives in `backend/src/infrastructure/dependency_injection.py`. Controllers and services MUST resolve dependencies through getters (`get_user_service()`, `get_hybrid_database_service()`, …). Direct instantiation in controller/service bodies is forbidden — it breaks lifecycle and Git sync invariants.

## 5. API Contract

All endpoints are JSON; success responses are shaped `{ "success": true, "data": ... }` and errors as `{ "success": false, "error": "<msg>" }` with appropriate HTTP status. Auth-protected endpoints expect `Authorization: Bearer <jwt>`.

### 5.1 Blueprints

| Prefix                   | Module                                      | Purpose                                  |
|--------------------------|---------------------------------------------|------------------------------------------|
| `/api/auth`              | `auth_controller.py`                        | Login, signup, refresh, password reset.  |
| `/api/users`             | `user_controller.py`                        | User CRUD, role updates (admin-gated).   |
| `/api/admin`             | `admin_controller.py`                       | Admin-only operations.                   |
| `/api/test-cases`        | `test_case_controller.py`                   | Test case CRUD + bulk import.            |
| `/api/requirements`      | `requirement_controller.py`                 | Requirement CRUD.                        |
| `/api/design-tickets`    | `design_ticket_controller.py`               | Design ticket CRUD + linkage.            |
| `/api/specs`             | `spec_controller.py`                        | Specification CRUD.                      |

### 5.2 Platform / Sync Endpoints (legacy routes in `main.py`)

| Method | Path                                       | Purpose                                  |
|--------|--------------------------------------------|------------------------------------------|
| GET    | `/health`                                  | Liveness probe.                          |
| GET    | `/api/status`                              | API metadata + endpoint catalogue.       |
| GET    | `/api/all/`                                | Dump of every table (debug/inspection).  |
| GET    | `/api/databases`                           | List managed SQLite databases.           |
| GET    | `/api/databases/<name>/info`               | DB info / metadata.                      |
| POST   | `/api/databases/<name>/sync`               | Sync a named DB.                         |
| POST   | `/api/databases/<name>/query`              | Execute parameterised query (admin).     |
| GET    | `/api/git/status`                          | Git workspace status.                    |
| POST   | `/api/git/pull`                            | Pull latest remote changes.              |
| GET    | `/api/sync/status`                         | Hybrid sync state.                       |
| POST   | `/api/sync/force`                          | Force immediate sync cycle.              |
| GET    | `/api/users/<id>/preferences`              | Read user preferences (local-only).      |
| POST   | `/api/users/<id>/preferences`              | Write user preference `{ key, value }`.  |

### 5.3 Frontend Routes ↔ Components (`app.routes.ts`)

| Path                          | Component                            | Guard                |
|-------------------------------|--------------------------------------|----------------------|
| `/`                           | `DashboardComponent`                 | `AuthGuard`          |
| `/login`                      | `DashboardComponent` *(auth on)* / redirect `/` *(auth off)* | — |
| `/forgot-password`            | `ForgotPasswordComponent` *(auth on)* / redirect `/` *(auth off)* | — |
| `/requirements`               | `RequirementsComponent`              | `AuthGuard`          |
| `/requirements/create`        | `CreateRequirementComponent`         | `AuthGuard`          |
| `/requirements/:id`           | `RequirementDetailComponent`         | `AuthGuard`          |
| `/users`                      | `UserManagementComponent`            | `AuthGuard, AdminGuard` |
| `/test-cases`                 | `TestCaseManagementComponent`        | `AuthGuard`          |
| `/test-cases/create`          | `CreateTestCaseComponent`            | `AuthGuard`          |
| `/test-cases/:id`             | `TestCaseDetailComponent`            | `AuthGuard`          |
| `/design-tickets`             | `DesignTicketManagementComponent`    | `AuthGuard`          |
| `/design-tickets/create`      | `CreateDesignTicket`                 | `AuthGuard`          |
| `/design-tickets/:id`         | `DesignTicketManagementComponent`    | `AuthGuard`          |
| `/specs`                      | `SpecManagementComponent`            | `AuthGuard`          |
| `/split-view`                 | `SplitViewComponent`                 | `AuthGuard`          |
| `**`                          | redirect to `/`                      | —                    |

## 6. Frontend State

- Reactive primitives: `signal`, `computed`, `effect` from `@angular/core`.
- `effect()` MUST be created inside class field initialisers or the `constructor()` (injection context). Lifecycle-hook creation triggers `NG0203`.
- Services use field-level `inject(...)` rather than constructor parameters for new code.
- Auth state lives in `AuthService` with the JWT cached in `localStorage`.

## 7. Configuration

- `APP_SETTINGS` (frontend) toggles auth-related routing.
- Backend env: `FLASK_ENV`, `HOST`, `PORT`, `ALLOWED_ORIGINS`, `ENABLE_NETWORK_RESTRICTIONS`.
- Backend JSON config: `src/infrastructure/configuration_manager.py` reads paths like `database.local_db_path`.

## 8. Local Development

```bash
# backend
cd backend && pip install -r requirements.txt && python main.py    # :5000

# frontend
cd frontend && npm install && npm run dev                          # :4200
```

Both servers must run concurrently for the SPA to talk to the API in development.
