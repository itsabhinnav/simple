"""Local-only database service.

The class is still called ``HybridDatabaseService`` for source compatibility
with the existing repository / service / controller layer, but the
"hybrid" half is gone — there is no remote database, no Git workspace,
no startup sync, and no periodic sync worker. Every read and write
goes straight to the local SQLite database via :class:`LocalDatabaseService`.

The remote/Git data-layer was removed in full; do not reintroduce it. If
distributed storage is needed in the future, design it as a separate
service rather than reviving the old git-mirror flow.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

from src.services.local_database_service import LocalDatabaseService
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class HybridDatabaseService:
    """Thin wrapper around :class:`LocalDatabaseService`.

    Kept under the original name so callers (controllers, repositories,
    services) don't need to be rewritten. All public methods are
    local-only — anything that previously reached out to git/remote has
    been removed.
    """

    def __init__(self, local_db_service: LocalDatabaseService):
        self.local_db = local_db_service
        # Local-only mode is permanent. The flag is kept (always False) so
        # any external caller that still inspects it doesn't crash.
        self.git_sync_enabled = False
        self.cache_expiry = 3600  # seconds — only used by the local cache table
        self.last_sync_time: datetime | None = None

        logger.info("HybridDatabaseService initialised in local-only mode")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> bool:
        """Initialise the local database. Always returns the local result."""
        logger.info("Initialising local database (local-only mode)")
        return self.local_db.initialize()

    def stop_periodic_sync(self) -> None:
        """No-op kept for backwards compatibility with old shutdown paths."""
        return None

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------
    def execute_query(
        self,
        query: str,
        database_name: str = "default",
        use_cache: bool = True,
        params: tuple = (),
    ) -> Dict[str, Any]:
        """Execute a SQL query against the local database."""
        try:
            query_upper = query.strip().upper()
            if query_upper.startswith("SELECT"):
                return self._handle_read_query(query, database_name, use_cache, params)
            return self._handle_write_query(query, database_name, params)
        except Exception as exc:
            logger.error(f"Query execution failed: {exc}")
            return {"success": False, "error": str(exc), "data": []}

    def _handle_read_query(
        self,
        query: str,
        database_name: str,
        use_cache: bool,
        params: tuple = (),
    ) -> Dict[str, Any]:
        result = self.local_db.execute_query(query, database_name, params=params)
        if result.get("success") and use_cache:
            try:
                import json
                cache_key = f"query_{hash(query)}"
                cache_data = json.dumps(result["data"])
                expires_at = datetime.now() + timedelta(seconds=self.cache_expiry)
                self.local_db.cache_data(cache_key, cache_data, expires_at.isoformat())
            except Exception as cache_exc:
                logger.debug(f"Result-cache write skipped: {cache_exc}")
        return result

    def _handle_write_query(
        self,
        query: str,
        database_name: str,
        params: tuple = (),
    ) -> Dict[str, Any]:
        result = self.local_db.execute_query(query, database_name, params=params)
        if result.get("success"):
            try:
                self.local_db.increment_database_version()
            except Exception as version_exc:
                logger.warning(f"Failed to bump database version: {version_exc}")
            self._clear_relevant_cache(query)
        return result

    def _clear_relevant_cache(self, query: str) -> None:
        try:
            query_upper = query.strip().upper()
            if query_upper.startswith("INSERT INTO"):
                table_name = query_upper.split("INSERT INTO", 1)[1].split()[0].strip()
            elif query_upper.startswith("UPDATE"):
                table_name = query_upper.split("UPDATE", 1)[1].split()[0].strip()
            elif query_upper.startswith("DELETE FROM"):
                table_name = query_upper.split("DELETE FROM", 1)[1].split()[0].strip()
            else:
                return
            self.local_db.clear_table_cache(table_name)
        except Exception as exc:
            logger.debug(f"Cache invalidation skipped: {exc}")

    # ------------------------------------------------------------------
    # Status / housekeeping (kept for the /api/sync/status legacy route)
    # ------------------------------------------------------------------
    def get_sync_status(self) -> Dict[str, Any]:
        return {
            "success": True,
            "mode": "local-only",
            "remote_sync_enabled": False,
            "message": "Remote/Git database sync has been removed.",
        }

    def cleanup_expired_cache(self) -> int:
        try:
            result = self.local_db.execute_query(
                "DELETE FROM local_cache WHERE expires_at IS NOT NULL "
                "AND expires_at < CURRENT_TIMESTAMP"
            )
            return int(result.get("row_count", 0)) if result.get("success") else 0
        except Exception as exc:
            logger.error(f"Failed to clean up expired cache: {exc}")
            return 0

    # ------------------------------------------------------------------
    # User preferences passthrough (used by /api/users/<id>/preferences)
    # ------------------------------------------------------------------
    def set_user_preference(self, user_id: int, preference_key: str, preference_value: str) -> bool:
        return self.local_db.set_user_preference(user_id, preference_key, preference_value)

    def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """Return user row + preferences from the local database only."""
        try:
            preferences = self.local_db.get_user_preferences(user_id)
            user_row: Dict[str, Any] = {}
            result = self.local_db.execute_query(
                "SELECT * FROM users WHERE id = ?",
                "default",
                params=(user_id,),
            )
            if result.get("success") and result.get("data"):
                user_row = result["data"][0]
            user_row["preferences"] = preferences
            return user_row
        except Exception as exc:
            logger.error(f"Failed to get user data: {exc}")
            return {}
