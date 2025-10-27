"""Authentication middleware for extracting user info from JWT"""
from flask import request, g
import jwt
from functools import wraps
from src.controllers.auth_controller import JWT_SECRET_KEY, JWT_ALGORITHM
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


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


