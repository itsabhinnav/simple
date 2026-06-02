"""Celery application factory for the hybrid document parsing engine.

Worker-side ONLY: must not depend on Flask app context. The orchestrator is
constructed via a lightweight WorkerContainer in `src.services.parsing.tasks`.
"""

from __future__ import annotations

import os

from celery import Celery

from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


def _resolve(key: str, env_var: str, default: str) -> str:
    env_value = os.environ.get(env_var)
    if env_value:
        return env_value
    try:
        cfg_value = get_config_manager().get_config(key, None)
    except Exception:  # noqa: BLE001 - never block worker startup on config
        cfg_value = None
    return cfg_value or default


broker_url = _resolve("parsing.celery.broker_url", "CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = _resolve("parsing.celery.result_backend", "CELERY_RESULT_BACKEND", "redis://localhost:6379/1")


celery = Celery("sakura_parsing", broker=broker_url, backend=result_backend)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    task_default_queue="parsing",
    timezone="UTC",
)

celery.autodiscover_tasks(["src.services.parsing"], related_name="tasks", force=True)

logger.info(
    f"Celery configured: broker={broker_url} backend={result_backend} queue=parsing"
)


__all__ = ["celery"]
