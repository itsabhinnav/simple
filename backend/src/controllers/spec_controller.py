from flask import Blueprint, request, jsonify
from typing import Dict, Any
from werkzeug.utils import secure_filename
import os
from src.services.spec_service import ISpecService
from src.schemas.spec_schema import SpecCreateSchema, SpecUpdateSchema
from src.infrastructure.logging_config import get_logger
from src.controllers._bulk_import_routes import attach_bulk_import_routes

logger = get_logger(__name__)


UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../uploads/specs'))
os.makedirs(UPLOAD_DIR, exist_ok=True)


class SpecController:
    def __init__(self, spec_service: ISpecService):
        self.spec_service = spec_service

    def get_all_specs(self) -> Dict[str, Any]:
        try:
            specs = self.spec_service.get_all_specs()
            return jsonify({"success": True, "message": "Specifications retrieved", "data": specs, "count": len(specs)}), 200
        except Exception as e:
            logger.error(f"Failed to get specs: {e}")
            return jsonify({"success": False, "error": "Failed to get specifications", "message": str(e)}), 500

    def get_spec_by_id(self, spec_id: int) -> Dict[str, Any]:
        try:
            spec = self.spec_service.get_spec_by_id(spec_id)
            if spec:
                return jsonify({"success": True, "message": "Specification retrieved", "data": spec}), 200
            return jsonify({"success": False, "error": "Not found"}), 404
        except Exception as e:
            return jsonify({"success": False, "error": "Failed to get specification", "message": str(e)}), 500

    def create_spec(self) -> Dict[str, Any]:
        try:
            payload = request.get_json() or {}
            data = SpecCreateSchema(**payload)
            spec = self.spec_service.create_spec(data)
            return jsonify({"success": True, "message": "Specification created", "data": spec}), 201
        except Exception as e:
            return jsonify({"success": False, "error": "Failed to create specification", "message": str(e)}), 500

    def update_spec(self, spec_id: int) -> Dict[str, Any]:
        try:
            payload = request.get_json() or {}
            data = SpecUpdateSchema(**payload)
            spec = self.spec_service.update_spec(spec_id, data)
            if spec:
                return jsonify({"success": True, "message": "Specification updated", "data": spec}), 200
            return jsonify({"success": False, "error": "Not found"}), 404
        except Exception as e:
            return jsonify({"success": False, "error": "Failed to update specification", "message": str(e)}), 500

    def delete_spec(self, spec_id: int) -> Dict[str, Any]:
        try:
            ok = self.spec_service.delete_spec(spec_id)
            return jsonify({"success": ok, "message": "Specification deleted" if ok else "Delete failed"}), 200 if ok else 500
        except Exception as e:
            return jsonify({"success": False, "error": "Failed to delete specification", "message": str(e)}), 500

    def import_specs(self) -> Dict[str, Any]:
        try:
            if 'file' not in request.files:
                return jsonify({"success": False, "error": "No file uploaded"}), 400
            file = request.files['file']
            filename = secure_filename(file.filename)
            if not filename:
                return jsonify({"success": False, "error": "Invalid filename"}), 400
            save_path = os.path.join(UPLOAD_DIR, filename)
            file.save(save_path)
            # Minimal parsing stub — real parsing can be added later
            # For now, just return the stored path
            return jsonify({"success": True, "message": "File uploaded", "data": {"file_url": f"/uploads/specs/{filename}"}}), 200
        except Exception as e:
            logger.error(f"Import specs failed: {e}")
            return jsonify({"success": False, "error": "Failed to import specifications", "message": str(e)}), 500


def create_spec_blueprint(spec_service: ISpecService) -> Blueprint:
    bp = Blueprint('specifications', __name__, url_prefix='/api/specs')
    controller = SpecController(spec_service)
    bp.route('/', methods=['GET'])(controller.get_all_specs)
    bp.route('/', methods=['POST'])(controller.create_spec)
    # New deterministic bulk-import endpoints (`/import`, `/import/preview`,
    # `/import/fields`) — wired before the `/<int:spec_id>` catch-alls so
    # Flask never tries to parse "import" as an integer ID. The legacy
    # `/import` file-upload route below is replaced by these and exposes
    # the same shape the test_cases controller already uses.
    attach_bulk_import_routes(bp, "specifications")
    bp.route('/<int:spec_id>', methods=['GET'])(controller.get_spec_by_id)
    bp.route('/<int:spec_id>', methods=['PUT'])(controller.update_spec)
    bp.route('/<int:spec_id>', methods=['DELETE'])(controller.delete_spec)
    # Legacy single-file upload kept for backward compatibility. Not
    # invoked by the new Smart Import wizard.
    bp.route('/import/legacy', methods=['POST'])(controller.import_specs)
    return bp








