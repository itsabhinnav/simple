"""Unit tests for SSRF URL validation (SAK-040)."""

import pytest

from src.infrastructure.url_safety import spec_url_fetch_allowed, validate_fetch_url


def test_spec_url_fetch_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SAKURA_ALLOW_SPEC_URL_FETCH", raising=False)
    assert spec_url_fetch_allowed() is False


def test_rejects_non_http_scheme():
    ok, reason = validate_fetch_url("file:///etc/passwd")
    assert ok is False
    assert "http" in (reason or "").lower()


def test_rejects_missing_hostname():
    ok, reason = validate_fetch_url("https:///path")
    assert ok is False


def test_rejects_localhost():
    ok, reason = validate_fetch_url("http://localhost/spec.pdf")
    assert ok is False


def test_rejects_private_ip_literal():
    ok, reason = validate_fetch_url("http://192.168.1.10/spec.pdf")
    assert ok is False


def test_rejects_metadata_endpoint():
    ok, reason = validate_fetch_url("http://169.254.169.254/latest/meta-data")
    assert ok is False


def test_rejects_non_standard_port():
    ok, reason = validate_fetch_url("http://example.com:8080/spec.pdf")
    assert ok is False


def test_accepts_public_https_url(monkeypatch):
    monkeypatch.setattr(
        "src.infrastructure.url_safety.socket.getaddrinfo",
        lambda host, port, *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    ok, reason = validate_fetch_url("https://example.com/spec.pdf")
    assert ok is True
    assert reason is None
