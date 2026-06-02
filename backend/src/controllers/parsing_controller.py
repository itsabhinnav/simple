"""Flask blueprint exposing the hybrid document parsing engine.

Routes:
    POST /api/parsing/parse                — async/sync parse via Celery + hybrid orchestrator.
    POST /api/parsing/smart-preview        — synchronous unified preview (deterministic + AI).
    GET  /api/parsing/tasks/<id>           — celery task status.
    GET  /api/parsing/tasks/<id>/result    — celery task result payload.
    GET  /api/parsing/providers            — list registered VLM providers.

The smart-preview endpoint is consumed by the frontend Smart Import wizard
to get artifact classification, header→field mapping suggestions, sample
rows and (optionally) VLM-driven semantic overlays in a single round-trip.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from src.infrastructure.logging_config import get_logger
from src.interfaces.llm_provider import get_vlm_registry
from src.schemas.parsing_schema import ParseOptionsSchema, SmartPreviewOptionsSchema
from src.services.bulk_import_service import (
    BulkImportService,
    SUPPORTED_SUFFIXES as BULK_IMPORT_SUFFIXES,
    TARGET_CONFIG,
)
from src.services.parsing.models import ParseOptions
from src.services.parsing_service import ParsingService

logger = get_logger(__name__)


_PARSE_EXTENSIONS = {".xlsx", ".xlsm", ".docx"}
_SMART_PREVIEW_EXTENSIONS = {".xlsx", ".xlsm", ".csv", ".docx"}
_TARGETS = ("specifications", "requirements", "design_tickets", "test_cases")


class ParsingController:
    """Controller for /api/parsing/* endpoints."""

    def __init__(self, parsing_service: ParsingService) -> None:
        self.parsing_service = parsing_service
        self.bulk_import_service = BulkImportService()

    # ------------------------------------------------------------------
    # /parse — hybrid pipeline (deterministic + visual + VLM + reconcile)
    # ------------------------------------------------------------------
    def parse(self) -> Any:
        upload = request.files.get("file")
        if upload is None:
            return jsonify({"success": False, "error": "Missing file", "message": "form field 'file' required"}), 400
        filename = upload.filename or ""
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in _PARSE_EXTENSIONS:
            return jsonify(
                {
                    "success": False,
                    "error": "Unsupported file type",
                    "message": f"expected one of {sorted(_PARSE_EXTENSIONS)}, got '{ext}'",
                }
            ), 400

        form_opts: Dict[str, Any] = {
            "provider": request.form.get("provider"),
            "mode": request.form.get("mode") or "async",
            "target": request.form.get("target"),
        }
        if request.form.get("enable_visual") is not None:
            form_opts["enable_visual"] = request.form.get("enable_visual", "true").lower() == "true"
        if request.form.get("enable_vlm") is not None:
            form_opts["enable_vlm"] = request.form.get("enable_vlm", "true").lower() == "true"

        try:
            opts_model = ParseOptionsSchema(**{k: v for k, v in form_opts.items() if v is not None})
        except ValueError as exc:
            return jsonify({"success": False, "error": "Validation error", "message": str(exc)}), 400

        options_dict = opts_model.model_dump(exclude_none=True)
        options_dict.pop("mode", None)
        target_hint = options_dict.pop("target", None)

        try:
            if opts_model.mode == "sync":
                result = self.parsing_service.parse_sync_upload(upload, options_dict)
                payload = result.model_dump()
                if target_hint:
                    payload["target_hint"] = target_hint
                return jsonify({"success": True, "data": payload}), 200

            submission = self.parsing_service.submit_parse(upload, options_dict)
            if target_hint:
                submission["target_hint"] = target_hint
            return jsonify({"success": True, "data": submission}), 202
        except RuntimeError as exc:
            logger.warning(f"parse submission fell back: {exc}")
            return jsonify({"success": False, "error": "celery_unavailable", "message": str(exc)}), 503
        except Exception as exc:  # noqa: BLE001 - bubble as 500 with message
            logger.error(f"parse failed: {exc}", exc_info=True)
            return jsonify({"success": False, "error": "parse_failed", "message": str(exc)}), 500

    def get_task_status(self, task_id: str) -> Any:
        try:
            status = self.parsing_service.get_status(task_id)
            return jsonify({"success": True, "data": status.model_dump()}), 200
        except Exception as exc:  # noqa: BLE001
            logger.error(f"status fetch failed: {exc}")
            return jsonify({"success": False, "error": "status_failed", "message": str(exc)}), 500

    def get_task_result(self, task_id: str) -> Any:
        try:
            payload = self.parsing_service.get_result(task_id)
            if payload is None:
                return jsonify({"success": True, "data": None, "message": "Result not ready"}), 202
            return jsonify({"success": True, "data": payload}), 200
        except Exception as exc:  # noqa: BLE001
            logger.error(f"result fetch failed: {exc}")
            return jsonify({"success": False, "error": "result_failed", "message": str(exc)}), 500

    def list_providers(self) -> Any:
        registry = get_vlm_registry()
        return jsonify(
            {
                "success": True,
                "data": {
                    "default": registry.get_default_name(),
                    "providers": registry.list_providers(),
                },
            }
        ), 200

    # ------------------------------------------------------------------
    # /smart-preview — synchronous unified preview combining the
    # deterministic bulk-import header detection AND optionally the
    # robust hybrid parser (artifact classification, semantic overlays).
    #
    # The frontend Smart Import wizard issues a single call here before
    # the column-mapping step. The deterministic path stays authoritative
    # for the eventual DB write (handled by /api/<resource>/import) — this
    # endpoint is purely advisory.
    # ------------------------------------------------------------------
    def smart_preview(self) -> Any:
        upload = request.files.get("file") or (request.files.getlist("files") or [None])[0]
        if upload is None:
            return jsonify({
                "success": False,
                "error": "Missing file",
                "message": "form field 'file' (or 'files') required",
            }), 400
        filename = upload.filename or ""
        suffix = Path(filename).suffix.lower()
        if suffix not in _SMART_PREVIEW_EXTENSIONS:
            return jsonify({
                "success": False,
                "error": "Unsupported file type",
                "message": f"expected one of {sorted(_SMART_PREVIEW_EXTENSIONS)}, got '{suffix}'",
            }), 400

        try:
            opts = SmartPreviewOptionsSchema(
                target=request.form.get("target"),
                provider=request.form.get("provider"),
                sample_rows=int(request.form.get("sample_rows") or 5),
                enable_ai=(request.form.get("enable_ai") or "false").lower() == "true",
                enable_visual=(request.form.get("enable_visual") or "false").lower() == "true",
                enable_vlm=(request.form.get("enable_vlm") or "false").lower() == "true",
            )
        except ValueError as exc:
            return jsonify({"success": False, "error": "Validation error", "message": str(exc)}), 400

        deterministic_payload: Dict[str, Any] = {}
        # Phase 1 — deterministic bulk-import header preview. Reuses the
        # exact same header normalization the backend uses for the actual
        # /import call, so the suggested mapping is always faithful.
        try:
            target = opts.target or "auto"
            if suffix in BULK_IMPORT_SUFFIXES:
                # Cheap path: existing tabular preview.
                upload.stream.seek(0)
                deterministic_payload = self.bulk_import_service.preview_file(
                    upload, target, sample_rows=opts.sample_rows
                )
            else:
                deterministic_payload = {"file": filename, "sheets": []}
        except ValueError as exc:
            return jsonify({"success": False, "error": "Invalid request", "message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001 — degrade gracefully
            logger.warning(f"smart_preview deterministic stage failed: {exc}")
            deterministic_payload = {"file": filename, "sheets": [], "error": str(exc)}

        # Phase 2 — optional hybrid AI-driven enrichment. xlsx/docx only;
        # xlsm rides the openpyxl path inside HybridDocumentParser, csv
        # is handled by the deterministic preview already.
        ai_payload: Dict[str, Any] = {"requested": opts.enable_ai, "skipped": True}
        if opts.enable_ai and suffix in _PARSE_EXTENSIONS:
            try:
                upload.stream.seek(0)
            except Exception:
                pass
            try:
                hybrid_options: Dict[str, Any] = {
                    "enable_visual": opts.enable_visual,
                    "enable_vlm": opts.enable_vlm,
                }
                if opts.provider:
                    hybrid_options["provider"] = opts.provider
                hybrid_result = self.parsing_service.parse_sync_upload(upload, hybrid_options)
                ai_payload = {
                    "requested": True,
                    "skipped": False,
                    "artifact_kind": hybrid_result.artifact_kind,
                    "file_type": hybrid_result.file_type,
                    "warnings": hybrid_result.warnings,
                    "deterministic_summary": hybrid_result.deterministic,
                    "vlm": hybrid_result.vlm,
                    "conflicts": [c.model_dump() for c in hybrid_result.conflicts],
                    "structured_payload": hybrid_result.structured_payload,
                }
            except Exception as exc:  # noqa: BLE001 — AI is best-effort
                logger.warning(f"smart_preview AI stage failed: {exc}")
                ai_payload = {
                    "requested": True,
                    "skipped": True,
                    "error": str(exc),
                }

        # Provider catalog — the frontend wizard renders this as a
        # dropdown so users can pick local Ollama vs. cloud providers.
        registry = get_vlm_registry()
        providers = {
            "default": registry.get_default_name(),
            "providers": registry.list_providers(),
        }

        return jsonify({
            "success": True,
            "data": {
                "file": filename,
                "target": opts.target,
                "deterministic": deterministic_payload,
                "ai": ai_payload,
                "providers": providers,
                "supported_targets": list(_TARGETS),
            },
        }), 200

    def list_targets(self) -> Any:
        """Expose the canonical fields for every importable target."""
        catalog: Dict[str, Any] = {}
        for target in _TARGETS:
            cfg = TARGET_CONFIG.get(target)
            if not cfg:
                continue
            catalog[target] = {
                "id_field": cfg["id_field"],
                "required": cfg["required"],
                "fields": cfg["fields"],
            }
        return jsonify({"success": True, "data": {"targets": catalog}}), 200


def create_parsing_blueprint(parsing_service: ParsingService) -> Blueprint:
    """Create and configure the parsing blueprint."""
    parsing_bp = Blueprint("parsing", __name__, url_prefix="/api/parsing")
    controller = ParsingController(parsing_service)

    parsing_bp.route("/parse", methods=["POST"])(controller.parse)
    parsing_bp.route("/smart-preview", methods=["POST"])(controller.smart_preview)
    parsing_bp.route("/tasks/<task_id>", methods=["GET"])(controller.get_task_status)
    parsing_bp.route("/tasks/<task_id>/result", methods=["GET"])(controller.get_task_result)
    parsing_bp.route("/providers", methods=["GET"])(controller.list_providers)
    parsing_bp.route("/targets", methods=["GET"])(controller.list_targets)

    return parsing_bp
