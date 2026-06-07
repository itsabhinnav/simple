"""HTTP controller for the natural-language assistant."""

from __future__ import annotations

import json
from typing import Any, Dict

from flask import Blueprint, Response, jsonify, request, stream_with_context

from src.infrastructure.logging_config import get_logger
from src.services.assistant_service import AssistantService

logger = get_logger(__name__)


def create_assistant_blueprint(assistant_service: AssistantService) -> Blueprint:
    bp = Blueprint("assistant", __name__, url_prefix="/api/assistant")

    @bp.route("/chat", methods=["POST"])
    def chat() -> Any:
        try:
            payload: Dict[str, Any] = request.get_json(silent=True) or {}
            result = assistant_service.answer(
                question=payload.get("question", ""),
                history=payload.get("history") or [],
                kinds=payload.get("kinds"),
                provider=payload.get("provider"),
            )
            return jsonify({"success": True, "data": result}), 200
        except ValueError as exc:
            return jsonify({"success": False, "error": "Invalid request", "message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Assistant chat failed: {exc}", exc_info=True)
            return jsonify({"success": False, "error": "Assistant failure", "message": str(exc)}), 500

    @bp.route("/stream", methods=["POST"])
    def stream() -> Any:
        try:
            payload: Dict[str, Any] = request.get_json(silent=True) or {}
            question = payload.get("question", "")
            history = payload.get("history") or []
            kinds = payload.get("kinds")
            provider = payload.get("provider")
        except Exception as exc:  # noqa: BLE001
            return jsonify({"success": False, "message": str(exc)}), 400

        def generate():
            try:
                for event, data in assistant_service.answer_stream(
                    question=question, history=history, kinds=kinds, provider=provider
                ):
                    yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            except ValueError as exc:
                yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Assistant stream failed: {exc}", exc_info=True)
                yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @bp.route("/index/status", methods=["GET"])
    def index_status() -> Any:
        try:
            from src.infrastructure.dependency_injection import get_vector_index_service
            vec = get_vector_index_service()
            if vec is None:
                return jsonify({"success": True, "data": {"enabled": False, "backend": "disabled"}}), 200
            st = vec.status()
            return jsonify({"success": True, "data": st.__dict__}), 200
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Index status failed: {exc}", exc_info=True)
            return jsonify({"success": False, "message": str(exc)}), 500

    @bp.route("/index/refresh", methods=["POST"])
    def index_refresh() -> Any:
        try:
            from src.infrastructure.dependency_injection import get_vector_index_service, get_live_indexer
            vec = get_vector_index_service()
            if vec is None:
                return jsonify({"success": False, "message": "RAG disabled"}), 400
            payload = request.get_json(silent=True) or {}
            force = bool(payload.get("force"))
            indexer = get_live_indexer()
            if indexer is not None:
                indexer.trigger_now()
            summary = vec.reindex(force=force)
            return jsonify({"success": True, "data": {"summary": summary, "status": vec.status().__dict__}}), 200
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Index refresh failed: {exc}", exc_info=True)
            return jsonify({"success": False, "message": str(exc)}), 500

    @bp.route("/providers", methods=["GET"])
    def providers() -> Any:
        """Return the list of registered providers + current default so the
        frontend's provider picker can render without hitting the admin API."""
        try:
            from src.interfaces.llm_provider import get_vlm_registry

            registry = get_vlm_registry()
            return jsonify({
                "success": True,
                "data": {
                    "providers": registry.list_providers(),
                    "default": registry.get_default_name(),
                },
            }), 200
        except Exception as exc:  # noqa: BLE001
            return jsonify({"success": False, "message": str(exc)}), 500

    return bp
