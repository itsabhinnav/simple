"""Celery application factory for the hybrid document parsing engine.

Worker-side ONLY: must not depend on Flask app context. The orchestrator is
constructed via a lightweight WorkerContainer in `src.services.parsing.tasks`.
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

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


def _enforce_loopback_broker(url: str, label: str) -> str:
    """SAK-039 fix: refuse to start if the Celery broker is not on loopback.

    Parsing tasks ship paragraph text, OCR results, and base64-encoded images
    through the broker — a remote Redis becomes an exfil channel. Operators
    who explicitly need a LAN broker can set ``SAKURA_ALLOW_REMOTE_BROKER=true``
    to opt out.
    """
    if os.environ.get("SAKURA_ALLOW_REMOTE_BROKER", "false").lower() == "true":
        if os.environ.get("ENVIRONMENT", "production").lower() == "production":
            raise RuntimeError(
                "SAKURA_ALLOW_REMOTE_BROKER=true is not permitted when ENVIRONMENT=production"
            )
        return url
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return url
    if host in ("localhost", "127.0.0.1", "::1"):
        return url
    try:
        if ipaddress.ip_address(host).is_loopback:
            return url
    except ValueError:
        pass
    raise RuntimeError(
        f"{label} must be a loopback Redis URL (got host {host!r}). "
        "Set SAKURA_ALLOW_REMOTE_BROKER=true if you have audited the consequences."
    )


broker_url = _enforce_loopback_broker(
    _resolve("parsing.celery.broker_url", "CELERY_BROKER_URL", "redis://localhost:6379/0"),
    "Celery broker_url",
)
result_backend = _enforce_loopback_broker(
    _resolve("parsing.celery.result_backend", "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    "Celery result_backend",
)


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
