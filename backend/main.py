#!/usr/bin/env python3
"""
Sakura Backend Application - Main Entry Point

This is the main entry point for the Sakura thick client backend application.
It provides a Flask-based API for database management with Artifactory integration.
"""

import os
import sys
from pathlib import Path
from flask import Flask, request, send_from_directory, jsonify
from flask_cors import CORS

# Load environment variables from .env file at the project root if present.
# Done before any other backend imports so that secrets like JWT_SECRET_KEY,
# ENCRYPTION_KEY, ALLOWED_ORIGINS, ENABLE_NETWORK_RESTRICTIONS etc. are
# visible to the rest of the application during module-level initialisation.
try:
    from dotenv import load_dotenv

    _backend_dir = Path(__file__).resolve().parent
    for _env_path in (_backend_dir / ".env", _backend_dir.parent / ".env"):
        if _env_path.exists():
            load_dotenv(_env_path, override=False)
except Exception:
    pass

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Enable network restrictions for security (optional, can be disabled for development)
ENABLE_NETWORK_RESTRICTIONS = os.environ.get('ENABLE_NETWORK_RESTRICTIONS', 'false').lower() == 'true'

if ENABLE_NETWORK_RESTRICTIONS:
    try:
        from src.infrastructure.network_restrictor import enable_network_restrictions, verify_network_isolation
        enable_network_restrictions()
        print("[SECURITY] Network restrictions enabled")
    except Exception as e:
        print(f"[WARNING] Could not enable network restrictions: {e}")
else:
    print("[INFO] Network restrictions disabled (set ENABLE_NETWORK_RESTRICTIONS=true to enable)")

from src.infrastructure.dependency_injection import (
    get_user_service, get_test_case_service, get_hybrid_database_service, get_git_database_service,
    get_requirement_service, get_design_ticket_service, get_spec_service
)
from src.controllers.user_controller import create_user_blueprint
from src.controllers.test_case_controller import create_test_case_blueprint
from src.controllers.auth_controller import create_auth_blueprint
from src.controllers.admin_controller import create_admin_blueprint
from src.controllers.requirement_controller import create_requirement_blueprint
from src.controllers.design_ticket_controller import create_design_ticket_blueprint
from src.controllers.spec_controller import create_spec_blueprint
from src.middleware.error_handlers import (
    setup_error_handlers, setup_request_logging, 
    setup_cors_headers, setup_request_validation, setup_api_documentation,
    setup_security_headers, setup_rate_limiting
)
from src.middleware.auth_middleware import get_current_username
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


def create_app() -> Flask:
    """
    Create and configure the Flask application.
    
    Returns:
        Flask: Configured Flask application instance
    """
    # In the portable PyInstaller bundle the static folder lives inside the
    # _MEIPASS extraction directory, not next to a real main.py on disk.
    # SAKURA_STATIC_DIR (set by portable_entry.py) lets us point Flask at
    # the absolute extracted path instead of relying on relative resolution.
    static_dir = os.environ.get('SAKURA_STATIC_DIR') or 'static'
    app = Flask(__name__, static_folder=static_dir)
    
    # Disable strict slashes to prevent redirects
    app.url_map.strict_slashes = False
    
    # Determine development mode from environment (app.debug is not yet set at this point
    # because Flask only flips it when app.run(debug=True) is called later in main()).
    is_dev = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.config['SAKURA_IS_DEV'] = is_dev
    
    # Configure CORS. In development, allow any origin so the Angular dev server
    # (http://localhost:4200) can talk to the API on http://localhost:5000.
    cors_origins = ["*"] if is_dev else os.environ.get('ALLOWED_ORIGINS', 'https://sakura.company.com').split(',')
    CORS(app, origins=cors_origins, methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], 
         allow_headers=["Content-Type", "Authorization"], supports_credentials=True)
    
    # Setup middleware
    setup_error_handlers(app)
    setup_request_logging(app)
    setup_cors_headers(app)
    setup_request_validation(app)
    setup_api_documentation(app)
    setup_security_headers(app)
    setup_rate_limiting(app)
    
    @app.before_request
    def inject_current_user():
        from flask import g
        from src.middleware.auth_middleware import get_current_user
        g.current_user = get_current_user()
        g.current_username = g.current_user.get('username') if g.current_user else None
    
    # Register API blueprints
    register_api_routes(app)
    
    # Register legacy routes for backward compatibility
    register_legacy_routes(app)
    
    # Serve static frontend files
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        static_path = os.path.join(app.static_folder, path)
        if path and os.path.isfile(static_path):
            return send_from_directory(app.static_folder, path)
        route_index = os.path.join(static_path, 'index.html')
        if path and os.path.isdir(static_path) and os.path.isfile(route_index) and os.path.getsize(route_index) > 0:
            return send_from_directory(static_path, 'index.html')

        # For Angular routing, serve index.html for all other paths
        return send_from_directory(app.static_folder, 'index.html')
    
    logger.info("Flask application created successfully")
    return app


def register_api_routes(app: Flask) -> None:
    """Register API-first routes using blueprints."""
    
    # Get services from dependency injection
    user_service = get_user_service()
    test_case_service = get_test_case_service()
    requirement_service = get_requirement_service()
    design_ticket_service = get_design_ticket_service()
    spec_service = get_spec_service()
    
    # Create and register blueprints
    auth_bp = create_auth_blueprint(user_service)
    user_bp = create_user_blueprint(user_service)
    test_case_bp = create_test_case_blueprint(test_case_service)
    admin_bp = create_admin_blueprint()
    requirement_bp = create_requirement_blueprint(requirement_service)
    design_ticket_bp = create_design_ticket_blueprint(design_ticket_service)
    spec_bp = create_spec_blueprint(spec_service)
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(test_case_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(requirement_bp)
    app.register_blueprint(design_ticket_bp)
    app.register_blueprint(spec_bp)
    
    logger.info("API routes registered successfully")


def register_legacy_routes(app: Flask) -> None:
    """Register legacy routes for backward compatibility."""
    
    @app.route('/api/status')
    def api_status():
        """API status endpoint."""
        return {
            "status": "ok",
            "message": "Sakura API is running",
            "version": "1.0.0",
            "endpoints": {
                "health": "/health",
                "api_docs": "/api/docs",
                "auth": "/api/auth",
                "users": "/api/users",
                "test_cases": "/api/test-cases",
                "requirements": "/api/requirements"
            }
        }
    
    @app.route('/health')
    def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "message": "Sakura API is running",
            "version": "1.0.0"
        }
    
    @app.route('/api/all/')
    def get_all_data():
        """Get all data from all tables."""
        try:
            import sqlite3
            from pathlib import Path
            
            # Get database path from configuration
            from src.infrastructure.configuration_manager import get_config_manager
            config_manager = get_config_manager()
            local_db_path = config_manager.get_config("database.local_db_path", "data/local/dev/database/local.db")
            
            # Resolve path relative to backend directory
            backend_dir = Path(__file__).parent
            db_path = backend_dir / local_db_path
            
            if not db_path.exists():
                return {
                    "success": False,
                    "error": "Database not found",
                    "path": str(db_path)
                }, 404
            
            # Connect to database
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            try:
                # Get all table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [t[0] for t in cursor.fetchall() if t[0] != 'sqlite_sequence']
                
                all_data = {}
                
                for table in tables:
                    # Get all rows from the table
                    cursor.execute(f"SELECT * FROM {table}")
                    rows = cursor.fetchall()
                    
                    # Convert rows to dictionaries
                    table_data = []
                    for row in rows:
                        table_data.append(dict(row))
                    
                    all_data[table] = {
                        "count": len(table_data),
                        "data": table_data
                    }
                
                return {
                    "success": True,
                    "message": "All data retrieved successfully",
                    "database": str(db_path.name),
                    "tables": all_data,
                    "total_tables": len(tables),
                    "total_rows": sum(data["count"] for data in all_data.values())
                }
                
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Failed to get all data: {e}")
            return {
                "success": False,
                "error": str(e)
            }, 500
    
    @app.route('/api/databases')
    def list_databases():
        """List available databases (legacy endpoint)."""
        try:
            database_service = get_hybrid_database_service()
            databases = database_service.list_databases()
            return {
                "success": True,
                "data": databases
            }
        except Exception as e:
            logger.error(f"Failed to list databases: {e}")
            return {
                "success": False,
                "error": str(e)
            }, 500
    
    @app.route('/api/databases/<database_name>/info')
    def get_database_info(database_name):
        """Get database information (legacy endpoint)."""
        try:
            database_service = get_git_database_service()
            info = database_service.get_database_info()
            return {
                "success": True,
                "data": info
            }
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {
                "success": False,
                "error": str(e)
            }, 500
    
    @app.route('/api/databases/<database_name>/sync', methods=['POST'])
    def sync_database(database_name):
        """Sync database (legacy endpoint)."""
        try:
            database_service = get_hybrid_database_service()
            result = database_service.sync_database(database_name, "default")
            return {
                "success": True,
                "message": "Database synced successfully",
                "data": result
            }
        except Exception as e:
            logger.error(f"Failed to sync database: {e}")
            return {
                "success": False,
                "error": str(e)
            }, 500
    
    @app.route('/api/databases/<database_name>/query', methods=['POST'])
    def execute_query(database_name):
        """Execute database query (legacy endpoint)."""
        try:
            query = request.json.get('query') if request.is_json else request.form.get('query')
            if not query:
                return {
                    "success": False,
                    "error": "Query parameter is required"
                }, 400
            
            database_service = get_hybrid_database_service()
            result = database_service.execute_query(query, "default")
            
            # Format response to match frontend expectations
            if result.get("success") and result.get("data"):
                # Extract columns from first row if data exists
                columns = []
                if result["data"]:
                    columns = list(result["data"][0].keys())
                
                return {
                    "success": True,
                    "data": {
                        "columns": columns,
                        "data": result["data"],
                        "row_count": result.get("row_count", len(result["data"]))
                    }
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Query failed")
                }
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            return {
                "success": False,
                "error": str(e)
            }, 500
    
    @app.route('/api/git/status')
    def get_git_status():
        """Get Git repository status."""
        try:
            database_service = get_hybrid_database_service()
            status = database_service.get_repo_status()
            return {
                "success": True,
                "data": status
            }
        except Exception as e:
            logger.error(f"Failed to get git status: {e}")
            return {
                "success": False,
                "error": str(e)
            }, 500
    
    @app.route('/api/git/pull', methods=['POST'])
    def pull_latest_changes():
        """Pull latest changes from Git repository."""
        try:
            database_service = get_hybrid_database_service()
            success = database_service.pull_latest_changes()
            return {
                "success": success,
                "message": "Latest changes pulled successfully" if success else "Failed to pull latest changes"
            }
        except Exception as e:
            logger.error(f"Failed to pull latest changes: {e}")
            return {
                "success": False,
                "error": str(e)
            }, 500
    
    @app.route('/api/sync/status', methods=['GET'])
    def get_sync_status():
        """Get synchronization status."""
        try:
            hybrid_service = get_hybrid_database_service()
            status = hybrid_service.get_sync_status()
            return jsonify(status)
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route('/api/sync/force', methods=['POST'])
    def force_sync():
        """Force immediate synchronization."""
        try:
            hybrid_service = get_hybrid_database_service()
            success = hybrid_service.force_sync()
            return jsonify({
                "success": success,
                "message": "Sync completed" if success else "Sync failed"
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route('/api/users/<int:user_id>/preferences', methods=['GET'])
    def get_user_preferences(user_id):
        """Get user preferences."""
        try:
            from src.infrastructure.dependency_injection import get_local_database_service
            local_service = get_local_database_service()
            preferences = local_service.get_user_preferences(user_id)
            return jsonify({
                "success": True,
                "data": preferences
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route('/api/users/<int:user_id>/preferences', methods=['POST'])
    def set_user_preference(user_id):
        """Set user preference."""
        try:
            from src.infrastructure.dependency_injection import get_local_database_service
            data = request.get_json()
            if not data or 'key' not in data or 'value' not in data:
                return jsonify({
                    "success": False,
                    "error": "Key and value are required"
                }), 400
            
            local_service = get_local_database_service()
            success = local_service.set_user_preference(user_id, data['key'], data['value'])
            
            return jsonify({
                "success": success,
                "message": "Preference set" if success else "Failed to set preference"
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    logger.info("Legacy routes registered successfully")


def main():
    """Main entry point for the Sakura backend application."""
    
    # Set environment variables for configuration
    os.environ.setdefault('FLASK_ENV', 'development')
    
    # Create Flask application
    app = create_app()
    
    # Initialize hybrid database service
    try:
        hybrid_service = get_hybrid_database_service()
        if hybrid_service.initialize():
            print("[SUCCESS] Hybrid database service initialized successfully")
        else:
            print("[ERROR] Failed to initialize hybrid database service")
            print("[WARNING] Continuing with limited functionality...")
    except Exception as e:
        print(f"[ERROR] Error initializing hybrid database service: {e}")
        print("[WARNING] Continuing with limited functionality...")
    
    # Provision master admin account
    try:
        from src.infrastructure.master_admin_provision import provision_master_admin
        if provision_master_admin():
            print("[SUCCESS] Master admin account provisioned")
        else:
            print("[WARNING] Failed to provision master admin account")
    except Exception as e:
        print(f"[ERROR] Error provisioning master admin account: {e}")
        print("[WARNING] Continuing without master admin account...")
    
    # Get configuration
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"[START] Starting Sakura Backend Server")
    print(f"[INFO] Host: {host}")
    print(f"[INFO] Port: {port}")
    print(f"[INFO] Debug: {debug}")
    print(f"[INFO] API Base URL: http://{host}:{port}")
    print(f"[INFO] Health Check: http://{host}:{port}/health")
    print(f"[INFO] Database List: http://{host}:{port}/api/databases")
    print(f"[INFO] API Documentation: http://{host}:{port}/api/docs")
    print(f"[INFO] Git Status: http://{host}:{port}/api/git/status")
    
    # Start the application
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
