"""Integration tests for the new robust parsing API endpoints.

Covers:
    POST /api/parsing/smart-preview            (sync unified preview)
    GET  /api/parsing/providers                (provider catalog)
    GET  /api/parsing/targets                  (target field catalog)
    GET  /api/specs/import/fields              (deterministic catalog)
    GET  /api/requirements/import/fields       (deterministic catalog)
    GET  /api/design-tickets/import/fields     (deterministic catalog)
    POST /api/specs/import/preview             (deterministic preview)

The parsing controller is exercised in isolation via a stub Flask app that
mounts only the parsing blueprint plus the per-resource bulk-import
blueprints — keeps this test independent of the heavier full-app wiring
in `main.py`.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from flask import Flask


@pytest.fixture()
def app(tmp_path: Path):
    """Build a minimal Flask app with the parsing + bulk-import routes."""
    from src.controllers.parsing_controller import create_parsing_blueprint
    from src.controllers._bulk_import_routes import attach_bulk_import_routes
    from src.infrastructure.dependency_injection import get_parsing_service
    from flask import Blueprint

    flask_app = Flask(__name__)
    flask_app.config.update(TESTING=True)

    flask_app.register_blueprint(create_parsing_blueprint(get_parsing_service()))

    for prefix, target in (
        ("/api/specs", "specifications"),
        ("/api/requirements", "requirements"),
        ("/api/design-tickets", "design_tickets"),
        ("/api/test-cases", "test_cases"),
    ):
        bp = Blueprint(f"{target}_test_bp", __name__, url_prefix=prefix)
        attach_bulk_import_routes(bp, target)
        flask_app.register_blueprint(bp)

    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


# --------------------------------------------------------------------- catalog


def test_providers_catalog_has_default(client):
    res = client.get("/api/parsing/providers")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["success"] is True
    assert "default" in payload["data"]
    assert isinstance(payload["data"]["providers"], list)
    # ollama/openai/anthropic auto-register on import.
    assert {"ollama", "openai", "anthropic"}.issubset(set(payload["data"]["providers"]))


def test_targets_catalog_lists_all_four(client):
    res = client.get("/api/parsing/targets")
    assert res.status_code == 200
    targets = res.get_json()["data"]["targets"]
    assert {"specifications", "requirements", "design_tickets", "test_cases"} <= set(targets.keys())
    assert "id_field" in targets["specifications"]
    assert "fields" in targets["test_cases"]


# ------------------------------------------------------------------- bulk import


@pytest.mark.parametrize(
    "prefix,id_field",
    [
        ("/api/specs", "spec_id"),
        ("/api/requirements", "requirement_id"),
        ("/api/design-tickets", "design_ticket_id"),
        ("/api/test-cases", "test_case_id"),
    ],
)
def test_each_target_exposes_import_fields(client, prefix, id_field):
    res = client.get(f"{prefix}/import/fields")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["success"] is True
    assert payload["data"]["id_field"] == id_field
    assert id_field in payload["data"]["fields"]


def test_specs_preview_reports_sheets(client, xlsx_fixture):
    upload = (BytesIO(xlsx_fixture.read_bytes()), xlsx_fixture.name)
    res = client.post(
        "/api/specs/import/preview",
        data={"file": upload},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    payload = res.get_json()["data"]
    assert payload["file"] == xlsx_fixture.name
    assert payload["sheets"], "expected at least one sheet"
    sheet = payload["sheets"][0]
    assert "raw_headers" in sheet
    assert "suggested_mapping" in sheet


# ------------------------------------------------------------------ smart-preview


def test_smart_preview_deterministic_only(client, xlsx_fixture):
    upload = (BytesIO(xlsx_fixture.read_bytes()), xlsx_fixture.name)
    res = client.post(
        "/api/parsing/smart-preview",
        data={"file": upload, "target": "specifications", "enable_ai": "false"},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["target"] == "specifications"
    assert data["deterministic"]["sheets"], "deterministic preview must surface sheets"
    assert data["ai"]["requested"] is False
    assert data["ai"]["skipped"] is True
    assert data["providers"]["providers"], "providers must be listed"
    assert "test_cases" in data["supported_targets"]


def test_smart_preview_rejects_unsupported_extension(client, tmp_path: Path):
    bad = tmp_path / "notes.txt"
    bad.write_text("not a workbook")
    upload = (BytesIO(bad.read_bytes()), bad.name)
    res = client.post(
        "/api/parsing/smart-preview",
        data={"file": upload, "target": "test_cases"},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400


def test_smart_preview_csv(client, tmp_path: Path):
    csv_path = tmp_path / "tests.csv"
    csv_path.write_text(
        "test_case_id,title,priority\nTC_LOGIN_001,Login OK,P1\nTC_LOGIN_002,Logout OK,P2\n",
        encoding="utf-8",
    )
    upload = (BytesIO(csv_path.read_bytes()), csv_path.name)
    res = client.post(
        "/api/parsing/smart-preview",
        data={"file": upload, "target": "test_cases", "enable_ai": "false"},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["deterministic"]["sheets"], "csv must produce a synthetic sheet"
    sheet = data["deterministic"]["sheets"][0]
    assert "test_case_id" in sheet["raw_headers"]
    assert sheet["target"] == "test_cases"


def test_smart_preview_target_validation(client, xlsx_fixture):
    upload = (BytesIO(xlsx_fixture.read_bytes()), xlsx_fixture.name)
    res = client.post(
        "/api/parsing/smart-preview",
        data={"file": upload, "target": "totally_unknown"},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400


def test_smart_preview_ai_degrades_gracefully_when_provider_offline(client, xlsx_fixture):
    """The AI stage must never fail the whole call.

    Ollama/OpenAI/Anthropic are unreachable in unit-test environments
    (network restrictor + no daemon), so the AI stage is expected to be
    `requested=true, skipped=true` with an `error` field — but the
    deterministic stage must still complete successfully.
    """
    upload = (BytesIO(xlsx_fixture.read_bytes()), xlsx_fixture.name)
    res = client.post(
        "/api/parsing/smart-preview",
        data={
            "file": upload,
            "target": "test_cases",
            "enable_ai": "true",
            "enable_visual": "false",
            "enable_vlm": "true",
        },
        content_type="multipart/form-data",
    )
    # Whether AI succeeds or skips, the call must respond 200 with
    # the deterministic preview attached.
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["deterministic"]["sheets"], "deterministic preview should still complete"
    assert data["ai"]["requested"] is True
