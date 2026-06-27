"""Persist named filter presets as reusable test suites."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.infrastructure.logging_config import get_logger
from src.services.hybrid_database_service import HybridDatabaseService

logger = get_logger(__name__)

_SUITE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS test_suite_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    filters_json TEXT NOT NULL,
    created_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


class TestSuitePresetService:
    def __init__(self, database_service: HybridDatabaseService) -> None:
        self._db = database_service
        self._ensure_table()

    def _ensure_table(self) -> None:
        try:
            self._db.execute_query(_SUITE_TABLE_DDL.strip(), "default")
        except Exception:
            logger.exception("Failed to ensure test_suite_presets table")

    @staticmethod
    def _row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        raw = row.get("filters_json")
        if raw:
            try:
                filters = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except (TypeError, json.JSONDecodeError):
                filters = {}
        return {
            "id": row.get("id"),
            "name": row.get("name"),
            "description": row.get("description") or "",
            "filters": filters,
            "created_by": row.get("created_by"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def list_presets(self) -> List[Dict[str, Any]]:
        result = self._db.execute_query(
            "SELECT id, name, description, filters_json, created_by, created_at, updated_at "
            "FROM test_suite_presets ORDER BY name COLLATE NOCASE ASC",
            "default",
        )
        if not result.get("success"):
            raise RuntimeError(result.get("error") or "Failed to list test suites")
        return [self._row_to_dict(row) for row in (result.get("data") or [])]

    def get_preset(self, preset_id: int) -> Optional[Dict[str, Any]]:
        result = self._db.execute_query(
            "SELECT id, name, description, filters_json, created_by, created_at, updated_at "
            "FROM test_suite_presets WHERE id = ?",
            "default",
            params=(preset_id,),
        )
        if not result.get("success"):
            raise RuntimeError(result.get("error") or "Failed to load test suite")
        rows = result.get("data") or []
        return self._row_to_dict(rows[0]) if rows else None

    def create_preset(
        self,
        name: str,
        filters: Dict[str, Any],
        *,
        description: str = "",
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Suite name is required")
        if not isinstance(filters, dict):
            raise ValueError("filters must be an object")

        filters_json = json.dumps(filters, ensure_ascii=False)
        result = self._db.execute_query(
            "INSERT INTO test_suite_presets (name, description, filters_json, created_by) "
            "VALUES (?, ?, ?, ?)",
            "default",
            params=(clean_name, (description or "").strip(), filters_json, created_by),
        )
        if not result.get("success"):
            msg = str(result.get("error") or "")
            if "UNIQUE" in msg.upper():
                raise ValueError(f"A test suite named {clean_name!r} already exists")
            raise RuntimeError(msg or "Failed to create test suite")

        lookup = self._db.execute_query(
            "SELECT id FROM test_suite_presets WHERE name = ?",
            "default",
            params=(clean_name,),
        )
        rows = lookup.get("data") or []
        if not rows:
            raise RuntimeError("Suite created but could not be loaded")
        created = self.get_preset(int(rows[0]["id"]))
        if not created:
            raise RuntimeError("Suite created but could not be loaded")
        return created

    def update_preset(
        self,
        preset_id: int,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        existing = self.get_preset(preset_id)
        if not existing:
            return None

        next_name = (name or existing["name"]).strip()
        next_description = existing["description"] if description is None else (description or "").strip()
        next_filters = existing["filters"] if filters is None else filters
        if not next_name:
            raise ValueError("Suite name is required")
        if not isinstance(next_filters, dict):
            raise ValueError("filters must be an object")

        result = self._db.execute_query(
            "UPDATE test_suite_presets SET name = ?, description = ?, filters_json = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            "default",
            params=(
                next_name,
                next_description,
                json.dumps(next_filters, ensure_ascii=False),
                preset_id,
            ),
        )
        if not result.get("success"):
            msg = str(result.get("error") or "")
            if "UNIQUE" in msg.upper():
                raise ValueError(f"A test suite named {next_name!r} already exists")
            raise RuntimeError(msg or "Failed to update test suite")
        return self.get_preset(preset_id)

    def delete_preset(self, preset_id: int) -> bool:
        result = self._db.execute_query(
            "DELETE FROM test_suite_presets WHERE id = ?",
            "default",
            params=(preset_id,),
        )
        if not result.get("success"):
            raise RuntimeError(result.get("error") or "Failed to delete test suite")
        return int(result.get("row_count") or 0) > 0
