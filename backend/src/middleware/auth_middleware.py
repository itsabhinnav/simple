"""Authentication middleware for extracting user info from JWT"""
import os
from flask import request, g, jsonify
import jwt
from functools import wraps
from typing import Optional, Tuple
from src.controllers.auth_controller import JWT_SECRET_KEY, JWT_ALGORITHM
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)

# Routes reachable without a valid JWT (fail-closed everywhere else under /api/).
_PUBLIC_AUTH_PATHS = frozenset(
    {
        "/api/auth/login",
        "/api/auth/signup",
        "/api/auth/reset-password",
        "/api/auth/verify-secret",
    }
)


def get_current_user():
    """Extract current user from JWT token in request"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return {
            'user_id': decoded.get('user_id'),
            'username': decoded.get('username')
        }
    except Exception as e:
        logger.debug(f"Could not extract user from token: {e}")
        return None


def get_current_username() -> str | None:
    """Get current username from request"""
    user = get_current_user()
    return user.get('username') if user else None


def before_request():
    """Add user info to Flask's g object before request"""
    user = get_current_user()
    g.current_user = user
    g.current_username = user.get('username') if user else None


def is_auth_enforced() -> bool:
    """Return True when API routes require a valid JWT (default: always)."""
    explicit = os.environ.get("SAKURA_REQUIRE_AUTH")
    if explicit is not None:
        return explicit.lower() not in ("false", "0", "no", "off")
    return True


def _is_public_api_path(path: str) -> bool:
    if path in _PUBLIC_AUTH_PATHS:
        return True
    if path == "/api/auth/verify":
        return True
    return False


def enforce_authentication() -> Optional[Tuple]:
    """Global gate for /api/* — returns a Flask response tuple when blocked."""
    if not is_auth_enforced():
        return None
    if request.method == "OPTIONS":
        return None
    path = request.path.rstrip("/") or "/"
    if not path.startswith("/api/"):
        return None
    if _is_public_api_path(path):
        return None
    if get_current_user():
        return None
    logger.warning("Blocked unauthenticated API request: %s %s", request.method, path)
    return (
        jsonify(
            {
                "success": False,
                "error": "Unauthorized",
                "message": "Authentication required",
            }
        ),
        401,
    )


def require_auth(f):
    """Decorator for routes that must always require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not get_current_user():
            return jsonify(
                {
                    "success": False,
                    "error": "Unauthorized",
                    "message": "Authentication required",
                }
            ), 401
        return f(*args, **kwargs)

    return decorated_function










