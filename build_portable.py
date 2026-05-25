#!/usr/bin/env python3
"""
Build a portable Windows distribution of the Sakura app using PyInstaller.

Pipeline:
  1. Build the Angular frontend in production mode (skipped if up-to-date).
  2. Publish the bundle into ``backend/static/``.
  3. Locate a seed SQLite database (the one the user wants embedded).
  4. Generate a PyInstaller spec that includes the backend source, the
     frontend static bundle, the config.yaml, and the seed DB.
  5. Invoke PyInstaller (one-folder build by default, optionally one-file).
  6. Drop a launcher ``Sakura.bat`` and a copy of ``.env.example`` next to
     the exe so end users can edit secrets without unpacking the bundle.
  7. Optionally zip the whole ``dist/Sakura/`` directory for distribution.

The resulting bundle is self-contained: the target machine does NOT need
Python, pip, or any DLLs preinstalled. The seed database is copied to a
writable location on first launch by ``backend/portable_entry.py``.

Usage::

    # First time: install build dependencies into the venv
    pip install -r backend/requirements-portable.txt

    # Default build (one-folder, no zip)
    python build_portable.py

    # One-file exe (slower startup but a single file to ship)
    python build_portable.py --onefile

    # Skip rebuilding the Angular bundle (use the existing backend/static/)
    python build_portable.py --skip-frontend

    # Pick a specific seed database
    python build_portable.py --seed-db data/remote/data/remote/dev/database/sakura_db.db

    # Produce a ZIP next to the dist folder for distribution
    python build_portable.py --zip
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "Sakura"
VERSION = "1.0.0"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
SPEC_FILE = ROOT / "sakura.spec"
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist" / "frontend" / "browser"
STATIC_DIR = BACKEND_DIR / "static"

DEFAULT_SEED_CANDIDATES = [
    ROOT / "data" / "local" / "dev" / "database" / "sakura_db.db",
    ROOT / "data" / "remote" / "data" / "remote" / "dev" / "database" / "sakura_db.db",
]


def banner(msg: str) -> None:
    print()
    print("=" * 64)
    print(f"  {msg}")
    print("=" * 64)


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    pretty = " ".join(str(c) for c in cmd)
    print(f"$ {pretty}")
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None, env=full_env)


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[build] PyInstaller not found; installing build deps...")
        req = BACKEND_DIR / "requirements-portable.txt"
        run([sys.executable, "-m", "pip", "install", "-r", str(req)])


def build_frontend(skip: bool) -> None:
    banner("Frontend")
    if skip:
        if not STATIC_DIR.is_dir() or not (STATIC_DIR / "index.html").exists():
            sys.exit(
                "[build] --skip-frontend was passed but backend/static/index.html "
                "is missing. Run the regular setup.* script first or drop the flag."
            )
        print(f"[build] Reusing existing static bundle at {STATIC_DIR}")
        return

    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        sys.exit("[build] npm not found in PATH; cannot build the Angular bundle.")

    if not (FRONTEND_DIR / "node_modules" / ".package-lock.json").exists():
        run([npm, "ci"], cwd=FRONTEND_DIR)
    run([npm, "run", "build"], cwd=FRONTEND_DIR)

    if not FRONTEND_DIST.is_dir():
        sys.exit(f"[build] Expected Angular output at {FRONTEND_DIST} but it does not exist.")

    if STATIC_DIR.exists():
        shutil.rmtree(STATIC_DIR)
    STATIC_DIR.mkdir(parents=True)
    for item in FRONTEND_DIST.iterdir():
        target = STATIC_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    index = STATIC_DIR / "index.html"
    index_csr = STATIC_DIR / "index.csr.html"
    if not index.exists() and index_csr.exists():
        shutil.copy2(index_csr, index)
    print(f"[build] Published frontend bundle to {STATIC_DIR}")


def resolve_seed_db(explicit: str | None) -> Path | None:
    if explicit:
        p = (ROOT / explicit).resolve() if not Path(explicit).is_absolute() else Path(explicit).resolve()
        if not p.exists():
            sys.exit(f"[build] --seed-db {p} does not exist.")
        return p

    # Pick the largest existing candidate (more data > less data).
    found = [c for c in DEFAULT_SEED_CANDIDATES if c.exists() and c.stat().st_size > 0]
    if not found:
        print("[build] No seed database found - the bundle will start with an empty schema.")
        return None
    found.sort(key=lambda p: p.stat().st_size, reverse=True)
    print(f"[build] Auto-selected seed database: {found[0]} ({found[0].stat().st_size / 1024:.1f} KiB)")
    return found[0]


def write_spec(onefile: bool, seed_db: Path | None) -> Path:
    banner("Generating PyInstaller spec")

    backend_src = (BACKEND_DIR / "src").as_posix()
    backend_dir_posix = BACKEND_DIR.as_posix()
    static_dir_posix = STATIC_DIR.as_posix()
    config_yaml_posix = (BACKEND_DIR / "config" / "config.yaml").as_posix()
    entry_posix = (BACKEND_DIR / "portable_entry.py").as_posix()

    # Note: src/ and config/ Python packages are picked up automatically via
    # pathex + collect_submodules below, so the only thing we have to ship
    # as a data file is config.yaml itself (read with open(), not imported)
    # and the seed database.
    seed_data_line = ""
    if seed_db:
        seed_data_line = f"    (r'{seed_db.as_posix()}', 'seed'),\n"

    spec = f"""# -*- mode: python ; coding: utf-8 -*-
# Auto-generated by build_portable.py - do not edit by hand.
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

backend_datas = [
    (r'{static_dir_posix}', 'backend/static'),
    (r'{config_yaml_posix}', 'backend/config'),
    (r'{config_yaml_posix}', 'config'),
{seed_data_line}]

# Collect compiled extensions and data files for packages that ship native
# code or rely on runtime resource lookups. Without these the bundled exe
# crashes at startup with "Module ... has no attribute ..." or fails to
# locate cryptography's bindings.
collected = []
for pkg in (
    'cryptography', 'pydantic', 'pydantic_settings',
    'flask', 'flask_cors', 'flask_limiter', 'flask_talisman',
    'werkzeug', 'jinja2', 'openpyxl', 'waitress', 'yaml',
):
    try:
        datas, binaries, hiddenimports = collect_all(pkg)
    except Exception:
        continue
    collected.append((datas, binaries, hiddenimports))

all_datas = list(backend_datas)
all_binaries = []
all_hidden = []
for datas, binaries, hiddenimports in collected:
    all_datas.extend(datas)
    all_binaries.extend(binaries)
    all_hidden.extend(hiddenimports)

all_hidden.extend([
    # The backend layered modules are imported through string lookups in a few
    # places (blueprints, dependency_injection), so help PyInstaller see them.
    *collect_submodules('src'),
    *collect_submodules('config'),
    # WSGI servers
    'waitress', 'waitress.server',
    # SQLite is in the stdlib but PyInstaller occasionally misses the
    # _sqlite3 DLL on Windows when other hooks rewrite sys.modules.
    'sqlite3', '_sqlite3',
    # cryptography backends
    'cryptography.hazmat.bindings._rust',
    # psycopg2 is imported at module-load time by postgresql_database_service.
    'psycopg2',
])

a = Analysis(
    [r'{entry_posix}'],
    pathex=[r'{backend_dir_posix}', r'{backend_src}'],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy.testing', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
"""

    if onefile:
        spec += f"""
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""
    else:
        spec += f"""
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='{APP_NAME}',
)
"""

    SPEC_FILE.write_text(spec, encoding="utf-8")
    print(f"[build] Wrote {SPEC_FILE}")
    return SPEC_FILE


def run_pyinstaller(spec: Path) -> Path:
    banner("Running PyInstaller")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    target = DIST_DIR / APP_NAME
    if target.exists():
        shutil.rmtree(target)
    onefile_exe = DIST_DIR / f"{APP_NAME}.exe"
    if onefile_exe.exists():
        onefile_exe.unlink()

    run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        str(spec),
    ])

    if target.is_dir():
        return target
    if onefile_exe.exists():
        return onefile_exe
    sys.exit("[build] PyInstaller finished but no output was produced under dist/.")


def write_launcher_and_env(output: Path) -> None:
    """Drop a friendly .bat launcher and a copy of .env.example next to the exe."""
    if output.is_file():
        target_dir = output.parent
    else:
        target_dir = output

    launcher = target_dir / "Start-Sakura.bat"
    launcher.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        "cd /d \"%~dp0\"\r\n"
        "echo Starting Sakura...\r\n"
        f"\"%~dp0{APP_NAME}.exe\"\r\n"
        "if errorlevel 1 (\r\n"
        "  echo.\r\n"
        "  echo Sakura exited with an error. Press any key to close.\r\n"
        "  pause >nul\r\n"
        ")\r\n",
        encoding="utf-8",
    )
    print(f"[build] Wrote launcher: {launcher}")

    env_example = ROOT / ".env.example"
    if env_example.exists():
        shutil.copy2(env_example, target_dir / ".env.example")
        print(f"[build] Copied .env.example into {target_dir}")

    readme = target_dir / "README.txt"
    readme.write_text(
        f"""{APP_NAME} v{VERSION} - Portable Windows distribution

QUICK START
-----------
1. Double-click Start-Sakura.bat (or {APP_NAME}.exe directly).
2. Wait for the console to print "Starting Waitress" (5-10 seconds on first
   launch while the seed database is copied into place).
3. Open http://localhost:5000 in your browser.

CONFIGURATION
-------------
Copy .env.example to .env in this directory and edit secrets / ports as
needed. The exe reads it on every launch.

DATA LOCATION
-------------
The live SQLite database lives at:
    <this folder>\\data\\local\\dev\\database\\sakura_db.db
It is seeded from the bundled snapshot on first launch and persists across
restarts. Delete the file to reset to the snapshot.

TROUBLESHOOTING
---------------
- Port 5000 already in use? Set PORT=5050 in .env and relaunch.
- Antivirus quarantines the exe? PyInstaller bundles trigger generic
  heuristics; add this folder to your AV's allow list.
""",
        encoding="utf-8",
    )
    print(f"[build] Wrote {readme}")


def zip_output(output: Path) -> Path:
    banner("Zipping distribution")
    if output.is_file():
        # one-file: zip the exe + sidecar files (launcher, .env.example).
        archive = DIST_DIR / f"{APP_NAME}_Portable_v{VERSION}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in output.parent.iterdir():
                if path == archive:
                    continue
                zf.write(path, arcname=path.name)
    else:
        archive = DIST_DIR / f"{APP_NAME}_Portable_v{VERSION}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in output.rglob("*"):
                if file.is_file():
                    zf.write(file, arcname=file.relative_to(output.parent))
    size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"[build] Created {archive} ({size_mb:.1f} MiB)")
    return archive


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--onefile", action="store_true", help="Produce a single .exe (slower startup, easier to ship).")
    p.add_argument("--skip-frontend", action="store_true", help="Reuse the existing backend/static/ instead of rebuilding the Angular bundle.")
    p.add_argument("--seed-db", default=None, help="Path (absolute or relative to the repo root) to the SQLite file to embed as the seed DB. If omitted the script picks the largest matching candidate.")
    p.add_argument("--zip", action="store_true", help="Also produce dist/Sakura_Portable_vX.Y.Z.zip ready for distribution.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    ensure_pyinstaller()
    build_frontend(args.skip_frontend)

    seed_db = resolve_seed_db(args.seed_db)
    if seed_db is None:
        # Still continue, but warn loudly so the user knows.
        print(
            "[build] WARNING: building without a seed database. End users will "
            "see an empty schema until something writes to it."
        )

    spec = write_spec(args.onefile, seed_db)
    output = run_pyinstaller(spec)
    write_launcher_and_env(output)

    if args.zip:
        zip_output(output)

    banner("Done")
    if output.is_dir():
        exe = output / f"{APP_NAME}.exe"
    else:
        exe = output
    print(f"  Executable : {exe}")
    print(f"  Launcher   : {(output if output.is_dir() else output.parent) / 'Start-Sakura.bat'}")
    print("  Test it    : double-click the launcher, then open http://localhost:5000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
