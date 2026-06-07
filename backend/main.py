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

# Network egress allow-list. Default is "strict" (loopback only). The audit
# (SAK-013) flagged that this used to default off — keeping it on closes the
# easiest exfiltration channel during development too. Production refuses to
# boot with restrictions fully off.
_RESTRICTOR_MODE = os.environ.get('ENABLE_NETWORK_RESTRICTIONS', 'strict').strip().lower()
# Back-compat: legacy boolean values still work.
if _RESTRICTOR_MODE in ('true', '1', 'yes', 'on'):
    _RESTRICTOR_MODE = 'strict'
elif _RESTRICTOR_MODE in ('false', '0', 'no'):
    _RESTRICTOR_MODE = 'off'

if _RESTRICTOR_MODE == 'off' and os.environ.get('ENVIRONMENT', '').lower() == 'production':
    raise RuntimeError(
        "ENABLE_NETWORK_RESTRICTIONS=off is not allowed when ENVIRONMENT=production. "
        "Use 'strict' (loopback-only) or 'allow_lan' (RFC-1918) instead."
    )

ENABLE_NETWORK_RESTRICTIONS = _RESTRICTOR_MODE in ('strict', 'allow_lan')
os.environ['SAKURA_RESTRICTOR_MODE'] = _RESTRICTOR_MODE

if ENABLE_NETWORK_RESTRICTIONS:
    try:
        from src.infrastructure.network_restrictor import enable_network_restrictions, verify_network_isolation
        enable_network_restrictions()
    except Exception as e:
        # Use stderr because the structured logger isn't configured yet at module load time.
        sys.stderr.write(f"[WARNING] Could not enable network restrictions: {e}\n")

from src.infrastructure.dependency_injection import (
    get_user_service, get_test_case_service, get_hybrid_database_service,
    get_requirement_service, get_design_ticket_service, get_spec_service, get_parsing_service,
    get_assistant_service, get_activity_log_service,
)
from src.controllers.user_controller import create_user_blueprint
from src.controllers.test_case_controller import create_test_case_blueprint
from src.controllers.auth_controller import create_auth_blueprint
from src.controllers.admin_controller import create_admin_blueprint
from src.controllers.requirement_controller import create_requirement_blueprint
from src.controllers.design_ticket_controller import create_design_ticket_blueprint
from src.controllers.spec_controller import create_spec_blueprint
from src.controllers.parsing_controller import create_parsing_blueprint
from src.controllers.assistant_controller import create_assistant_blueprint
from src.controllers.activity_controller import create_activity_blueprint
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
    # SAK-018/028 fix: production is now the default; dev mode must be opted into.
    is_dev = os.environ.get('FLASK_ENV', 'production') == 'development'
    app.config['SAKURA_IS_DEV'] = is_dev

    # Configure CORS. The pre-audit version allowed origins="*" together with
    # supports_credentials=True in dev, which Flask-CORS would happily emit —
    # browsers refuse it, but the misconfiguration also hides real CSRF posture
    # bugs. We now demand an explicit allow-list and refuse the wildcard +
    # credentials combination outright (SAK-015).
    allowed_origins_env = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:4200,http://localhost:5000')
    cors_origins = [o.strip() for o in allowed_origins_env.split(',') if o.strip()]
    if '*' in cors_origins:
        raise RuntimeError(
            "ALLOWED_ORIGINS must not contain '*' (refused at startup: SAK-015). "
            "List the exact frontend origin(s) instead."
        )
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
    parsing_service = get_parsing_service()
    assistant_service = get_assistant_service()
    activity_log_service = get_activity_log_service()
    
    # Create and register blueprints
    auth_bp = create_auth_blueprint(user_service)
    user_bp = create_user_blueprint(user_service)
    test_case_bp = create_test_case_blueprint(test_case_service)
    admin_bp = create_admin_blueprint()
    requirement_bp = create_requirement_blueprint(requirement_service)
    design_ticket_bp = create_design_ticket_blueprint(design_ticket_service)
    spec_bp = create_spec_blueprint(spec_service)
    parsing_bp = create_parsing_blueprint(parsing_service)
    assistant_bp = create_assistant_blueprint(assistant_service)
    activity_bp = create_activity_blueprint(activity_log_service)
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(test_case_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(requirement_bp)
    app.register_blueprint(design_ticket_bp)
    app.register_blueprint(spec_bp)
    app.register_blueprint(parsing_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(activity_bp)
    
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
    
    # SAK-003: the legacy /api/all/ endpoint dumped every table including
    # users.password_hash, secret_key_hash, and git_token_encrypted with no
    # authentication. Removed wholesale. The endpoint now returns 410 so old
    # clients learn the feature is gone and stop polling. Use the per-resource
    # APIs (with proper authz) instead.
    @app.route('/api/all/')
    @app.route('/api/all')
    def get_all_data():
        return jsonify({
            "success": False,
            "error": "Endpoint removed",
            "message": "GET /api/all was removed in the security hardening pass (SAK-003). Use the per-resource APIs.",
        }), 410

    
    # Remote/Git database sync was removed. The legacy endpoints below exist
    # only to give old clients a clean 410 response instead of a hard 404 so
    # they can detect the feature has been retired and stop polling.
    _REMOTE_RETIRED_PAYLOAD = {
        "success": False,
        "error": "Remote/Git database sync has been removed; the app runs in local-only mode.",
    }

    @app.route('/api/databases', methods=['GET'])
    @app.route('/api/databases/<database_name>/info', methods=['GET'])
    @app.route('/api/databases/<database_name>/sync', methods=['POST'])
    @app.route('/api/databases/<database_name>/query', methods=['POST'])
    @app.route('/api/git/status', methods=['GET'])
    @app.route('/api/git/pull', methods=['POST'])
    @app.route('/api/sync/force', methods=['POST'])
    def _retired_remote_endpoint(database_name: str | None = None):
        return jsonify(_REMOTE_RETIRED_PAYLOAD), 410

    @app.route('/api/sync/status', methods=['GET'])
    def get_sync_status():
        """Local-only sync status. Auth required (SAK-029)."""
        from flask import g
        if not getattr(g, 'current_user', None):
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        try:
            hybrid_service = get_hybrid_database_service()
            return jsonify(hybrid_service.get_sync_status())
        except Exception:
            logger.exception("sync status failed")
            return jsonify({"success": False, "error": "Internal error"}), 500

    @app.route('/api/users/<int:user_id>/preferences', methods=['GET'])
    def get_user_preferences(user_id):
        """Get user preferences (SAK-005: owner or admin only)."""
        from flask import g
        current = getattr(g, 'current_user', None)
        if not current:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        if current.get('id') != user_id and current.get('role') != 'admin':
            return jsonify({"success": False, "error": "Forbidden"}), 403
        try:
            from src.infrastructure.dependency_injection import get_local_database_service
            local_service = get_local_database_service()
            preferences = local_service.get_user_preferences(user_id)
            return jsonify({
                "success": True,
                "data": preferences
            })
        except Exception:
            logger.exception("get_user_preferences failed")
            return jsonify({
                "success": False,
                "error": "Internal error"
            }), 500

    @app.route('/api/users/<int:user_id>/preferences', methods=['POST'])
    def set_user_preference(user_id):
        """Set user preference (SAK-005: owner or admin only)."""
        from flask import g
        current = getattr(g, 'current_user', None)
        if not current:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        if current.get('id') != user_id and current.get('role') != 'admin':
            return jsonify({"success": False, "error": "Forbidden"}), 403
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
        except Exception:
            logger.exception("set_user_preference failed")
            return jsonify({
                "success": False,
                "error": "Internal error"
            }), 500

    logger.info("Legacy routes registered successfully")


def main():
    """Main entry point for the Sakura backend application."""

    # SAK-018/028 fix: production is the default; development must be opted-into.
    os.environ.setdefault('FLASK_ENV', 'production')
    os.environ.setdefault('ENVIRONMENT', 'production')

    # Create Flask application
    app = create_app()

    # Initialize hybrid database service
    try:
        hybrid_service = get_hybrid_database_service()
        if hybrid_service.initialize():
            logger.info("Hybrid database service initialized successfully")
        else:
            logger.error("Failed to initialize hybrid database service; continuing with limited functionality")
    except Exception:
        logger.exception("Error initializing hybrid database service; continuing with limited functionality")

    # Provision master admin account
    try:
        from src.infrastructure.master_admin_provision import provision_master_admin
        if provision_master_admin():
            logger.info("Master admin account provisioned")
        else:
            logger.warning("Failed to provision master admin account")
    except Exception:
        logger.exception("Error provisioning master admin account; continuing without it")

    # Start bundled Ollama VLM sidecar (best-effort; falls back silently if
    # the binary or pre-pulled qwen2.5vl:7b blobs aren't shipped in this build).
    if os.environ.get("SAKURA_DISABLE_OLLAMA_SIDECAR", "false").lower() != "true":
        try:
            from src.infrastructure.ollama_sidecar import ensure_ollama_running
            ensure_ollama_running()
        except Exception:
            logger.exception("Ollama sidecar not started")

    # Start the assistant's live vector indexer (RAG). Runs in a daemon
    # thread that polls database_metadata.version every N seconds and
    # incrementally re-embeds rows whose content hash changed. Disable by
    # setting assistant.rag.enabled: false in config.yaml.
    if os.environ.get("SAKURA_DISABLE_LIVE_INDEXER", "false").lower() != "true":
        try:
            from src.infrastructure.dependency_injection import get_live_indexer
            live = get_live_indexer()
            if live is not None:
                live.start()
                logger.info("Assistant live indexer started")
            else:
                logger.info("Assistant live indexer disabled (assistant.rag.enabled=false)")
        except Exception:
            logger.exception("Live indexer not started")

    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'

    # SAK-028 fix: the werkzeug dev server exposes a debug PIN console that is
    # RCE-on-LAN. Refuse to bind a debug server to anything except loopback.
    if debug and host not in ('127.0.0.1', '::1', 'localhost'):
        raise RuntimeError(
            f"Refusing to start: FLASK_ENV=development with HOST={host}. "
            "The werkzeug debug server must only bind to loopback. "
            "Either set FLASK_ENV=production or HOST=127.0.0.1."
        )

    logger.info("Starting Sakura backend server host=%s port=%s debug=%s", host, port, debug)

    # In production, hand off to run_server.py (Waitress/Gunicorn). The
    # werkzeug dev server is only used when explicitly running in dev mode.
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
