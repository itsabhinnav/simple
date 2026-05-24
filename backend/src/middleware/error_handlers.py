from flask import Flask, request, jsonify
from datetime import datetime
import logging
import os
from typing import Dict, Any
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

# Global limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "200 per hour"]
)


def setup_error_handlers(app: Flask) -> None:
    """Setup global error handlers for the Flask application"""
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "The request was invalid or cannot be served",
            "timestamp": datetime.utcnow().isoformat()
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            "success": False,
            "error": "Unauthorized",
            "message": "Authentication is required",
            "timestamp": datetime.utcnow().isoformat()
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": "Access to this resource is forbidden",
            "timestamp": datetime.utcnow().isoformat()
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "success": False,
            "error": "Not Found",
            "message": "The requested resource was not found",
            "timestamp": datetime.utcnow().isoformat()
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            "success": False,
            "error": "Method Not Allowed",
            "message": "The method is not allowed for this resource",
            "timestamp": datetime.utcnow().isoformat()
        }), 405
    
    @app.errorhandler(422)
    def unprocessable_entity(error):
        return jsonify({
            "success": False,
            "error": "Unprocessable Entity",
            "message": "The request was well-formed but contains semantic errors",
            "timestamp": datetime.utcnow().isoformat()
        }), 422
    
    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat()
        }), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handle all unhandled exceptions"""
        app.logger.error(f"Unhandled exception: {str(error)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat()
        }), 500


def setup_request_logging(app: Flask) -> None:
    """Setup request logging middleware"""
    
    @app.before_request
    def log_request_info():
        """Log request information"""
        app.logger.info(f"Request: {request.method} {request.url}")
        app.logger.info(f"Headers: {dict(request.headers)}")
        if request.is_json:
            app.logger.info(f"JSON Body: {request.get_json()}")
    
    @app.after_request
    def log_response_info(response):
        """Log response information"""
        app.logger.info(f"Response: {response.status_code}")
        return response


def setup_cors_headers(app: Flask) -> None:
    """Setup CORS headers for API responses"""
    # CORS headers are already handled by Flask-CORS in main.py
    # This function is kept for backward compatibility but does nothing
    pass


def setup_request_validation(app: Flask) -> None:
    """Setup request validation middleware"""
    
    @app.before_request
    def validate_request():
        """Validate incoming requests"""
        # OPTIONS requests are handled by Flask-CORS
        if request.method == 'OPTIONS':
            return
        
        # Validate Content-Type for POST/PUT requests. File import endpoints use multipart forms.
        content_type = request.content_type or ''
        is_multipart = content_type.startswith('multipart/form-data')
        if request.method in ['POST', 'PUT'] and request.is_json is False and not is_multipart:
            return jsonify({
                "success": False,
                "error": "Invalid Content-Type",
                "message": "Content-Type must be application/json or multipart/form-data for POST/PUT requests"
            }), 400


def setup_api_documentation(app: Flask) -> None:
    """Setup API documentation endpoint"""
    
    @app.route('/api/docs')
    def api_documentation():
        """Return API documentation"""
        return jsonify({
            "success": True,
            "message": "Sakura API Documentation",
            "version": "1.0.0",
            "endpoints": {
                "users": {
                    "GET /api/users": "Get all users",
                    "POST /api/users": "Create a new user",
                    "GET /api/users/{id}": "Get user by ID",
                    "PUT /api/users/{id}": "Update user",
                    "DELETE /api/users/{id}": "Delete user"
                },
                "test_cases": {
                    "GET /api/test-cases": "Get all test cases",
                    "POST /api/test-cases": "Create a new test case",
                    "GET /api/test-cases/{id}": "Get test case by ID",
                    "PUT /api/test-cases/{id}": "Update test case",
                    "DELETE /api/test-cases/{id}": "Delete test case",
                    "GET /api/test-cases/feature?feature={name}": "Get test cases by feature"
                },
                "database": {
                    "GET /api/databases": "List all databases",
                    "GET /api/databases/{name}/info": "Get database information",
                    "POST /api/databases/{name}/sync": "Sync database",
                    "POST /api/databases/{name}/query": "Execute database query"
                }
            }
        })

def setup_security_headers(app: Flask) -> None:
    """Setup secure headers using Flask-Talisman"""
    # Force HTTPS only if not in development and not explicitly disabled.
    # app.debug is not yet True at middleware-setup time (Flask flips it inside
    # app.run(debug=True)), so prefer the SAKURA_IS_DEV flag stamped in main.py
    # and fall back to FLASK_ENV to avoid silently redirecting localhost to HTTPS.
    is_dev = bool(app.config.get('SAKURA_IS_DEV')) or os.environ.get('FLASK_ENV', 'development') == 'development' or app.debug
    force_https = os.environ.get('FORCE_HTTPS', str(not is_dev)).lower() == 'true'
    
    Talisman(
        app,
        force_https=force_https,
        content_security_policy=None,  # Adjust CSP based on frontend needs
        strict_transport_security=force_https
    )


def setup_rate_limiting(app: Flask) -> None:
    """Setup rate limiting using Flask-Limiter"""
    limiter.init_app(app)
