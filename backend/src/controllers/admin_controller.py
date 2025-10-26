"""Admin-specific endpoints"""
from flask import Blueprint, request, jsonify
from typing import Dict, Any
from src.middleware.admin_middleware import is_admin, get_current_user_role


class AdminController:
    """Controller for admin-specific endpoints"""
    
    def check_admin_status(self) -> Dict[str, Any]:
        """Check if current user is admin"""
        try:
            is_user_admin = is_admin()
            role = get_current_user_role()
            
            return jsonify({
                "success": True,
                "data": {
                    "is_admin": is_user_admin,
                    "role": role or "user"
                }
            }), 200
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to check admin status",
                "message": str(e)
            }), 500


def create_admin_blueprint() -> Blueprint:
    """Create and configure admin blueprint"""
    admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')
    controller = AdminController()
    
    # Register routes
    admin_bp.route('/status', methods=['GET'])(controller.check_admin_status)
    
    return admin_bp

