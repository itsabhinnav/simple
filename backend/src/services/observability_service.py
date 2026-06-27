"""Local-only API observability — no third-party telemetry (SAK-042)."""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import Deque, Dict, List, Optional

from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)

_MAX_EVENTS = 2000


@dataclass
class RequestMetric:
    method: str
    path: str
    status: int
    duration_ms: float
    timestamp: str
    username: Optional[str] = None
    error: Optional[str] = None


class ObservabilityService:
    """Ring buffer of recent request metrics stored in-process only."""

    def __init__(self, max_events: int = _MAX_EVENTS) -> None:
        self._events: Deque[RequestMetric] = deque(maxlen=max_events)
        self._lock = threading.Lock()
        self._started_at = time.time()

    def record(
        self,
        *,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        username: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        event = RequestMetric(
            method=method,
            path=path,
            status=status,
            duration_ms=round(duration_ms, 2),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            username=username,
            error=error,
        )
        with self._lock:
            self._events.append(event)

    def summary(self) -> Dict:
        with self._lock:
            events = list(self._events)

        by_path: Dict[str, Dict] = {}
        errors: List[Dict] = []
        status_counts: Dict[int, int] = {}

        for ev in events:
            status_counts[ev.status] = status_counts.get(ev.status, 0) + 1
            bucket = by_path.setdefault(
                ev.path,
                {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "errors": 0},
            )
            bucket["count"] += 1
            bucket["total_ms"] += ev.duration_ms
            bucket["max_ms"] = max(bucket["max_ms"], ev.duration_ms)
            if ev.status >= 500 or ev.error:
                bucket["errors"] += 1
                errors.append(asdict(ev))

        endpoints = []
        for path, stats in sorted(by_path.items(), key=lambda x: x[1]["count"], reverse=True)[:50]:
            count = stats["count"] or 1
            endpoints.append(
                {
                    "path": path,
                    "count": stats["count"],
                    "avg_ms": round(stats["total_ms"] / count, 2),
                    "max_ms": round(stats["max_ms"], 2),
                    "errors": stats["errors"],
                }
            )

        return {
            "uptime_seconds": round(time.time() - self._started_at),
            "sample_size": len(events),
            "status_counts": status_counts,
            "endpoints": endpoints,
            "recent_errors": errors[-20:],
        }


_service: Optional[ObservabilityService] = None
_service_lock = threading.Lock()


def observability_enabled() -> bool:
    return os.environ.get("SAKURA_ENABLE_OBSERVABILITY", "true").lower() not in (
        "false",
        "0",
        "no",
        "off",
    )


def get_observability_service() -> ObservabilityService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = ObservabilityService()
    return _service
