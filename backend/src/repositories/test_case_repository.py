"""SQLite repository for the ``test_cases`` table.

Multi-value columns (``feature``, ``region``, ``brand``, ``vehicle_variant``,
``vehicle_specification``, ``env_dependency``, ``testsuite_type``,
``reference_document``, ``associated_requirement_id``, ``screen_id``)
are persisted as JSON arrays so callers can supply ``["FOTA","BT"]`` and
get the same shape back.

Reads quietly migrate two retired columns onto their replacements:
    * legacy ``vehicle_mode`` JSON  → ``vehicle_specification``
    * legacy ``description`` text   → ``test_objective`` (when empty)

The column data is left in place on disk (SQLite ``DROP COLUMN`` is finicky
across versions) but never round-tripped through the API. ``_hydrate_row``
is the single funnel that strips them out of every response shape.

Reads are tolerant of legacy single-string rows: anything that does not
parse as a JSON list is returned as a one-element list (empty for blank
strings) so the API contract is uniform regardless of how the row was
written.

All write paths are parameterized — the previous implementation relied on
f-string interpolation, which is unsafe and prevented us from storing
JSON values that contain quotes.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.schemas.test_case_schema import (
    MULTI_VALUE_FIELDS,
    TestCaseCreateSchema,
)


_MULTI_VALUE_FIELD_SET = set(MULTI_VALUE_FIELDS)


def _serialize_multi(value: Any) -> Optional[str]:
    """Convert a list / scalar / None into the JSON string we persist."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        cleaned = [str(v).strip() for v in value if v is not None and str(v).strip() != ""]
        return json.dumps(cleaned)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return json.dumps([])
        if stripped.startswith("[") and stripped.endswith("]"):
            # Already JSON; round-trip to normalise whitespace.
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return json.dumps(
                        [str(v).strip() for v in parsed if v is not None and str(v).strip() != ""]
                    )
            except Exception:
                pass
        return json.dumps([part.strip() for part in stripped.split(",") if part.strip()])
    return json.dumps([str(value).strip()])


def _deserialize_multi(value: Any) -> List[str]:
    """Inverse of ``_serialize_multi`` — always returns a list (possibly empty)."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v is not None and str(v).strip() != ""]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return []
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if v is not None and str(v).strip() != ""]
            except Exception:
                pass
        return [part.strip() for part in stripped.split(",") if part.strip()]
    return [str(value).strip()]


def _hydrate_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Apply ``_deserialize_multi`` to every multi-value column in a row.

    Also migrates the two retired columns onto their replacements so legacy
    rows (written before the schema change) keep flowing through the API
    without dropping data:

        vehicle_mode (JSON list) -> vehicle_specification (when empty)
        description (text)       -> test_objective       (when empty)

    The legacy columns themselves are stripped from the response shape so
    clients only ever see the canonical names.
    """
    if not row:
        return row

    legacy_mode = row.pop("vehicle_mode", None)
    if legacy_mode is not None and not row.get("vehicle_specification"):
        row["vehicle_specification"] = legacy_mode

    legacy_description = row.pop("description", None)
    if legacy_description is not None and not row.get("test_objective"):
        row["test_objective"] = legacy_description

    for field in MULTI_VALUE_FIELDS:
        if field in row:
            row[field] = _deserialize_multi(row.get(field))
    return row


class ITestCaseRepository(ABC):
    """Interface for test case data access operations"""

    @abstractmethod
    def find_all(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def find_by_id(self, test_case_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def find_by_feature(self, feature: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def create(self, test_case_data: TestCaseCreateSchema) -> Dict[str, Any]:
        pass

    @abstractmethod
    def update(self, test_case_id: str, test_case_data: dict) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete(self, test_case_id: str) -> bool:
        pass


class TestCaseRepository(ITestCaseRepository):
    """Concrete implementation of test case repository"""

    def __init__(self, database_service, table_name: str = "test_cases", activity_log_service=None):
        self.database_service = database_service
        self.table_name = table_name
        # Late-bound: resolved lazily on first write to avoid a circular
        # DI dependency between this repository and the activity log
        # service (which itself depends on the database service).
        self._activity_log_service = activity_log_service

    def _get_activity_log(self):
        if self._activity_log_service is not None:
            return self._activity_log_service
        try:
            from src.infrastructure.dependency_injection import get_activity_log_service
            self._activity_log_service = get_activity_log_service()
        except Exception:
            self._activity_log_service = None
        return self._activity_log_service

    def _current_user(self) -> Dict[str, Any]:
        try:
            from flask import g
            user = getattr(g, "current_user", None) or {}
            return {
                "username": user.get("username") or g.get("current_username") or "system",
                "id": user.get("id"),
            }
        except Exception:
            return {"username": "system", "id": None}

    def find_all(self) -> List[Dict[str, Any]]:
        try:
            result = self.database_service.execute_query(
                f"SELECT * FROM {self.table_name} ORDER BY id",
                "default",
            )
            rows = result.get("data", []) or []
            return [_hydrate_row(r) for r in rows]
        except Exception as e:
            raise Exception(f"Failed to fetch test cases: {str(e)}")

    def find_by_id(self, test_case_id: str) -> Optional[Dict[str, Any]]:
        try:
            result = self.database_service.execute_query(
                f"SELECT * FROM {self.table_name} WHERE test_case_id = ?",
                "default",
                params=(test_case_id,),
            )
            test_cases = result.get("data", []) or []
            return _hydrate_row(test_cases[0]) if test_cases else None
        except Exception as e:
            raise Exception(f"Failed to fetch test case {test_case_id}: {str(e)}")

    def find_by_feature(self, feature: str) -> List[Dict[str, Any]]:
        # Substring match works on the JSON-serialised feature column too —
        # `["FOTA","BT"]` still contains the literal "FOTA".
        try:
            result = self.database_service.execute_query(
                f"SELECT * FROM {self.table_name} WHERE feature LIKE ?",
                "default",
                params=(f"%{feature}%",),
            )
            rows = result.get("data", []) or []
            return [_hydrate_row(r) for r in rows]
        except Exception as e:
            raise Exception(f"Failed to fetch test cases for feature {feature}: {str(e)}")

    def create(self, test_case_data: TestCaseCreateSchema) -> Dict[str, Any]:
        try:
            test_case_dict = test_case_data.model_dump()

            # Drop None values so SQLite uses column defaults; serialise lists.
            payload: Dict[str, Any] = {}
            for key, value in test_case_dict.items():
                if value is None:
                    continue
                if key in _MULTI_VALUE_FIELD_SET:
                    payload[key] = _serialize_multi(value)
                else:
                    payload[key] = value

            if not payload:
                raise Exception("No valid data provided for test case creation")

            columns = ", ".join(payload.keys())
            placeholders = ", ".join(["?"] * len(payload))
            params = tuple(payload.values())

            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
            result = self.database_service.execute_query(query, "default", params=params)

            if not result.get("success"):
                raise Exception(f"Insert failed: {result.get('error', 'Unknown error')}")

            created = self.find_by_id(test_case_data.test_case_id) or {}
            if not created:
                # Fallback (DB without RETURNING) — re-hydrate from the input.
                hydrated = test_case_dict.copy()
                for field in MULTI_VALUE_FIELDS:
                    hydrated[field] = _deserialize_multi(hydrated.get(field))
                hydrated["id"] = result.get("lastrowid")
                hydrated["created_at"] = result.get("created_at")
                hydrated["updated_at"] = result.get("updated_at")
                created = hydrated

            try:
                act = self._get_activity_log()
                if act:
                    user = self._current_user()
                    act.record_change(
                        entity_type="test_case",
                        entity_id=created.get("test_case_id") or test_case_data.test_case_id,
                        entity_pk=created.get("id"),
                        action="create",
                        before=None,
                        after=created,
                        author_username=user["username"],
                        author_id=user.get("id"),
                    )
            except Exception:  # noqa: BLE001
                pass

            return created
        except Exception as e:
            raise Exception(f"Failed to create test case: {str(e)}")

    def update(self, test_case_id: str, test_case_data: dict) -> Optional[Dict[str, Any]]:
        try:
            if not test_case_data:
                return self.find_by_id(test_case_id)

            before = self.find_by_id(test_case_id)
            if not before:
                return None

            payload: Dict[str, Any] = {}
            for key, value in test_case_data.items():
                if key in _MULTI_VALUE_FIELD_SET:
                    payload[key] = _serialize_multi(value)
                else:
                    payload[key] = value

            set_clause = ", ".join([f"{k} = ?" for k in payload.keys()])
            params = tuple(payload.values()) + (test_case_id,)

            query = (
                f"UPDATE {self.table_name} SET {set_clause}, "
                f"updated_at = CURRENT_TIMESTAMP WHERE test_case_id = ?"
            )
            result = self.database_service.execute_query(query, "default", params=params)

            if not result.get("success"):
                raise Exception(f"Update failed: {result.get('error', 'Unknown error')}")

            after = self.find_by_id(test_case_id)

            try:
                act = self._get_activity_log()
                if act and after:
                    user = self._current_user()
                    act.record_change(
                        entity_type="test_case",
                        entity_id=test_case_id,
                        entity_pk=after.get("id"),
                        action="update",
                        before=before,
                        after=after,
                        author_username=user["username"],
                        author_id=user.get("id"),
                    )
            except Exception:  # noqa: BLE001
                pass

            return after
        except Exception as e:
            raise Exception(f"Failed to update test case {test_case_id}: {str(e)}")

    def delete(self, test_case_id: str) -> bool:
        try:
            before = self.find_by_id(test_case_id)
            query = f"DELETE FROM {self.table_name} WHERE test_case_id = ?"
            result = self.database_service.execute_query(query, "default", params=(test_case_id,))
            success = result.get("success", False)

            if success and before:
                try:
                    act = self._get_activity_log()
                    if act:
                        user = self._current_user()
                        act.record_change(
                            entity_type="test_case",
                            entity_id=test_case_id,
                            entity_pk=before.get("id"),
                            action="delete",
                            before=before,
                            after=None,
                            author_username=user["username"],
                            author_id=user.get("id"),
                        )
                except Exception:  # noqa: BLE001
                    pass

            return success
        except Exception as e:
            raise Exception(f"Failed to delete test case {test_case_id}: {str(e)}")
