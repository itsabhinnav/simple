#!/usr/bin/env python3
"""
Sakura Backend Application - Main Entry Point

This is the main entry point for the Sakura thick client backend application.
It provides a Flask-based API for database management with Artifactory integration.
"""

import os
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from app_api import create_app
from src.infrastructure.dependency_injection import get_git_database_service

def main():
    """Main entry point for the Sakura backend application."""
    
    # Set environment variables for configuration
    os.environ.setdefault('FLASK_ENV', 'development')
    
    # Create Flask application
    app = create_app()
    
    # Initialize Git database service
    try:
        git_db_service = get_git_database_service()
        if git_db_service.initialize():
            print("✅ Git database service initialized successfully")
        else:
            print("❌ Failed to initialize Git database service")
    except Exception as e:
        print(f"❌ Error initializing Git database service: {e}")
    
    # Get configuration
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"🚀 Starting Sakura Backend Server")
    print(f"📍 Host: {host}")
    print(f"🔌 Port: {port}")
    print(f"🐛 Debug: {debug}")
    print(f"🌐 API Base URL: http://{host}:{port}")
    print(f"💡 Health Check: http://{host}:{port}/health")
    print(f"📊 Database List: http://{host}:{port}/api/databases")
    print(f"📚 API Documentation: http://{host}:{port}/api/docs")
    print(f"🔧 Git Status: http://{host}:{port}/api/git/status")
    
    # Start the application
    app.run(host=host, port=port, debug=debug)

if __name__ == "__main__":
    main()
