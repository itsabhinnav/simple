from flask import Blueprint, request, jsonify
from typing import Dict, Any
from src.services.user_service import IUserService
from src.schemas.user_schema import UserCreateSchema, UserUpdateSchema
from src.schemas.api_schema import ErrorResponseSchema, SuccessResponseSchema
from src.middleware.admin_middleware import require_admin, is_admin


class UserController:
    """Controller for user-related API endpoints"""
    
    def __init__(self, user_service: IUserService):
        self.user_service = user_service
    
    @require_admin
    def get_all_users(self) -> Dict[str, Any]:
        """GET /api/users - Get all users (Admin only)"""
        try:
            users = self.user_service.get_all_users()
            return jsonify({
                "success": True,
                "message": "Users retrieved successfully",
                "data": users,
                "count": len(users)
            }), 200
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to retrieve users",
                "message": str(e)
            }), 500
    
    def get_user_by_id(self, user_id: int) -> Dict[str, Any]:
        """GET /api/users/<user_id> - Get user by ID"""
        try:
            user = self.user_service.get_user_by_id(user_id)
            if user:
                return jsonify({
                    "success": True,
                    "message": "User retrieved successfully",
                    "data": user
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "User not found",
                    "message": f"User with ID {user_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to retrieve user",
                "message": str(e)
            }), 500
    
    @require_admin
    def create_user(self) -> Dict[str, Any]:
        """POST /api/users - Create a new user (Admin only)"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            # Validate data using schema
            user_data = UserCreateSchema(**data)
            user = self.user_service.create_user(user_data)
            
            return jsonify({
                "success": True,
                "message": "User created successfully",
                "data": user
            }), 201
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Validation error",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to create user",
                "message": str(e)
            }), 500
    
    @require_admin
    def update_user(self, user_id: int) -> Dict[str, Any]:
        """PUT /api/users/<user_id> - Update user (Admin only)"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            # Validate data using schema
            user_data = UserUpdateSchema(**data)
            user = self.user_service.update_user(user_id, user_data)
            
            if user:
                return jsonify({
                    "success": True,
                    "message": "User updated successfully",
                    "data": user
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "User not found",
                    "message": f"User with ID {user_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Validation error",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to update user",
                "message": str(e)
            }), 500
    
    @require_admin
    def delete_user(self, user_id: int) -> Dict[str, Any]:
        """DELETE /api/users/<user_id> - Delete user (Admin only)"""
        try:
            success = self.user_service.delete_user(user_id)
            if success:
                return jsonify({
                    "success": True,
                    "message": "User deleted successfully"
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "User not found",
                    "message": f"User with ID {user_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to delete user",
                "message": str(e)
            }), 500


def create_user_blueprint(user_service: IUserService) -> Blueprint:
    """Create and configure user blueprint"""
    user_bp = Blueprint('users', __name__, url_prefix='/api/users')
    controller = UserController(user_service)
    
    # Register routes
    user_bp.route('/', methods=['GET'])(controller.get_all_users)
    user_bp.route('/', methods=['POST'])(controller.create_user)
    user_bp.route('/<int:user_id>', methods=['GET'])(controller.get_user_by_id)
    user_bp.route('/<int:user_id>', methods=['PUT'])(controller.update_user)
    user_bp.route('/<int:user_id>', methods=['DELETE'])(controller.delete_user)
    
    return user_bp
