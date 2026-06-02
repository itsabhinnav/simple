"""High-level service that bridges Flask uploads → orchestrator / Celery."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger
from src.services.parsing.hybrid_parser import HybridDocumentParser
from src.services.parsing.models import HybridParseResult, ParseOptions, ParseTaskStatus

logger = get_logger(__name__)


class ParsingService:
    """Bridge between the controller, the orchestrator, and the Celery task."""

    def __init__(self, hybrid_parser: HybridDocumentParser) -> None:
        self.hybrid_parser = hybrid_parser
        self._cm = get_config_manager()
        self._tmp_dir = Path(self._cm.get_config("parsing.tmp_dir", "data/tmp/parsing"))
        self._tmp_dir.mkdir(parents=True, exist_ok=True)

    def submit_parse(self, file_storage: Any, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Save the uploaded file and enqueue the Celery task. Returns task metadata."""
        saved_path = self._save_upload(file_storage)
        opts = ParseOptions(**(options or {}))
        try:
            from src.services.parsing.tasks import parse_document_task
        except Exception as exc:  # noqa: BLE001 - Celery may be unavailable
            raise RuntimeError(f"Celery unavailable: {exc}") from exc
        async_result = parse_document_task.apply_async(args=[str(saved_path), opts.model_dump(exclude_none=True)])
        return {
            "task_id": async_result.id,
            "status_url": f"/api/parsing/tasks/{async_result.id}",
            "result_url": f"/api/parsing/tasks/{async_result.id}/result",
            "submitted_at": datetime.utcnow().isoformat(),
        }

    def get_status(self, task_id: str) -> ParseTaskStatus:
        from src.services.parsing.tasks import parse_status

        return parse_status(task_id)

    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        from src.infrastructure.celery_app import celery

        async_result = celery.AsyncResult(task_id)
        if not async_result.ready():
            return None
        try:
            return async_result.get(timeout=1)
        except Exception as exc:  # noqa: BLE001 - return the error metadata
            logger.warning(f"could not fetch result for {task_id}: {exc}")
            return {"error": str(exc)}

    def parse_sync(self, file_path: str, options: Optional[Dict[str, Any]] = None) -> HybridParseResult:
        opts = ParseOptions(**(options or {}))
        return self.hybrid_parser.parse(file_path, opts)

    def parse_sync_upload(self, file_storage: Any, options: Optional[Dict[str, Any]] = None) -> HybridParseResult:
        saved_path = self._save_upload(file_storage)
        return self.parse_sync(str(saved_path), options)

    def _save_upload(self, file_storage: Any) -> Path:
        filename = getattr(file_storage, "filename", None) or "upload.bin"
        safe_name = Path(filename).name
        unique = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        target = self._tmp_dir / unique
        target.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(file_storage, "save"):
            file_storage.save(str(target))
        else:
            target.write_bytes(file_storage.read())
        logger.info(f"saved upload to {target}")
        return target
