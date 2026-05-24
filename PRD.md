# Sakura — Product Requirements

## 1. Product Summary
Sakura is an internal thick-client web app for managing software-engineering artefacts (requirements, test cases, design tickets, specs, users) on top of a SQLite database that is transparently synchronised through a Git remote. It is single-tenant per Git repo: every authoring action becomes a Git commit, giving auditable history without a dedicated DB server.

## 2. Goals & Non-Goals
**Goals**
- Single source of truth for requirements ↔ test cases ↔ design tickets ↔ specs.
- Offline-first reads, eventually-consistent writes via Git.
- Role-aware UI (admin vs. standard user) with masking of sensitive fields.
- Frictionless local dev: one Flask process + one Angular dev server.

**Non-Goals**
- Multi-tenant SaaS hosting.
- Real-time collaborative editing (last-writer-wins via Git timestamps/versions).
- External AI / 3rd-party integrations — outbound traffic is sandboxed by `network_restrictor.py`.

## 3. Personas
- **Admin** — provisions users, manages roles, has access to `/users`. Master admin auto-provisioned at startup.
- **Engineer / Author** — primary user; creates and edits requirements, test cases, design tickets, specs.
- **Reviewer / Reader** — browses artefacts via list/detail/split views; may not author depending on role gating.

## 4. Core User Flows
1. **Auth** (when `APP_SETTINGS.auth.enabled`)
   - Sign up → login → JWT cached in `localStorage` (`AuthService`).
   - Forgot-password flow available; routes auto-redirect to `/` when auth is disabled.
   - `AuthGuard` protects authenticated routes; `AdminGuard` protects `/users`.
2. **Requirements** — list (`/requirements`), create (`/requirements/create`), detail (`/requirements/:id`).
3. **Test Cases** — list with filter panel (priority/type/region), create, detail with step procedures. Bulk import via CSV/XLSX (`bulk_import_service.py`, `sample_aaos_test_cases.*`).
4. **Design Tickets** — management view, create, detail with mockups/status tags/linkage to requirements.
5. **Specs** — list/detail under `/specs`.
6. **Split View** — side-by-side comparison/navigation across artefact types (`/split-view`).
7. **User Management** (admin only) — list, role change, delete, create modal; emails masked in tables.
8. **Sync** — startup + periodic background pull; manual `POST /api/sync/force` and `POST /api/git/pull` available.

## 5. Functional Requirements
- All write paths go through `HybridDatabaseService` so the metadata version is incremented and the SQLite file is committed/pushed.
- All SQL is parameterised; no string-interpolated user input.
- Sensitive columns (e.g. `email`) must render via masked variants (`email_masked || email`).
- Frontend dependencies stay within the configured Angular bundle budgets.
- Git commit messages reflect the action (e.g. `Add user: testuser1`); user's encrypted token (`git_token_encrypted`) is decoded to attribute the commit when present.

## 6. Non-Functional Requirements
- **Security**: JWT auth, security headers, rate limiting, CORS allowlist (`*` in dev only). Outbound network is monkey-patched to localhost + Git host allowlist.
- **Performance**: Reads served from local SQLite; writes <1 push round-trip, async background sync worker.
- **Reliability**: App boots even if hybrid sync init fails — degrades to "limited functionality" with logged warning rather than crashing.
- **Observability**: Structured loggers via `src.infrastructure.logging_config`; request logging middleware enabled.

## 7. Scope
**In scope**: artefact CRUD, role-based access, Git-backed persistence, bulk CSV/XLSX import for test cases, masked PII in tables, dashboard landing page, i18n via `translation.service` + `translate.pipe`.
**Out of scope**: external integrations, push notifications, mobile app, multi-DB tenancy.

## 8. Success Metrics
- Backend `/health` returns 200 within 1s of boot after sync init.
- Authoring round-trip (write → committed to remote) ≤ 5s on a healthy connection.
- Zero raw SQL strings constructed via interpolation in `repositories/` or `services/`.
- `npm run build` passes without exceeding bundle budgets on every PR.
