"""Activity / change-log API.

Endpoints:

  GET  /api/activity
       Recent activity across every tracked entity. Supports
       ?entity_type=<type>&limit=<n>&offset=<n> for filtering.

  GET  /api/activity/<entity_type>/<entity_id>
       Per-entity change history, newest first. Same limit/offset.

  GET  /api/activity/commit/<commit_hash>
       Inspect a single commit (full before/after snapshots + diff).

  POST /api/activity/commit/<commit_hash>/revert
       Restore the entity to the state captured in this commit's
       ``snapshot_before`` (or ``snapshot_after`` for delete-commits,
       which effectively un-deletes). The revert is itself recorded
       as a new activity_log row with ``action='restore'`` so the
       history is append-only.

The revert path delegates to the corresponding entity service to keep
the activity log in sync with whatever validation / side effects those
services impose.
"""

from typing import Any, Dict

from flask import Blueprint, jsonify, request

from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


def _ok(payload: Dict[str, Any], status: int = 200):
    return jsonify({"success": True, **payload}), status


def _err(message: str, status: int = 500, error: str = "Internal error"):
    return jsonify({"success": False, "error": error, "message": message}), status


def create_activity_blueprint(activity_log_service) -> Blueprint:
    """Create the activity blueprint bound to a concrete service instance."""
    bp = Blueprint("activity", __name__, url_prefix="/api/activity")

    @bp.route("/", methods=["GET"])
    def get_recent_activity():
        try:
            entity_type = request.args.get("entity_type") or None
            limit = int(request.args.get("limit", 50))
            offset = int(request.args.get("offset", 0))
            data = activity_log_service.get_recent(
                entity_type=entity_type, limit=limit, offset=offset
            )
            return _ok({"data": data, "count": len(data)})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load recent activity")
            return _err(str(exc))

    @bp.route("/<entity_type>/<entity_id>", methods=["GET"])
    def get_activity_for_entity(entity_type: str, entity_id: str):
        try:
            limit = int(request.args.get("limit", 50))
            offset = int(request.args.get("offset", 0))
            data = activity_log_service.get_for_entity(
                entity_type, entity_id, limit=limit, offset=offset
            )
            return _ok({"data": data, "count": len(data)})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load entity activity")
            return _err(str(exc))

    @bp.route("/commit/<commit_hash>", methods=["GET"])
    def get_commit(commit_hash: str):
        try:
            commit = activity_log_service.get_by_commit(commit_hash)
            if not commit:
                return _err("Commit not found", status=404, error="Not found")
            return _ok({"data": commit})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load commit")
            return _err(str(exc))

    @bp.route("/commit/<commit_hash>/revert", methods=["POST"])
    def revert_commit(commit_hash: str):
        """Roll an entity back to the state captured in ``snapshot_before``.

        For ``action='delete'`` commits we instead re-create the entity from
        ``snapshot_after`` which holds the row as it was just before
        deletion. The revert itself produces a new activity row.
        """
        try:
            commit = activity_log_service.get_by_commit(commit_hash)
            if not commit:
                return _err("Commit not found", status=404, error="Not found")

            entity_type = commit["entity_type"]
            entity_id = commit["entity_id"]
            entity_pk = commit.get("entity_pk")
            action = commit["action"]

            # Decide which snapshot to restore.
            if action == "delete":
                target_snapshot = commit.get("snapshot_before") or commit.get("snapshot_after")
            else:
                target_snapshot = commit.get("snapshot_before")

            if not target_snapshot:
                return _err(
                    "Cannot revert: no snapshot data captured for this commit",
                    status=400,
                    error="Bad request",
                )

            restored = _apply_revert(entity_type, entity_id, entity_pk, action, target_snapshot)
            return _ok({"data": restored, "message": f"Reverted to commit {commit_hash}"})
        except ValueError as exc:
            return _err(str(exc), status=400, error="Bad request")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Revert failed")
            return _err(str(exc))

    return bp


def _apply_revert(
    entity_type: str,
    entity_id: str,
    entity_pk: Any,
    original_action: str,
    snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply a snapshot back onto the live entity via its own service.

    Delegates rather than writing SQL directly so business validation and
    activity logging (the entity services emit ``action='restore'`` rows
    via the same code path as a normal update) stay consistent.
    """
    from src.infrastructure.dependency_injection import (
        get_requirement_service,
        get_test_case_service,
    )

    if entity_type == "requirement":
        from src.schemas.requirement_schema import RequirementUpdateSchema, RequirementCreateSchema

        # Whitelist the fields the update schema accepts.
        update_fields = set(RequirementUpdateSchema.__fields__.keys())
        payload = {}
        for k, v in snapshot.items():
            if k == "when_action":
                payload["when"] = v
            elif k == "then_result":
                payload["then"] = v
            elif k in update_fields:
                payload[k] = v

        service = get_requirement_service()
        if original_action == "delete":
            # Re-create using the snapshot. Pull required fields from the
            # snapshot itself; if requirement_id is missing this raises.
            create_payload = {**payload}
            if "requirement_id" not in create_payload and entity_id:
                create_payload["requirement_id"] = entity_id
            if "title" not in create_payload:
                create_payload["title"] = snapshot.get("title") or entity_id
            schema = RequirementCreateSchema(**{k: v for k, v in create_payload.items()
                                                if k in RequirementCreateSchema.__fields__})
            return service.create_requirement(schema)

        if not isinstance(entity_pk, int) or entity_pk <= 0:
            # Try to find by requirement_id if numeric PK is missing.
            from src.infrastructure.dependency_injection import get_hybrid_database_service
            db = get_hybrid_database_service()
            row = db.execute_query(
                "SELECT id FROM requirements WHERE requirement_id = ?",
                "default",
                params=(entity_id,),
            )
            data = row.get("data") or []
            if not data:
                raise ValueError(f"Requirement {entity_id} no longer exists")
            entity_pk = data[0]["id"]

        schema = RequirementUpdateSchema(**payload)
        restored = service.update_requirement(entity_pk, schema)
        if not restored:
            raise ValueError(f"Requirement {entity_id} not found")
        return restored

    if entity_type == "test_case":
        from src.schemas.test_case_schema import TestCaseCreateSchema

        service = get_test_case_service()
        # update_test_case accepts a dict; whitelist by stripping computed
        # fields that the service injects on read.
        computed = {"is_high_priority", "has_requirements", "test_complexity"}
        payload = {k: v for k, v in snapshot.items() if k not in computed and k != "id"}

        if original_action == "delete":
            create_fields = set(TestCaseCreateSchema.__fields__.keys())
            create_payload = {k: v for k, v in payload.items() if k in create_fields}
            if "test_case_id" not in create_payload and entity_id:
                create_payload["test_case_id"] = entity_id
            schema = TestCaseCreateSchema(**create_payload)
            return service.create_test_case(schema)

        restored = service.update_test_case(entity_id, payload)
        if not restored:
            raise ValueError(f"Test case {entity_id} not found")
        return restored

    raise ValueError(f"Revert is not supported for entity_type '{entity_type}'")
