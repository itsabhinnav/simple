"""Unit tests for global API authentication gate."""

import os

# auth_controller refuses import without secrets — set test values first.
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-with-sufficient-entropy-32b")
os.environ.setdefault("ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

import pytest
from flask import Flask

from src.middleware.auth_middleware import enforce_authentication, is_auth_enforced


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SAKURA_REQUIRE_AUTH", "true")
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.route("/api/requirements")
    def protected():
        return {"ok": True}

    @app.route("/api/auth/login", methods=["POST"])
    def login():
        return {"ok": True}

    @app.route("/health")
    def health():
        return {"ok": True}

    @app.before_request
    def gate():
        response = enforce_authentication()
        if response is not None:
            return response

    return app


def test_unauthenticated_api_blocked(app):
    with app.test_client() as client:
        resp = client.get("/api/requirements")
        assert resp.status_code == 401


def test_public_auth_route_allowed(app):
    with app.test_client() as client:
        resp = client.post("/api/auth/login", json={"username": "a", "password": "b"})
        assert resp.status_code == 200


def test_health_not_blocked(app):
    with app.test_client() as client:
        resp = client.get("/health")
        assert resp.status_code == 200


def test_auth_can_be_disabled(monkeypatch):
    monkeypatch.setenv("SAKURA_REQUIRE_AUTH", "false")
    assert is_auth_enforced() is False
