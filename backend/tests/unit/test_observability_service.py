"""Unit tests for local observability service."""

import os

import pytest

from src.services.observability_service import (
    ObservabilityService,
    get_observability_service,
    observability_enabled,
)


def test_record_and_summary():
    svc = ObservabilityService(max_events=10)
    svc.record(method="GET", path="/api/health", status=200, duration_ms=12.5)
    svc.record(method="POST", path="/api/auth/login", status=401, duration_ms=3.1, error="HTTP 401")
    summary = svc.summary()
    assert summary["sample_size"] == 2
    assert summary["status_counts"][200] == 1
    assert len(summary["endpoints"]) >= 1


def test_observability_flag(monkeypatch):
    monkeypatch.setenv("SAKURA_ENABLE_OBSERVABILITY", "false")
    assert observability_enabled() is False
    monkeypatch.setenv("SAKURA_ENABLE_OBSERVABILITY", "true")
    assert observability_enabled() is True


def test_singleton():
    a = get_observability_service()
    b = get_observability_service()
    assert a is b
