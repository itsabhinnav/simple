"""Admin-specific endpoints"""
from flask import Blueprint, request, jsonify
from typing import Dict, Any
from src.middleware.admin_middleware import is_admin, get_current_user_role, require_admin
from src.services.bulk_import_service import (
    BulkImportService,
    TARGET_CONFIG,
    HEADER_ALIASES,
    get_effective_target_config,
)
from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


# Top-level config.yaml sections that the admin UI is allowed to read/write.
# Keep this allow-list narrow: secrets (JWT keys, DB passwords) live in env
# vars, and ``database`` paths must not be hot-swapped at runtime.
EDITABLE_CONFIG_SECTIONS = {
    "test_case_dropdowns",
    "features",
    "authentication",
    "server",
    "logging",
    "parsing",
    "bulk_import",
    "network",
}

# Sections we expose read-only for transparency (so the admin can audit
# what the backend is actually using) but refuse to mutate via the API.
READ_ONLY_SECTIONS = {
    "database",
    "environment",
}


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


    # ------------------------------------------------------------------
    # Settings / Configuration management (visual editor for config.yaml)
    # ------------------------------------------------------------------
    @require_admin
    def get_settings(self) -> Dict[str, Any]:
        """GET /api/admin/settings — return editable + read-only config sections.

        Shape::

            {
              "file_path": "<absolute path to config.yaml>",
              "editable_sections": [...],
              "read_only_sections": [...],
              "sections": {
                  "<section_name>": <current value (deep-copied)>,
                  ...
              }
            }
        """
        try:
            mgr = get_config_manager()
            sections: Dict[str, Any] = {}
            for name in EDITABLE_CONFIG_SECTIONS | READ_ONLY_SECTIONS:
                value = mgr.get_config(name, None)
                sections[name] = value if value is not None else {}
            return jsonify({
                "success": True,
                "data": {
                    "file_path": mgr.get_file_config_path(),
                    "editable_sections": sorted(EDITABLE_CONFIG_SECTIONS),
                    "read_only_sections": sorted(READ_ONLY_SECTIONS),
                    "sections": sections,
                },
            }), 200
        except Exception as e:
            logger.error(f"Failed to load admin settings: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to load settings",
                "message": str(e),
            }), 500

    @require_admin
    def update_section(self, section: str) -> Dict[str, Any]:
        """PUT /api/admin/settings/<section> — overwrite a single top-level
        section in ``config.yaml``. Body: ``{"value": <new section value>}``.
        """
        try:
            if section not in EDITABLE_CONFIG_SECTIONS:
                return jsonify({
                    "success": False,
                    "error": "Section not editable",
                    "message": f"'{section}' cannot be edited via the admin API",
                }), 400
            payload = request.get_json(silent=True) or {}
            if "value" not in payload:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Body must include a 'value' field",
                }), 400
            value = payload["value"]
            ok = get_config_manager().set_section(section, value)
            if not ok:
                return jsonify({
                    "success": False,
                    "error": "Save failed",
                    "message": "Could not persist changes to config.yaml",
                }), 500
            updated = get_config_manager().get_config(section, value)
            return jsonify({
                "success": True,
                "message": f"Section '{section}' updated",
                "data": {"section": section, "value": updated},
            }), 200
        except Exception as e:
            logger.error(f"Failed to update section {section}: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to update section",
                "message": str(e),
            }), 500

    @require_admin
    def get_import_schema(self) -> Dict[str, Any]:
        """GET /api/admin/import-schema — expose the bulk import contract
        (canonical fields per entity + alias dictionary) so the admin UI
        can render mapping configuration."""
        try:
            targets: Dict[str, Any] = {}
            for name, base in TARGET_CONFIG.items():
                effective = get_effective_target_config(name) or base
                targets[name] = {
                    "table": base.get("table"),
                    "id_field": base.get("id_field"),
                    "prefix": base.get("prefix"),
                    "required": effective.get("required", []),
                    "fields": effective.get("fields", []),
                    "default_required": base.get("required", []),
                    "default_fields": base.get("fields", []),
                }
            return jsonify({
                "success": True,
                "data": {
                    "targets": targets,
                    "header_aliases": HEADER_ALIASES,
                },
            }), 200
        except Exception as e:
            logger.error(f"Failed to load import schema: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to load import schema",
                "message": str(e),
            }), 500


def create_admin_blueprint() -> Blueprint:
    """Create and configure admin blueprint"""
    admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')
    controller = AdminController()
    
    # Register routes
    admin_bp.route('/status', methods=['GET'])(controller.check_admin_status)
    admin_bp.route('/bulk-import', methods=['POST'])(controller.bulk_import)
    admin_bp.route('/settings', methods=['GET'])(controller.get_settings)
    admin_bp.route('/settings/<section>', methods=['PUT'])(controller.update_section)
    admin_bp.route('/import-schema', methods=['GET'])(controller.get_import_schema)
    
    return admin_bp










