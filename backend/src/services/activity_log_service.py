"""Git-style activity / change log for tracked entities.

Every create / update / delete on a tracked entity writes a single
``activity_log`` row that captures:

  * a short commit hash (uuid-based, displayed as 12 hex chars in the UI)
  * the previous commit hash for the same entity (parent pointer, mirrors
    git's parent chain so a future revert endpoint can walk backwards)
  * a JSON diff: ``{field: {old, new}}`` for every field that changed
  * the full before/after snapshots (useful for restore + auditing)
  * a one-line human-readable summary
  * the authoring user (username + numeric id when available)

Compared to the existing ``schema_migrations`` table, which only tracks
DDL changes performed by the admin Schema Editor, this table records the
data plane.

The service is intentionally lightweight: a single class with one public
method (``record_change``) for writes and a few helpers for reads
(``get_for_entity``, ``get_recent``). It does NOT perform any reverse
mutations on its own — restore is implemented in the controller, which
delegates the actual write to the corresponding entity service.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Iterable, List, Optional

from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


# Columns that should never appear in diffs / snapshots — they are mutated
# automatically on every save and would otherwise dominate the diff noise.
_NOISY_COLUMNS = {"created_at", "updated_at"}


def _normalise(value: Any) -> Any:
    """Coerce values to a JSON-friendly, comparison-stable form."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_normalise(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items()}
    # datetimes, decimals, etc. — fall through as their string form.
    try:
        return str(value)
    except Exception:
        return repr(value)


def _compute_diff(
    before: Optional[Dict[str, Any]],
    after: Optional[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Return ``{field: {old, new}}`` for every field whose value differs."""
    before_n = {k: _normalise(v) for k, v in (before or {}).items() if k not in _NOISY_COLUMNS}
    after_n = {k: _normalise(v) for k, v in (after or {}).items() if k not in _NOISY_COLUMNS}

    keys: Iterable[str] = set(before_n.keys()) | set(after_n.keys())
    diff: Dict[str, Dict[str, Any]] = {}
    for key in sorted(keys):
        old = before_n.get(key)
        new = after_n.get(key)
        if old != new:
            diff[key] = {"old": old, "new": new}
    return diff


def _summarise(action: str, entity_type: str, entity_id: str, diff: Dict[str, Any]) -> str:
    if action == "create":
        return f"Created {entity_type} {entity_id}"
    if action == "delete":
        return f"Deleted {entity_type} {entity_id}"
    if action == "restore":
        return f"Restored {entity_type} {entity_id}"
    if not diff:
        return f"Touched {entity_type} {entity_id} (no field changes)"
    fields = list(diff.keys())
    if len(fields) == 1:
        return f"Updated {fields[0]} on {entity_type} {entity_id}"
    if len(fields) <= 3:
        return f"Updated {', '.join(fields)} on {entity_type} {entity_id}"
    return f"Updated {len(fields)} fields on {entity_type} {entity_id}"


class ActivityLogService:
    """Append-only change log persisted in the local SQLite database."""

    def __init__(self, database_service):
        self.database_service = database_service

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def record_change(
        self,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        author_username: Optional[str] = None,
        author_id: Optional[int] = None,
        entity_pk: Optional[int] = None,
        summary: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Persist one activity row. Returns the inserted row dict or None."""
        try:
            payload = self._build_change_payload(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                before=before,
                after=after,
                author_username=author_username,
                author_id=author_id,
                entity_pk=entity_pk,
                summary=summary,
            )
            if payload is None:
                return None

            result = self.database_service.execute_query(
                payload["query"], "default", params=payload["params"]
            )
            if not result.get("success"):
                logger.warning(
                    "Activity log write failed for %s/%s: %s",
                    entity_type, entity_id, result.get("error"),
                )
                return None
            return payload["meta"]
        except Exception as exc:  # noqa: BLE001
            logger.exception("Activity log error: %s", exc)
            return None

    def record_change_on_connection(
        self,
        conn,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        author_username: Optional[str] = None,
        author_id: Optional[int] = None,
        entity_pk: Optional[int] = None,
        summary: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Insert an activity row using an open SQLite connection (same transaction)."""
        try:
            payload = self._build_change_payload(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                before=before,
                after=after,
                author_username=author_username,
                author_id=author_id,
                entity_pk=entity_pk,
                summary=summary,
                parent_hash=self._latest_commit_hash_for(entity_type, entity_id),
            )
            if payload is None:
                return None
            conn.execute(payload["query"], payload["params"])
            return payload["meta"]
        except Exception as exc:  # noqa: BLE001
            logger.exception("Activity log (transaction) error: %s", exc)
            raise

    def _build_change_payload(
        self,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        author_username: Optional[str] = None,
        author_id: Optional[int] = None,
        entity_pk: Optional[int] = None,
        summary: Optional[str] = None,
        parent_hash: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        entity_type = str(entity_type)
        entity_id = str(entity_id)
        action = str(action).lower()

        diff = _compute_diff(before, after) if action in ("update", "restore") else {}
        if action == "create":
            diff = {
                k: {"old": None, "new": _normalise(v)}
                for k, v in (after or {}).items()
                if k not in _NOISY_COLUMNS and v not in (None, "", [])
            }
        elif action == "delete":
            diff = {
                k: {"old": _normalise(v), "new": None}
                for k, v in (before or {}).items()
                if k not in _NOISY_COLUMNS
            }

        commit_hash = uuid.uuid4().hex[:12]
        if parent_hash is None:
            parent_hash = self._latest_commit_hash_for(entity_type, entity_id)

        summary_text = summary or _summarise(action, entity_type, entity_id, diff)
        query = (
            "INSERT INTO activity_log "
            "(commit_hash, parent_hash, entity_type, entity_id, entity_pk, "
            " action, field_changes, snapshot_before, snapshot_after, "
            " summary, author_username, author_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            commit_hash,
            parent_hash,
            entity_type,
            entity_id,
            entity_pk,
            action,
            json.dumps(diff, ensure_ascii=False),
            json.dumps(_normalise(before or {}), ensure_ascii=False) if before else None,
            json.dumps(_normalise(after or {}), ensure_ascii=False) if after else None,
            summary_text,
            author_username or "system",
            author_id,
        )
        return {
            "query": query,
            "params": params,
            "meta": {
                "commit_hash": commit_hash,
                "parent_hash": parent_hash,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "summary": summary_text,
                "field_changes": diff,
                "author_username": author_username or "system",
                "author_id": author_id,
            },
        }

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def get_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit or 50), 500))
        offset = max(0, int(offset or 0))
        query = (
            "SELECT id, commit_hash, parent_hash, entity_type, entity_id, "
            "entity_pk, action, field_changes, snapshot_before, snapshot_after, "
            "summary, author_username, author_id, created_at "
            "FROM activity_log WHERE entity_type = ? AND entity_id = ? "
            "ORDER BY datetime(created_at) DESC, id DESC LIMIT ? OFFSET ?"
        )
        result = self.database_service.execute_query(
            query, "default", params=(entity_type, entity_id, limit, offset)
        )
        return [self._hydrate(row) for row in (result.get("data") or [])]

    def get_recent(
        self,
        entity_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit or 50), 500))
        offset = max(0, int(offset or 0))
        if entity_type:
            query = (
                "SELECT id, commit_hash, parent_hash, entity_type, entity_id, "
                "entity_pk, action, field_changes, snapshot_before, snapshot_after, "
                "summary, author_username, author_id, created_at "
                "FROM activity_log WHERE entity_type = ? "
                "ORDER BY datetime(created_at) DESC, id DESC LIMIT ? OFFSET ?"
            )
            result = self.database_service.execute_query(
                query, "default", params=(entity_type, limit, offset)
            )
        else:
            query = (
                "SELECT id, commit_hash, parent_hash, entity_type, entity_id, "
                "entity_pk, action, field_changes, snapshot_before, snapshot_after, "
                "summary, author_username, author_id, created_at "
                "FROM activity_log ORDER BY datetime(created_at) DESC, id DESC "
                "LIMIT ? OFFSET ?"
            )
            result = self.database_service.execute_query(
                query, "default", params=(limit, offset)
            )
        return [self._hydrate(row) for row in (result.get("data") or [])]

    def get_by_commit(self, commit_hash: str) -> Optional[Dict[str, Any]]:
        if not commit_hash:
            return None
        result = self.database_service.execute_query(
            "SELECT id, commit_hash, parent_hash, entity_type, entity_id, "
            "entity_pk, action, field_changes, snapshot_before, snapshot_after, "
            "summary, author_username, author_id, created_at "
            "FROM activity_log WHERE commit_hash = ? LIMIT 1",
            "default",
            params=(commit_hash,),
        )
        rows = result.get("data") or []
        return self._hydrate(rows[0]) if rows else None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _latest_commit_hash_for(self, entity_type: str, entity_id: str) -> Optional[str]:
        result = self.database_service.execute_query(
            "SELECT commit_hash FROM activity_log "
            "WHERE entity_type = ? AND entity_id = ? "
            "ORDER BY datetime(created_at) DESC, id DESC LIMIT 1",
            "default",
            params=(entity_type, entity_id),
        )
        rows = result.get("data") or []
        return rows[0]["commit_hash"] if rows else None

    def _hydrate(self, row: Dict[str, Any]) -> Dict[str, Any]:
        hydrated = dict(row)
        for key in ("field_changes", "snapshot_before", "snapshot_after"):
            raw = hydrated.get(key)
            if raw is None:
                hydrated[key] = None if key != "field_changes" else {}
                continue
            if isinstance(raw, (dict, list)):
                continue
            try:
                hydrated[key] = json.loads(raw)
            except Exception:
                hydrated[key] = raw
        return hydrated
