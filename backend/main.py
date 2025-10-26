#!/usr/bin/env python3
"""
Sakura Backend Application - Main Entry Point

This is the main entry point for the Sakura thick client backend application.
It provides a Flask-based API for database management with Artifactory integration.
"""

import os
import sys
from pathlib import Path
from flask import Flask, request
from flask_cors import CORS

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.infrastructure.dependency_injection import (
    get_user_service, get_test_case_service, get_hybrid_database_service, get_git_database_service
)
from src.controllers.user_controller import create_user_blueprint
from src.controllers.test_case_controller import create_test_case_blueprint
from src.controllers.auth_controller import create_auth_blueprint
from src.middleware.error_handlers import (
    setup_error_handlers, setup_request_logging, 
    setup_cors_headers, setup_request_validation, setup_api_documentation
)
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


def create_app() -> Flask:
    """
    Create and configure the Flask application.
    
    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)
    
    # Configure CORS
    CORS(app, origins=["*"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    
    # Setup middleware
    setup_error_handlers(app)
    setup_request_logging(app)
    setup_cors_headers(app)
    setup_request_validation(app)
    setup_api_documentation(app)
    
    # Register API blueprints
    register_api_routes(app)
    
    # Register legacy routes for backward compatibility
    register_legacy_routes(app)
    
    logger.info("Flask application created successfully")
    return app


def register_api_routes(app: Flask) -> None:
    """Register API-first routes using blueprints."""
    
    # Get services from dependency injection
    user_service = get_user_service()
    test_case_service = get_test_case_service()
    
    # Create and register blueprints
    auth_bp = create_auth_blueprint(user_service)
    user_bp = create_user_blueprint(user_service)
    test_case_bp = create_test_case_blueprint(test_case_service)
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(test_case_bp)
    
    logger.info("API routes registered successfully")


def register_legacy_routes(app: Flask) -> None:
    """Register legacy routes for backward compatibility."""
    
    @app.route('/health')
    def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "message": "Sakura API is running",
            "version": "1.0.0"
        }
    
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
