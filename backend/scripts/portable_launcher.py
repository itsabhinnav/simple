#!/usr/bin/env python3
"""
Portable Launcher for Sakura
This script initializes the app and handles the startup flow.
"""

import os
import sys
import time
import webbrowser
import http.server
import socketserver
from pathlib import Path
import subprocess
import threading

def check_backend_health():
    """Check if backend is running"""
    try:
        import requests
        response = requests.get("http://localhost:5000/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def start_backend():
    """Start the Flask backend server"""
    import sys
    
    # Add src to path
    backend_path = Path(__file__).parent.parent
    src_path = backend_path / "src"
    sys.path.insert(0, str(src_path))
    
    # Import and run Flask app
    from src.infrastructure.dependency_injection import get_container
    from backend.main import create_app
    
    app = create_app()
    app.run(host='127.0.0.1', port=5000, debug=False)

def start_frontend():
    """Start frontend HTTP server"""
    os.chdir('frontend')
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", 4200), handler)
    httpd.serve_forever()

def main():
    print("\n" + "="*60)
    print("  Sakura - Portable Application Launcher")
    print("="*60 + "\n")
    
    # Initialize local database
    print("Initializing local database...")
    db_init_path = Path(__file__).parent / "database" / "init_database.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(db_init_path)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ Local database initialized\n")
        else:
            print("⚠ Warning: Database initialization had issues\n")
    except Exception as e:
        print(f"⚠ Could not initialize database: {e}\n")
    
    # Start backend in background thread
    print("Starting backend server...")
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()
    
    # Wait for backend to be ready
    print("Waiting for backend to be ready...", end="", flush=True)
    for i in range(30):  # Wait up to 30 seconds
        if check_backend_health():
            print(" ✓")
            break
        time.sleep(1)
        if i % 3 == 0:
            print(".", end="", flush=True)
    else:
        print("\n⚠ Backend failed to start properly")
    
    # Start frontend in background thread
    print("Starting frontend server...")
    frontend_thread = threading.Thread(target=start_frontend, daemon=True)
    frontend_thread.start()
    
    # Wait a bit for frontend to start
    time.sleep(2)
    
    # Open browser
    print("\nOpening browser...")
    webbrowser.open("http://localhost:4200")
    
    print("\n" + "="*60)
    print("  Sakura is now running!")
    print("="*60)
    print("\n  Backend: http://localhost:5000")
    print("  Frontend: http://localhost:4200")
    print("\n  Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()

