"""Admin-specific endpoints"""
from flask import Blueprint, request, jsonify
from typing import Dict, Any
from src.middleware.admin_middleware import is_admin, get_current_user_role, require_admin
from src.services.bulk_import_service import BulkImportService
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class AdminController:
    """Controller for admin-specific endpoints"""

    def __init__(self):
        self.bulk_import_service = BulkImportService()
    
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

    @require_admin
    def bulk_import(self) -> Dict[str, Any]:
        """Import entity records from one or more Excel workbooks."""
        try:
            files = request.files.getlist('files') or request.files.getlist('file')
            if not files:
                return jsonify({
                    "success": False,
                    "error": "No files uploaded",
                    "message": "Upload at least one Excel workbook"
                }), 400

            target = (request.form.get('target') or 'auto').strip()
            created_by = getattr(request, "current_username", None)
            try:
                from flask import g
                created_by = g.get('current_username') or created_by or 'system'
            except Exception:
                created_by = created_by or 'system'

            result = self.bulk_import_service.import_files(files, target, created_by)
            totals = result["totals"]
            return jsonify({
                "success": totals["failed"] == 0 or totals["created"] > 0 or totals["skipped"] > 0,
                "message": "Bulk import completed",
                "data": result
            }), 200
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid import request",
                "message": str(e)
            }), 400
        except Exception as e:
            logger.error(f"Bulk import failed: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Bulk import failed",
                "message": str(e)
            }), 500


def create_admin_blueprint() -> Blueprint:
    """Create and configure admin blueprint"""
    admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')
    controller = AdminController()
    
    # Register routes
    admin_bp.route('/status', methods=['GET'])(controller.check_admin_status)
    admin_bp.route('/bulk-import', methods=['POST'])(controller.bulk_import)
    
    return admin_bp










