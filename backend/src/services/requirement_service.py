"""Requirement service — parameterized SQL with column-name remapping.

The Pydantic schema uses ``when`` / ``then`` as field names because that is
what the frontend (and the BDD-style domain) speaks. The underlying SQLite
columns are ``when_action`` / ``then_result`` because ``when`` and ``then``
are SQL reserved keywords (their use as identifiers produces a syntax error
on most SQLite builds, and would silently fail to update on others).

The previous implementation built UPDATE statements via f-string
interpolation of the raw schema keys. That produced
``SET when = '...', then = '...'``, which:

  * blew up with "near 'when': syntax error" on every save attempt, then
  * was reported back to the client as HTTP 404 (because the service
    returned ``None`` on failure), and finally
  * caused the detail page to reload the unchanged row, wiping the edit.

This rewrite eliminates the issue by:
  1. translating logical field names to physical column names
     (``when -> when_action``, ``then -> then_result``)
  2. using ? placeholders + a params tuple end-to-end
  3. surfacing real errors to the caller instead of swallowing them as 404
  4. recording every create / update / delete in the activity log so the
     UI can show a git-style change history per requirement.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from src.schemas.requirement_schema import (
    RequirementCreateSchema,
    RequirementUpdateSchema,
)
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


# Logical field name -> physical SQLite column. Anything not listed maps
# to itself. Keep this in sync with the requirements table DDL in
# ``LocalDatabaseService.ensure_tables_exist``.
_FIELD_TO_COLUMN = {
    "when": "when_action",
    "then": "then_result",
}


def _column_for(field: str) -> str:
    return _FIELD_TO_COLUMN.get(field, field)


# Columns the API exposes on read. Selected explicitly so legacy /
# experimental columns never leak into responses.
_SELECT_COLUMNS = (
    "id, requirement_id, srs_id, title, description, requirement_type, given, "
    "when_action, then_result, priority, status, assignee, tags, feature, "
    "region, brand, reference_spec_id, reference_spec_version, "
    "requirement_version, verification_method, linked_epic_jira_id, "
    "linked_test_case_ids, linked_design_ids, design_ticket_id, "
    "created_by, created_at, updated_at"
)


class IRequirementService(ABC):
    """Interface for requirement business logic operations"""

    @abstractmethod
    def get_all_requirements(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_requirement_by_id(self, req_id: int) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def create_requirement(self, requirement_data: RequirementCreateSchema) -> Dict[str, Any]:
        pass

    @abstractmethod
    def update_requirement(
        self, req_id: int, requirement_data: RequirementUpdateSchema
    ) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete_requirement(self, req_id: int) -> bool:
        pass


class RequirementService(IRequirementService):
    """Concrete implementation of the requirement service."""

    def __init__(self, database_service, activity_log_service=None):
        self.database_service = database_service
        # Late-bound to avoid a circular DI dependency; resolved lazily on
        # first write if not supplied at construction time.
        self._activity_log_service = activity_log_service

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_activity_log(self):
        if self._activity_log_service is not None:
            return self._activity_log_service
        try:
            from src.infrastructure.dependency_injection import get_activity_log_service
            self._activity_log_service = get_activity_log_service()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Activity log service unavailable: {exc}")
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

    def _row_to_dict(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        return dict(row)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def get_all_requirements(self) -> List[Dict[str, Any]]:
        try:
            query = f"SELECT {_SELECT_COLUMNS} FROM requirements ORDER BY created_at DESC"
            result = self.database_service.execute_query(query, "default")
            if not result.get("success"):
                raise Exception(result.get("error", "Unknown DB error"))
            return result.get("data", []) or []
        except Exception as e:
            logger.error(f"Failed to get requirements: {e}")
            raise Exception(f"Service error: Failed to get requirements - {str(e)}")

    def get_requirement_by_id(self, req_id: int) -> Optional[Dict[str, Any]]:
        try:
            if not isinstance(req_id, int) or req_id <= 0:
                raise ValueError("Invalid requirement ID")

            query = f"SELECT {_SELECT_COLUMNS} FROM requirements WHERE id = ?"
            result = self.database_service.execute_query(query, "default", params=(req_id,))
            if not result.get("success"):
                raise Exception(result.get("error", "Unknown DB error"))
            rows = result.get("data", []) or []
            return rows[0] if rows else None
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to get requirement: {e}")
            raise Exception(f"Service error: Failed to get requirement - {str(e)}")

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def create_requirement(self, requirement_data: RequirementCreateSchema) -> Dict[str, Any]:
        try:
            user = self._current_user()
            created_by = user["username"] or "system"

            payload_dict = requirement_data.dict(exclude_unset=False)
            # Strip None so SQLite uses defaults / NULL.
            payload: Dict[str, Any] = {}
            for key, value in payload_dict.items():
                if value is None:
                    continue
                payload[_column_for(key)] = value

            payload["created_by"] = created_by

            columns = ", ".join(payload.keys())
            placeholders = ", ".join(["?"] * len(payload))
            params = tuple(payload.values())

            query = f"INSERT INTO requirements ({columns}) VALUES ({placeholders})"
            result = self.database_service.execute_query(query, "default", params=params)

            if not result.get("success"):
                raise Exception(f"Insert failed: {result.get('error', 'Unknown error')}")

            new_pk = result.get("lastrowid")
            created = self.get_requirement_by_id(new_pk) if new_pk else None
            created_payload = created or {**payload, "id": new_pk}

            # Activity log: record creation with the full initial snapshot.
            try:
                act = self._get_activity_log()
                if act:
                    act.record_change(
                        entity_type="requirement",
                        entity_id=created_payload.get("requirement_id") or str(new_pk),
                        entity_pk=new_pk,
                        action="create",
                        before=None,
                        after=created_payload,
                        author_username=created_by,
                        author_id=user.get("id"),
                    )
            except Exception as log_exc:  # noqa: BLE001
                logger.warning(f"Activity log (create) failed: {log_exc}")

            return created_payload
        except Exception as e:
            logger.error(f"Failed to create requirement: {e}", exc_info=True)
            raise Exception(f"Service error: Failed to create requirement - {str(e)}")

    def update_requirement(
        self, req_id: int, requirement_data: RequirementUpdateSchema
    ) -> Optional[Dict[str, Any]]:
        try:
            if not isinstance(req_id, int) or req_id <= 0:
                raise ValueError("Invalid requirement ID")

            req_dict = requirement_data.dict(exclude_unset=True)
            if not req_dict:
                return self.get_requirement_by_id(req_id)

            # Snapshot the before-state for the activity log.
            before = self.get_requirement_by_id(req_id)
            if not before:
                # Don't 404 silently — surface so the controller can return 404.
                return None

            # Build a parameterized UPDATE using the logical->physical rename.
            set_parts: List[str] = []
            params: List[Any] = []
            for key, value in req_dict.items():
                col = _column_for(key)
                set_parts.append(f"{col} = ?")
                params.append(value)

            set_parts.append("updated_at = CURRENT_TIMESTAMP")
            set_clause = ", ".join(set_parts)

            query = f"UPDATE requirements SET {set_clause} WHERE id = ?"
            params.append(req_id)

            result = self.database_service.execute_query(
                query, "default", params=tuple(params)
            )
            if not result.get("success"):
                raise Exception(f"Update failed: {result.get('error', 'Unknown error')}")

            after = self.get_requirement_by_id(req_id)

            # Activity log: capture the diff in git-style commit form.
            try:
                act = self._get_activity_log()
                if act and after:
                    user = self._current_user()
                    act.record_change(
                        entity_type="requirement",
                        entity_id=after.get("requirement_id") or str(req_id),
                        entity_pk=req_id,
                        action="update",
                        before=before,
                        after=after,
                        author_username=user["username"],
                        author_id=user.get("id"),
                    )
            except Exception as log_exc:  # noqa: BLE001
                logger.warning(f"Activity log (update) failed: {log_exc}")

            return after
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to update requirement: {e}", exc_info=True)
            raise Exception(f"Service error: Failed to update requirement - {str(e)}")

    def delete_requirement(self, req_id: int) -> bool:
        try:
            if not isinstance(req_id, int) or req_id <= 0:
                raise ValueError("Invalid requirement ID")

            before = self.get_requirement_by_id(req_id)
            if not before:
                return False

            query = "DELETE FROM requirements WHERE id = ?"
            result = self.database_service.execute_query(query, "default", params=(req_id,))
            if not result.get("success"):
                raise Exception(result.get("error", "Unknown DB error"))

            try:
                act = self._get_activity_log()
                if act:
                    user = self._current_user()
                    act.record_change(
                        entity_type="requirement",
                        entity_id=before.get("requirement_id") or str(req_id),
                        entity_pk=req_id,
                        action="delete",
                        before=before,
                        after=None,
                        author_username=user["username"],
                        author_id=user.get("id"),
                    )
            except Exception as log_exc:  # noqa: BLE001
                logger.warning(f"Activity log (delete) failed: {log_exc}")

            return True
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete requirement: {e}", exc_info=True)
            raise Exception(f"Service error: Failed to delete requirement - {str(e)}")
