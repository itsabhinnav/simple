"""Unit tests for production security posture validation (SAK-041)."""

import pytest

from src.infrastructure.security_posture import validate_production_security_posture


def test_production_rejects_external_llm(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SAKURA_LLM_ALLOW_EXTERNAL", "true")
    with pytest.raises(RuntimeError, match="SAKURA_LLM_ALLOW_EXTERNAL"):
        validate_production_security_posture("strict")


def test_production_rejects_allow_lan_without_opt_in(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SAKURA_ALLOW_LAN_EGRESS", raising=False)
    with pytest.raises(RuntimeError, match="allow_lan"):
        validate_production_security_posture("allow_lan")


def test_production_accepts_strict_defaults(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SAKURA_LLM_ALLOW_EXTERNAL", "false")
    validate_production_security_posture("strict")


def test_development_allows_opt_out_flags(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SAKURA_LLM_ALLOW_EXTERNAL", "true")
    validate_production_security_posture("strict")
