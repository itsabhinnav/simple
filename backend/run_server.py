#!/usr/bin/env python3
"""
Cross-platform production launcher for the Sakura backend.

Behaviour:
- On Linux/macOS: runs Gunicorn with sensible worker defaults.
- On Windows: runs Waitress (Gunicorn is POSIX-only).
- Falls back to Flask's built-in development server when WAITRESS / GUNICORN
  are unavailable or when SAKURA_USE_DEV_SERVER=1 is set (e.g. during quick
  smoke-testing in environments without the production deps installed).

Environment variables:
- HOST            (default 0.0.0.0)
- PORT            (default 5000)
- WORKERS         (default: 2 * CPU_COUNT + 1, capped at 8)
- THREADS         (Waitress only, default 8)
- SAKURA_USE_DEV_SERVER=1  -> force Flask's dev server

This module also bootstraps the backend the same way main.py does
(initialise the hybrid database, provision the master admin account)
before handing control over to the WSGI server.
"""
from __future__ import annotations

import os
import sys
import platform
import multiprocessing
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.chdir(BACKEND_DIR)

try:
    from dotenv import load_dotenv
    for _env_path in (BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"):
        if _env_path.exists():
            load_dotenv(_env_path, override=False)
except Exception:
    pass


def _bootstrap_app():
    """Build the Flask app exactly like main.main() does, but without app.run()."""
    from main import create_app  # type: ignore
    from src.infrastructure.dependency_injection import get_hybrid_database_service

    app = create_app()

    try:
        hybrid = get_hybrid_database_service()
        if hybrid.initialize():
            print("[SUCCESS] Hybrid database service initialized")
        else:
            print("[WARNING] Hybrid database init returned False; continuing")
    except Exception as exc:
        print(f"[WARNING] Hybrid database init failed: {exc}")

    try:
        from src.infrastructure.master_admin_provision import provision_master_admin
        if provision_master_admin():
            print("[SUCCESS] Master admin account provisioned")
        else:
            print("[WARNING] Master admin provisioning returned False")
    except Exception as exc:
        print(f"[WARNING] Master admin provisioning failed: {exc}")

    return app


def _resolve_workers() -> int:
    env_value = os.environ.get("WORKERS")
    if env_value and env_value.isdigit():
        return max(1, int(env_value))
    cpu = multiprocessing.cpu_count() or 1
    return min(8, 2 * cpu + 1)


def main() -> int:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    workers = _resolve_workers()
    threads = int(os.environ.get("THREADS", "8"))
    force_dev = os.environ.get("SAKURA_USE_DEV_SERVER", "0") == "1"

    print("=" * 60)
    print(" Sakura Backend - production launcher")
    print("=" * 60)
    print(f"  Platform : {platform.system()} ({platform.python_version()})")
    print(f"  Host     : {host}")
    print(f"  Port     : {port}")
    print(f"  Workers  : {workers}")
    print("=" * 60)

    app = _bootstrap_app()

    if force_dev:
        print("[INFO] SAKURA_USE_DEV_SERVER=1 -> using Flask dev server")
        app.run(host=host, port=port, debug=False, use_reloader=False)
        return 0

    is_windows = platform.system().lower().startswith("win")

    if not is_windows:
        try:
            from gunicorn.app.base import BaseApplication

            class _Gunicorn(BaseApplication):
                def __init__(self, application, options):
                    self._app = application
                    self._opts = options
                    super().__init__()

                def load_config(self):
                    for key, value in self._opts.items():
                        if key in self.cfg.settings and value is not None:
                            self.cfg.set(key.lower(), value)

                def load(self):
                    return self._app

            options = {
                "bind": f"{host}:{port}",
                "workers": workers,
                "threads": threads,
                "timeout": 120,
                "accesslog": "-",
                "errorlog": "-",
            }
            print("[INFO] Starting Gunicorn")
            _Gunicorn(app, options).run()
            return 0
        except ImportError:
            print("[WARNING] Gunicorn not installed; falling back to Waitress")

    try:
        from waitress import serve

        print("[INFO] Starting Waitress")
        serve(app, host=host, port=port, threads=threads)
        return 0
    except ImportError:
        print("[WARNING] Waitress not installed; falling back to Flask dev server")
        app.run(host=host, port=port, debug=False, use_reloader=False)
        return 0


if __name__ == "__main__":
    sys.exit(main())
