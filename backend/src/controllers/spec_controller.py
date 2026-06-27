import json
import os
import re
import uuid
from flask import Blueprint, request, jsonify, send_file
from typing import Dict, Any, Optional
from werkzeug.utils import secure_filename
from src.services.spec_service import ISpecService
from src.schemas.spec_schema import SpecCreateSchema, SpecUpdateSchema
from src.infrastructure.logging_config import get_logger
from src.controllers._bulk_import_routes import attach_bulk_import_routes

logger = get_logger(__name__)

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../uploads/specs"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

_ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".md", ".zip", ".7z",
}


class SpecController:
    def __init__(self, spec_service: ISpecService):
        self.spec_service = spec_service

    def get_all_specs(self) -> Dict[str, Any]:
        try:
            search = request.args.get("search")
            project = request.args.get("project")
            specs = self.spec_service.get_all_specs(search=search, project=project)
            return jsonify({"success": True, "message": "Specifications retrieved", "data": specs, "count": len(specs)}), 200
        except Exception as e:
            logger.error(f"Failed to get specs: {e}")
            return jsonify({"success": False, "error": "Failed to get specifications", "message": str(e)}), 500

    def get_projects(self) -> Dict[str, Any]:
        try:
            projects = self.spec_service.get_projects()
            return jsonify({"success": True, "message": "Projects retrieved", "data": projects, "count": len(projects)}), 200
        except Exception as e:
            logger.error(f"Failed to get spec projects: {e}")
            return jsonify({"success": False, "error": "Failed to get projects", "message": str(e)}), 500

    def get_spec_by_id(self, spec_id: int) -> Dict[str, Any]:
        try:
            spec = self.spec_service.get_spec_by_id(spec_id)
            if spec:
                return jsonify({"success": True, "message": "Specification retrieved", "data": spec}), 200
            return jsonify({"success": False, "error": "Not found"}), 404
        except Exception as e:
            return jsonify({"success": False, "error": "Failed to get specification", "message": str(e)}), 500

    def get_spec_versions(self) -> Dict[str, Any]:
        try:
            spec_id = (request.args.get("spec_id") or "").strip()
            project = request.args.get("project")
            if not spec_id:
                return jsonify({"success": False, "error": "spec_id is required"}), 400
            versions = self.spec_service.get_spec_versions(spec_id, project=project)
            return jsonify({"success": True, "message": "Spec versions retrieved", "data": versions, "count": len(versions)}), 200
        except Exception as e:
            logger.error(f"Failed to get spec versions: {e}")
            return jsonify({"success": False, "error": "Failed to get spec versions", "message": str(e)}), 500

    def create_spec(self) -> Dict[str, Any]:
        try:
            payload, uploaded_file = self._parse_create_payload()
            data = SpecCreateSchema(**payload)

            if uploaded_file:
                file_name, file_path = self._save_spec_file(data.spec_id, uploaded_file)
                data.file_name = file_name
                data.file_url = file_path
            elif data.source_url and not data.file_url:
                fetched = self._try_fetch_external_file(data.spec_id, data.source_url)
                if fetched:
                    data.file_name, data.file_url = fetched

            spec = self.spec_service.create_spec(data)
            if spec.get("_error") == "duplicate_version":
                return jsonify({
                    "success": False,
                    "error": "duplicate_version",
                    "message": spec.get("_message", "This spec version already exists."),
                }), 409
            if not spec.get("id"):
                return jsonify({"success": False, "error": "Failed to add specification", "message": "Insert did not persist"}), 500
            return jsonify({"success": True, "message": "Specification added", "data": spec}), 201
        except Exception as e:
            logger.error(f"Failed to create spec: {e}")
            return jsonify({"success": False, "error": "Failed to add specification", "message": str(e)}), 500

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

    def download_spec_file(self, spec_id: int) -> Any:
        try:
            spec = self.spec_service.get_spec_by_id(spec_id)
            if not spec or not spec.get("file_url"):
                return jsonify({"success": False, "error": "No file available for this specification"}), 404
            abs_path = os.path.join(UPLOAD_DIR, spec["file_url"])
            if not os.path.isfile(abs_path):
                return jsonify({"success": False, "error": "File not found on disk"}), 404
            download_name = spec.get("file_name") or os.path.basename(abs_path)
            return send_file(abs_path, as_attachment=True, download_name=download_name)
        except Exception as e:
            logger.error(f"Download spec file failed: {e}")
            return jsonify({"success": False, "error": "Failed to download file", "message": str(e)}), 500

    def import_specs(self) -> Dict[str, Any]:
        try:
            if "file" not in request.files:
                return jsonify({"success": False, "error": "No file uploaded"}), 400
            file = request.files["file"]
            filename = secure_filename(file.filename)
            if not filename:
                return jsonify({"success": False, "error": "Invalid filename"}), 400
            save_path = os.path.join(UPLOAD_DIR, filename)
            file.save(save_path)
            return jsonify({"success": True, "message": "File uploaded", "data": {"file_url": filename}}), 200
        except Exception as e:
            logger.error(f"Import specs failed: {e}")
            return jsonify({"success": False, "error": "Failed to import specifications", "message": str(e)}), 500

    def _parse_create_payload(self):
        uploaded_file = None
        if request.content_type and "multipart/form-data" in request.content_type:
            raw = request.form.get("data") or "{}"
            payload = json.loads(raw)
            uploaded_file = request.files.get("file")
            if not payload.get("source_url") and request.form.get("source_url"):
                payload["source_url"] = request.form.get("source_url")
        else:
            payload = request.get_json() or {}
        return payload, uploaded_file

    def _save_spec_file(self, spec_id: str, file_storage) -> tuple[str, str]:
        original = secure_filename(file_storage.filename or "spec.bin")
        if not original:
            raise ValueError("Invalid filename")
        ext = os.path.splitext(original)[1].lower()
        if ext and ext not in _ALLOWED_EXTENSIONS:
            raise ValueError(f"File type {ext} is not supported")
        safe_spec = re.sub(r"[^\w\-]", "_", spec_id or "spec")
        spec_dir = os.path.join(UPLOAD_DIR, safe_spec)
        os.makedirs(spec_dir, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex[:8]}_{original}"
        abs_path = os.path.join(spec_dir, stored_name)
        file_storage.save(abs_path)
        rel_path = os.path.join(safe_spec, stored_name).replace("\\", "/")
        return original, rel_path

    def _try_fetch_external_file(self, spec_id: str, source_url: str) -> Optional[tuple[str, str]]:
        """Best-effort fetch for direct file links (SharePoint may require auth)."""
        try:
            from urllib.request import urlopen, Request

            req = Request(source_url, headers={"User-Agent": "Sakura/1.0"})
            with urlopen(req, timeout=30) as resp:
                content = resp.read()
                if not content:
                    return None
                guessed = os.path.basename(source_url.split("?")[0]) or "spec.bin"
                filename = secure_filename(guessed) or "spec.bin"
                safe_spec = re.sub(r"[^\w\-]", "_", spec_id or "spec")
                spec_dir = os.path.join(UPLOAD_DIR, safe_spec)
                os.makedirs(spec_dir, exist_ok=True)
                stored_name = f"{uuid.uuid4().hex[:8]}_{filename}"
                abs_path = os.path.join(spec_dir, stored_name)
                with open(abs_path, "wb") as fh:
                    fh.write(content)
                rel_path = os.path.join(safe_spec, stored_name).replace("\\", "/")
                return filename, rel_path
        except Exception as exc:
            logger.info(f"Could not fetch spec from {source_url}: {exc}")
            return None


def create_spec_blueprint(spec_service: ISpecService) -> Blueprint:
    bp = Blueprint("specifications", __name__, url_prefix="/api/specs")
    controller = SpecController(spec_service)
    bp.route("/", methods=["GET"])(controller.get_all_specs)
    bp.route("/projects", methods=["GET"])(controller.get_projects)
    bp.route("/versions", methods=["GET"])(controller.get_spec_versions)
    bp.route("/", methods=["POST"])(controller.create_spec)
    attach_bulk_import_routes(bp, "specifications")
    bp.route("/<int:spec_id>/file", methods=["GET"])(controller.download_spec_file)
    bp.route("/<int:spec_id>", methods=["GET"])(controller.get_spec_by_id)
    bp.route("/<int:spec_id>", methods=["PUT"])(controller.update_spec)
    bp.route("/<int:spec_id>", methods=["DELETE"])(controller.delete_spec)
    bp.route("/import/legacy", methods=["POST"])(controller.import_specs)
    return bp
