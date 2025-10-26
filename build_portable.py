#!/usr/bin/env python3
"""
Build Portable Windows Distribution for Sakura
This script bundles everything into a single ZIP file for easy distribution.
"""

import os
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path

BUILD_DIR = Path("dist")
PORTABLE_DIR = Path("dist/portable")
APP_NAME = "Sakura"
VERSION = "1.0.0"

def print_step(step):
    print(f"\n{'='*60}")
    print(f"  {step}")
    print(f"{'='*60}\n")

def clean_build_dir():
    """Clean previous build directory"""
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ Cleaned build directory: {BUILD_DIR}")

def build_frontend():
    """Build Angular frontend"""
    print_step("Building Frontend")
    
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        print("❌ Frontend directory not found!")
        return False
    
    # Check if already built
    if (frontend_dir / "dist" / "frontend" / "browser").exists():
        print("✓ Frontend already built")
        return True
    
    # Try to find npm
    import shutil
    npm_cmd = shutil.which("npm")
    if not npm_cmd:
        print("⚠ npm not found in PATH, trying to find Angular build output...")
        # Check if dist exists from previous build
        if (frontend_dir / "dist").exists():
            print("✓ Using existing frontend build")
            return True
        else:
            print("❌ Cannot build frontend without npm")
            return False
    
    # Build frontend
    print("Running: npm run build")
    result = subprocess.run(
        [npm_cmd, "run", "build", "--", "--configuration=production"],
        cwd=frontend_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"❌ Frontend build failed: {result.stderr}")
        return False
    
    print("✓ Frontend built successfully")
    return True

def create_backend_stub():
    """Create portable backend structure"""
    print_step("Creating Portable Backend Structure")
    
    portable_backend = PORTABLE_DIR / "backend"
    portable_backend.mkdir(parents=True, exist_ok=True)
    
    # Copy backend files
    backend_files = [
        ("src", "src"),
        ("main.py", "main.py"),
        ("requirements.txt", "requirements.txt"),
    ]
    
    for src, dest in backend_files:
        src_path = Path(f"backend/{src}")
        if src_path.exists():
            dest_path = portable_backend / dest
            if src_path.is_dir():
                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, dest_path)
            print(f"✓ Copied: {src}")
    
    print("✓ Backend structure created")
    return True

def copy_frontend_dist():
    """Copy frontend dist to portable directory"""
    print_step("Copying Frontend Distribution")
    
    frontend_dist = Path("frontend/dist/frontend/browser")
    portable_frontend = PORTABLE_DIR / "frontend"
    
    if not frontend_dist.exists():
        print("❌ Frontend dist not found!")
        return False
    
    shutil.copytree(frontend_dist, portable_frontend, dirs_exist_ok=True)
    print("✓ Frontend dist copied")
    
    return True

def create_startup_script():
    """Create Windows startup script"""
    print_step("Creating Startup Script")
    
    launcher_script = PORTABLE_DIR / "start_sakura.bat"
    
    script_content = """@echo off
cd /d "%~dp0"

echo.
echo ================================================
echo   Starting Sakura Application
echo ================================================
echo.

:: Try to use embedded Python first
if exist "python\\python.exe" (
    echo Using embedded Python...
    set PYTHON_EXE=python\\python.exe
    set PATH=%~dp0python;%PATH%
) else (
    echo Checking for system Python...
    where python >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo ERROR: Python not found!
        echo.
        echo Please ensure Python 3.10+ is installed.
        echo Download from: https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
    for /f "tokens=*" %%i in ('where python') do set PYTHON_EXE=%%i
)

echo Using Python: %PYTHON_EXE%
echo.

:: Initialize local database if it doesn't exist
if not exist "data\\cache\\dev\\sakura_db.db.db" (
    echo Initializing local database...
    %PYTHON_EXE% backend\\scripts\\database\\init_database.py
    if %ERRORLEVEL% NEQ 0 (
        echo Warning: Database initialization failed
    )
    echo.
)

:: Start backend and frontend using Python launcher
echo Starting Sakura application...
%PYTHON_EXE% backend\\scripts\\portable_launcher.py

pause
"""
    
    with open(launcher_script, 'w') as f:
        f.write(script_content)
    
    # Also copy the launcher script
    portable_launcher = Path("backend/scripts/portable_launcher.py")
    if portable_launcher.exists():
        dest = PORTABLE_DIR / "backend/scripts/portable_launcher.py"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(portable_launcher, dest)
        print(f"✓ Copied portable launcher")
    
    print(f"✓ Created startup script: {launcher_script}")
    return True

def create_readme():
    """Create README for the distribution"""
    readme_path = PORTABLE_DIR / "README.txt"
    
    readme_content = """
Sakura - Portable Windows Distribution
=========================================

QUICK START:
1. Run start_sakura.bat to launch the application
2. Open your browser at http://localhost:4200
3. Create an account with your GitLab token
4. Start managing your database!

SYSTEM REQUIREMENTS:
- Windows 10 or later
- No Python or Node.js installation required
- All dependencies bundled

FIRST TIME SETUP:
1. Run start_sakura.bat
2. Create your user account (required)
3. Enter your GitLab personal access token
4. The app will sync with remote repository

FILES:
- start_sakura.bat: Main launcher script
- backend/: Backend application files
- frontend/: Frontend application files
- data/: Local database storage

TROUBLESHOOTING:
- If ports 4200 or 5000 are in use, close those applications
- Check firewall settings if browser won't connect
- Ensure GitLab token has 'write_repository' permission

SUPPORT:
Visit: https://gitlab.com/android-devops/sakura
"""
    
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    
    print(f"✓ Created README: {readme_path}")
    return True

def create_pyinstaller_spec():
    """Create PyInstaller spec file for bundling"""
    print_step("Creating PyInstaller Configuration")
    
    spec_content = """# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

a = Analysis(
    ['backend/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('backend/src', 'src'),
        ('backend/config', 'config'),
        ('frontend/dist/frontend/browser', 'frontend'),
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'werkzeug.security',
        'werkzeug._internal',
        'sqlite3',
        'pydantic',
        'pydantic_settings',
        'PyJWT',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='sakura-backend',
    debug=False,
    bootloader_ignore_signals=False,
    target_arch='x86_64',
    codesign_identity=None,
    entitlements_file=None,
)
"""
    
    spec_path = Path("sakura.spec")
    with open(spec_path, 'w') as f:
        f.write(spec_content)
    
    print(f"✓ Created PyInstaller spec: {spec_path}")
    return spec_path

def bundle_portable():
    """Create the final portable ZIP"""
    print_step("Creating Portable ZIP")
    
    zip_path = BUILD_DIR / f"{APP_NAME}_Portable_v{VERSION}.zip"
    
    # Remove existing zip
    if zip_path.exists():
        zip_path.unlink()
    
    # Create ZIP file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in PORTABLE_DIR.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(PORTABLE_DIR.parent)
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")
    
    print(f"\n✓ Created portable distribution: {zip_path}")
    print(f"✓ Size: {zip_path.stat().st_size / (1024*1024):.2f} MB")
    
    return zip_path

def main():
    """Main build process"""
    print(f"\n{'#'*60}")
    print(f"  Building Portable Windows Distribution - {APP_NAME} v{VERSION}")
    print(f"{'#'*60}\n")
    
    try:
        # Step 1: Clean
        clean_build_dir()
        
        # Step 2: Build frontend
        if not build_frontend():
            print("\n❌ Build failed at frontend step")
            return 1
        
        # Step 3: Create portable structure
        create_backend_stub()
        copy_frontend_dist()
        
        # Step 4: Create startup script
        create_startup_script()
        
        # Step 5: Create README
        create_readme()
        
        # Step 6: Bundle into ZIP
        zip_path = bundle_portable()
        
        print(f"\n{'#'*60}")
        print(f"  ✓ Build Complete!")
        print(f"{'#'*60}")
        print(f"\nPortable package: {zip_path}")
        print(f"\nTo distribute:")
        print(f"  1. Share the ZIP file with clients")
        print(f"  2. Clients unzip and run start_sakura.bat")
        print(f"  3. Application opens in browser automatically")
        print(f"\n{'#'*60}\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Build failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

