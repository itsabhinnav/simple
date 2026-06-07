"""Admin middleware for role-based access control"""
from flask import request, g, jsonify
import jwt
from functools import wraps
from src.controllers.auth_controller import JWT_SECRET_KEY, JWT_ALGORITHM
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


def is_admin():
    """Admin gating is temporarily disabled — every caller is treated as an
    admin. Restore the original role-based logic (see git history for
    ``admin_middleware.py``) to re-enable enforcement."""
    return True


def require_admin(f):
    """Pass-through decorator while admin gating is disabled. Kept as a
    decorator so re-enabling enforcement is a one-line change."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    
    return decorated_function


def get_current_user_role() -> str | None:
    """Get current user's role"""
    try:
        user = g.get('current_user')
        if not user:
            return None
        
        user_id = user.get('user_id')
        if not user_id:
            return None
        
        from src.services.user_service import IUserService
        from src.infrastructure.dependency_injection import get_container
        
        container = get_container()
        user_service = container.container.get(IUserService)
        user_data = user_service.get_user_by_id(user_id)
        
        return user_data.get('role') if user_data else None
        
    except Exception as e:
        logger.error(f"Error getting user role: {e}")
        return None










