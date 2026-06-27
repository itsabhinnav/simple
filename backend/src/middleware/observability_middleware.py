"""Flask middleware for local-only request observability."""

from __future__ import annotations

import time

from flask import Flask, g, request

from src.services.observability_service import get_observability_service, observability_enabled


def setup_observability(app: Flask) -> None:
    if not observability_enabled():
        return

    @app.before_request
    def _obs_start():
        g._obs_start = time.perf_counter()

    @app.after_request
    def _obs_record(response):
        started = getattr(g, "_obs_start", None)
        if started is None:
            return response
        duration_ms = (time.perf_counter() - started) * 1000.0
        username = getattr(g, "current_username", None)
        error = None
        if response.status_code >= 500:
            error = f"HTTP {response.status_code}"
        try:
            get_observability_service().record(
                method=request.method,
                path=request.path,
                status=response.status_code,
                duration_ms=duration_ms,
                username=username,
                error=error,
            )
        except Exception:
            app.logger.debug("observability record failed", exc_info=True)
        return response
