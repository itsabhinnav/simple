"""Shared bulk-import HTTP handlers for spec/requirement/design/test-case controllers.

Mounting these routes on every entity blueprint keeps the deterministic
import pipeline (handled by `BulkImportService`) reachable for all four
import targets, while the new robust parsing engine at
``/api/parsing/smart-preview`` complements them with AI-driven
classification and semantic overlays.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from src.infrastructure.logging_config import get_logger
from src.services.bulk_import_service import BulkImportService

logger = get_logger(__name__)


_TARGETS = {"specifications", "requirements", "design_tickets", "test_cases"}


def _service() -> BulkImportService:
    return BulkImportService()


def _get_import_fields(target: str) -> Any:
    try:
        data = _service().get_target_fields(target)
        return jsonify({"success": True, "data": data}), 200
    except Exception as e:  # noqa: BLE001
        logger.error(f"[{target}] get_import_fields failed: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Failed to get import fields",
            "message": str(e),
        }), 500


def _preview_import(target: str) -> Any:
    try:
        file_storage = request.files.get("file") or (request.files.getlist("files") or [None])[0]
        if not file_storage:
            return jsonify({
                "success": False,
                "error": "No file uploaded",
                "message": "Upload an Excel/CSV workbook (.xlsx, .xlsm, .csv)",
            }), 400
        sample_rows = int(request.form.get("sample_rows", 5))
        data = _service().preview_file(file_storage, target, sample_rows=sample_rows)
        return jsonify({"success": True, "data": data}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": "Invalid request", "message": str(e)}), 400
    except Exception as e:  # noqa: BLE001
        logger.error(f"[{target}] preview_import failed: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Preview failed",
            "message": str(e),
        }), 500


def _bulk_import(target: str) -> Any:
    try:
        files = request.files.getlist("files") or request.files.getlist("file")
        if not files:
            return jsonify({
                "success": False,
                "error": "No files uploaded",
                "message": "Upload at least one Excel/CSV workbook",
            }), 400

        created_by = "system"
        try:
            from flask import g
            created_by = g.get("current_username") or created_by
        except Exception:
            pass

        mapping_raw = request.form.get("mapping")
        mapping: Dict[str, str] = {}
        if mapping_raw:
            try:
                parsed = json.loads(mapping_raw)
                if isinstance(parsed, dict):
                    mapping = {str(k): str(v) for k, v in parsed.items() if v}
            except json.JSONDecodeError:
                return jsonify({
                    "success": False,
                    "error": "Invalid mapping",
                    "message": "`mapping` must be a JSON object {raw_header: field_name}",
                }), 400

        duplicate_strategy = (request.form.get("duplicate_strategy") or "skip").strip().lower()

        service = _service()
        if mapping:
            result = service.import_files_with_mapping(
                files, target, mapping, created_by, duplicate_strategy=duplicate_strategy,
            )
        else:
            result = service.import_files(
                files, target, created_by, duplicate_strategy=duplicate_strategy,
            )

        totals = result["totals"]
        return jsonify({
            "success": (
                totals["created"] > 0
                or totals.get("updated", 0) > 0
                or totals["skipped"] > 0
                or totals["failed"] == 0
            ),
            "message": (
                f"Imported {totals['created']} created, "
                f"{totals.get('updated', 0)} updated, "
                f"{totals['skipped']} skipped, "
                f"{totals['failed']} failed."
            ),
            "data": result,
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": "Invalid import request", "message": str(e)}), 400
    except Exception as e:  # noqa: BLE001
        logger.error(f"[{target}] bulk_import failed: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Bulk import failed",
            "message": str(e),
        }), 500


def attach_bulk_import_routes(bp: Blueprint, target: str) -> None:
    """Register `/import/fields`, `/import/preview` and `/import` on ``bp``.

    Routes registered:
        GET    <prefix>/import/fields
        POST   <prefix>/import/preview
        POST   <prefix>/import

    `target` MUST be one of the keys in `bulk_import_service.TARGET_CONFIG`.
    """
    if target not in _TARGETS:
        raise ValueError(f"Unsupported bulk-import target: {target!r}")

    # Endpoints are namespaced per blueprint via Flask's view-function
    # name — prefixing with the target makes the names unique even if
    # multiple blueprints attach this helper.
    bp.add_url_rule(
        "/import/fields",
        view_func=lambda t=target: _get_import_fields(t),
        methods=["GET"],
        endpoint=f"{target}_get_import_fields",
    )
    bp.add_url_rule(
        "/import/preview",
        view_func=lambda t=target: _preview_import(t),
        methods=["POST"],
        endpoint=f"{target}_preview_import",
    )
    bp.add_url_rule(
        "/import",
        view_func=lambda t=target: _bulk_import(t),
        methods=["POST"],
        endpoint=f"{target}_bulk_import",
    )
