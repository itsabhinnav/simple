# AI Agents Developer Guide - Sakura Project Root

Welcome, AI Agent! This document provides a high-level overview of the **Sakura Project** codebase, its architecture, layout, security constraints, and running instructions. Read this before making edits or answering user queries.

---

## 1. System Overview

Sakura is a thick-client web application designed for database management integrated with Git repository tracking. It consists of:
- **Backend:** A Python Flask-based API managing SQLite databases with automatic remote Git synchronization.
- **Frontend:** An Angular 20+ standalone application leveraging reactive state management via Signals and stylized with custom CSS.

---

## 2. Directory Structure

Here is the high-level layout of the repository:

- [`backend/`](file:///c:/workspace/sources/Simple/backend) - Python Flask application.
  - [`AGENTS.md`](file:///c:/workspace/sources/Simple/backend/AGENTS.md) - Backend-specific AI agent guide.
  - [`src/`](file:///c:/workspace/sources/Simple/backend/src) - Modular backend codebase (controllers, services, repositories, infrastructure).
  - [`main.py`](file:///c:/workspace/sources/Simple/backend/main.py) - Flask entry point, registering blueprints and starting services.
  - [`requirements.txt`](file:///c:/workspace/sources/Simple/backend/requirements.txt) - Production Python dependencies.
  - [`scripts/`](file:///c:/workspace/sources/Simple/backend/scripts) - Seeding, schema migrations, testing, and network monitoring utilities.
- [`frontend/`](file:///c:/workspace/sources/Simple/frontend) - Angular client application.
  - [`AGENTS.md`](file:///c:/workspace/sources/Simple/frontend/AGENTS.md) - Frontend-specific AI agent guide.
  - [`src/app/`](file:///c:/workspace/sources/Simple/frontend/src/app) - Angular code including components, guards, routes, and services.
  - [`package.json`](file:///c:/workspace/sources/Simple/frontend/package.json) - Node scripts and packages (utilizes Angular 20.3.0+, `@angular/build`, TypeScript 5.9+).
- [`data/`](file:///c:/workspace/sources/Simple/data) - Local and remote databases storage folder.
- [`tests/`](file:///c:/workspace/sources/Simple/tests) - Backend unit/integration tests.
- [`README.md`](file:///c:/workspace/sources/Simple/README.md) - Standard instructions and critical AI warning notice.

---

## 3. Architecture & Core Subsystems

### A. SQLite + Git Hybrid Database
Sakura uses a dual-database pattern managed by `HybridDatabaseService`:
1. **Reads:** Routed directly to the local cached SQLite database (`local.db` or `sakura_db.db`) for near-instantaneous speed.
2. **Writes:** Applied locally first. A database metadata version is incremented, and then the updated SQLite file is copied into the Git workspace and pushed to the remote repository.
3. **Startup/Periodic Sync:** Changes from other clients are regularly pulled from the Git remote. Version control metadata decides whether to pull the remote SQLite file or push local changes in case of timestamp or version mismatches.

### B. Standalone Angular Client
The frontend uses standard Angular components with standalone flag enabled (no traditional NgModule configuration). It utilizes:
- **Angular Signals:** For modern reactive state and dependency-free component interactions.
- **Vanilla CSS:** Custom CSS variables define the layout, design system token, and coloring.

---

## 4. Crucial Security Notice (Network Sandboxing)

The backend features a **Network Restrictor** middleware:
- In production, it monkey-patches `socket.socket.connect`.
- Remote/git DB sync is permanently disabled, so the allow-list is now limited to `localhost` and loopbacks (`127.0.0.1`, `::1`). Any other host (including former remotes like `gitlab.com`) is **blocked immediately**.
- Keep this restriction in mind if implementing external network operations; external API integrations (like Google, OpenAI) will be blocked unless explicitly whitelisted in the configuration or the restrictor itself.

---

## 5. Instructions for Running the App

### Running Backend
1. Open a terminal in `backend/` and install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the server:
   ```bash
   python main.py
   ```
   *The server runs by default on `http://localhost:5000`.*

### Running Frontend
1. Open a terminal in `frontend/` and install node modules:
   ```bash
   npm install
   ```
2. Start the development server:
   ```bash
   npm run dev
   ```
   *The dev server runs on `http://localhost:4200` with hot-reloading.*

---

## 6. Critical Agent Guidelines

1. **Strict Code Verification:** Never declare a feature or bug fix completed until you've successfully validated compile status using `npm run build` or similar test runs.
2. **Do NOT Hallucinate:** Only output facts checked in the configuration, code, or databases.
3. **No Injection Violations in Frontend:** When working in Angular, do NOT invoke `effect()` inside lifecycle methods (like `ngOnInit()`). It MUST be declared in class constructors or field initializers to preserve injection context.
4. **Be Transparent About Failures:** If something doesn't compile or a service cannot start, highlight it clearly rather than reporting it as fixed.
