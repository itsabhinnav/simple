"""
Entry point used by the PyInstaller portable build (see build_portable.py
and sakura.spec). This module:

  1. Locates a writable application directory next to the .exe (or under
     %LOCALAPPDATA%\\Sakura when the exe lives in Program Files / a read-only
     location).
  2. Copies the seed SQLite database bundled inside _MEIPASS to that writable
     dir on first launch so the frontend doesn't show "0 everything".
  3. Exports SAKURA_LOCAL_DB_PATH and SAKURA_STATIC_DIR so the rest of the
     backend (main.py, local_database_service.py) ignores the read-only
     bundled paths and uses the writable / extracted ones instead.
  4. Hands control over to run_server.main().

When executed from a regular Python interpreter (sys.frozen is unset) the
script behaves like a thin wrapper around run_server.main() with the same
PYTHONPATH adjustments, so it can be smoke-tested without rebuilding.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _resource_dir() -> Path:
    """Directory holding bundled read-only resources (frontend, config, seed db)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    # Running unfrozen: resources live in the repo root.
    return Path(__file__).resolve().parent.parent


def _app_data_dir() -> Path:
    """Writable directory for the SQLite cache + uploads.

    Preference order:
      1. SAKURA_APP_DATA env var (explicit override).
      2. Directory next to the .exe (one-folder build) or the .exe itself
         (one-file build). This keeps the install fully portable.
      3. %LOCALAPPDATA%\\Sakura on Windows / ~/.local/share/sakura on POSIX
         if the previous location is not writable (e.g. Program Files).
    """
    env_override = os.environ.get("SAKURA_APP_DATA")
    if env_override:
        return Path(env_override).expanduser().resolve()

    if getattr(sys, "frozen", False):
        candidate = Path(sys.executable).resolve().parent
    else:
        candidate = Path(__file__).resolve().parent.parent

    # Probe for writability without leaving litter behind.
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        probe = candidate / ".sakura-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return candidate
    except OSError:
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        else:
            base = Path.home() / ".local/share"
        fallback = base / "Sakura"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _seed_database(resource_dir: Path, app_data_dir: Path) -> Path:
    """Copy the bundled seed sqlite_db.db into the writable app dir on first
    launch. Returns the absolute path of the live database.
    """
    # Keep the same relative layout the unfrozen app expects so log lines and
    # the config.yaml default still make sense.
    target = app_data_dir / "data" / "local" / "dev" / "database" / "sakura_db.db"
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and target.stat().st_size > 0:
        return target

    # The build script drops the seed db at <_MEIPASS>/seed/sakura_db.db so it
    # never clashes with the live one the runtime may write next to itself.
    seed_candidates = [
        resource_dir / "seed" / "sakura_db.db",
        resource_dir / "data" / "local" / "dev" / "database" / "sakura_db.db",
    ]
    for seed in seed_candidates:
        if seed.exists() and seed.stat().st_size > 0:
            shutil.copy2(seed, target)
            print(f"[portable] Seeded database from {seed} -> {target}")
            return target

    print(
        "[portable] WARNING: no seed database found in bundle. The app will "
        "start with an empty schema (HybridDatabaseService creates tables on "
        "first connect)."
    )
    return target


def _prepare_environment() -> None:
    resource_dir = _resource_dir()
    app_data_dir = _app_data_dir()

    # Static frontend (Angular bundle) - always serve from the read-only
    # bundle, never from a stale copy that may be lying around next to the
    # exe.
    static_dir = resource_dir / "backend" / "static"
    if static_dir.is_dir():
        os.environ["SAKURA_STATIC_DIR"] = str(static_dir)

    # SQLite database goes into the writable app dir.
    db_path = _seed_database(resource_dir, app_data_dir)
    os.environ["SAKURA_LOCAL_DB_PATH"] = str(db_path)

    # CD into the writable app dir so any other relative paths the backend
    # writes to (logs, uploads, etc.) land somewhere users can read.
    os.chdir(app_data_dir)

    # Make sure the bundled backend package is importable when running
    # unfrozen (PyInstaller handles this automatically when frozen).
    if not getattr(sys, "frozen", False):
        backend_dir = Path(__file__).resolve().parent
        src_dir = backend_dir / "src"
        for p in (str(src_dir), str(backend_dir), str(backend_dir.parent)):
            if p not in sys.path:
                sys.path.insert(0, p)

    print(f"[portable] resource dir : {resource_dir}")
    print(f"[portable] app data dir : {app_data_dir}")
    print(f"[portable] local db     : {db_path}")
    print(f"[portable] static dir   : {os.environ.get('SAKURA_STATIC_DIR', '<missing>')}")


def main() -> int:
    _prepare_environment()
    # Imported AFTER environment is set up so config_manager sees the right
    # SAKURA_* env vars during module initialisation.
    from run_server import main as run_server_main  # type: ignore
    return run_server_main()


if __name__ == "__main__":
    sys.exit(main())
