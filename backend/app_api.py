"""
Flask Application Factory for API-First Architecture

This module creates and configures the Flask application following API-first principles
with proper separation of concerns, dependency injection, and clean architecture.
"""

from flask import Flask, request
from flask_cors import CORS
from src.infrastructure.dependency_injection import (
    get_user_service, get_test_case_service, get_git_database_service
)
from src.controllers.user_controller import create_user_blueprint
from src.controllers.test_case_controller import create_test_case_blueprint
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
    user_bp = create_user_blueprint(user_service)
    test_case_bp = create_test_case_blueprint(test_case_service)
    
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
            database_service = get_git_database_service()
            databases = database_service.list_databases("default")
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
            info = database_service.get_database_info(database_name, "default")
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
            database_service = get_git_database_service()
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
            
            database_service = get_git_database_service()
            result = database_service.execute_query(query, "default")
            return {
                "success": True,
                "data": result
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
            database_service = get_git_database_service()
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
            database_service = get_git_database_service()
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
    
    logger.info("Legacy routes registered successfully")
