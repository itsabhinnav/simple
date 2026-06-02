"""Celery tasks for the hybrid document parsing engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from src.infrastructure.celery_app import celery
from src.infrastructure.logging_config import get_logger
from src.services.parsing.models import HybridParseResult, ParseOptions, ParseTaskStatus
from src.services.parsing.worker_container import WorkerContainer

logger = get_logger(__name__)


_PROGRESS_STAGES = ("DETERMINISTIC", "VISUAL", "ASSEMBLY", "VLM", "RECONCILIATION", "COMPLETED")


def _update(task, stage: str, info: Optional[Dict[str, Any]] = None) -> None:
    payload = {"stage": stage, "timestamp": datetime.utcnow().isoformat()}
    if info:
        payload.update(info)
    try:
        task.update_state(state="PROGRESS", meta=payload)
    except Exception as exc:  # noqa: BLE001 - never break the task on update failure
        logger.warning(f"could not update task state: {exc}")


@celery.task(
    bind=True,
    name="parsing.parse_document",
    max_retries=2,
    default_retry_delay=10,
)
def parse_document_task(self, file_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run the hybrid parser as a Celery task with progress reporting."""
    opts = ParseOptions(**(options or {}))

    _update(self, "DETERMINISTIC", {"file": file_path})
    container = WorkerContainer.instance()

    _update(self, "VISUAL")
    try:
        _update(self, "ASSEMBLY")
        _update(self, "VLM")
        result: HybridParseResult = container.parser.parse(file_path, opts)
    except Exception as exc:  # noqa: BLE001 - propagated to caller after retries
        logger.error(f"parse_document_task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)

    _update(self, "RECONCILIATION")
    payload = result.model_dump()
    _update(self, "COMPLETED", {"file_type": payload.get("file_type")})
    return payload


def parse_status(task_id: str) -> ParseTaskStatus:
    """Return a serializable status snapshot for a parsing task."""
    async_result = celery.AsyncResult(task_id)
    info = async_result.info if isinstance(async_result.info, dict) else {}
    return ParseTaskStatus(
        task_id=task_id,
        status=async_result.status,
        progress=info.get("stage") if isinstance(info, dict) else None,
        info=info if isinstance(info, dict) else {"value": str(async_result.info)},
        result=async_result.result if isinstance(async_result.result, dict) else None,
    )


__all__ = ["parse_document_task", "parse_status"]
