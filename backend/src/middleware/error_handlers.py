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

    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response
    
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


# SAK-006: never log these headers or these body field names — they carry
# credentials or PII. The pre-audit logger dumped every header (including the
# Authorization Bearer JWT) and the parsed JSON body (including login and
# signup passwords) at INFO. We now log a small, deterministic surface only.
_REDACTED = "<redacted>"
_SENSITIVE_HEADERS = frozenset({
    "authorization",
    "cookie",
    "set-cookie",
    "proxy-authorization",
    "x-api-key",
    "x-auth-token",
})
_NO_BODY_LOG_PATHS = (
    "/api/auth/login",
    "/api/auth/signup",
    "/api/auth/reset-password",
    "/api/auth/verify-secret",
    "/api/auth/verify",
    "/api/admin/llm",
)
_SENSITIVE_FIELDS = frozenset({
    "password",
    "new_password",
    "old_password",
    "secret_key",
    "git_token",
    "token",
    "authorization",
    "api_key",
    "apikey",
})


def _safe_headers(headers) -> dict:
    return {
        k: (_REDACTED if k.lower() in _SENSITIVE_HEADERS else v)
        for k, v in headers.items()
    }


def setup_request_logging(app: Flask) -> None:
    """Setup request logging middleware (SAK-006: sensitive-redacted)."""

    @app.before_request
    def log_request_info():
        # Path + method are safe. URL may carry query strings; we still log it
        # but operators should avoid putting secrets in query strings.
        app.logger.info("Request: %s %s", request.method, request.path)
        # Only log a short, allow-listed header summary — never the full set.
        ua = request.headers.get("User-Agent", "")
        ct = request.headers.get("Content-Type", "")
        app.logger.debug("UA=%s CT=%s", ua[:120], ct[:80])

    @app.after_request
    def log_response_info(response):
        app.logger.info("Response: %s %s -> %s", request.method, request.path, response.status_code)
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
        if request.method == 'OPTIONS':
            return
        
        content_type = request.content_type or ''
        is_multipart = content_type.startswith('multipart/form-data')
        if request.method in ['POST', 'PUT'] and 'application/json' in content_type and not is_multipart:
            if request.data and request.data.strip():
                try:
                    request.get_json(force=True)
                except Exception:
                    return jsonify({
                        "success": False,
                        "error": "Invalid JSON",
                        "message": "Request body must be valid JSON"
                    }), 400

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
            "title": "Sakura API",
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
    """Setup secure headers using Flask-Talisman.

    SAK-018/019 fix:
      * Force HTTPS by default in production (env-overridable).
      * Ship a strict Content-Security-Policy. The Angular SPA is served
        from the same origin and does not load anything cross-origin
        (no Google Fonts, no CDN, no Sentry/etc), so 'self' is sufficient.
      * Add Referrer-Policy and Permissions-Policy. COOP/CORP for isolation.
    """
    is_dev = bool(app.config.get('SAKURA_IS_DEV')) or os.environ.get('FLASK_ENV', 'production') == 'development' or app.debug
    force_https = os.environ.get('FORCE_HTTPS', str(not is_dev)).lower() == 'true'

    csp = {
        'default-src': "'self'",
        'script-src': "'self'",
        # Angular injects style attributes at runtime — 'unsafe-inline' is
        # unavoidable for style-src without nonces, but we still block scripts
        # and other vectors.
        'style-src': ["'self'", "'unsafe-inline'"],
        'img-src': ["'self'", "data:"],
        'font-src': ["'self'", "data:"],
        'connect-src': "'self'",
        'frame-ancestors': "'none'",
        'base-uri': "'self'",
        'form-action': "'self'",
        'object-src': "'none'",
    }

    Talisman(
        app,
        force_https=force_https,
        content_security_policy=csp,
        content_security_policy_nonce_in=[],
        strict_transport_security=force_https,
        strict_transport_security_max_age=63072000,
        strict_transport_security_include_subdomains=True,
        referrer_policy='no-referrer',
        frame_options='DENY',
        session_cookie_secure=force_https,
        session_cookie_http_only=True,
        feature_policy={
            'geolocation': "'none'",
            'microphone': "'none'",
            'camera': "'none'",
            'payment': "'none'",
            'usb': "'none'",
        },
    )


def setup_rate_limiting(app: Flask) -> None:
    """Setup rate limiting using Flask-Limiter"""
    limiter.init_app(app)
