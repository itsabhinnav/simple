import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class LocalDatabaseService:
    """Local SQLite database service for user-specific data"""
    
    def __init__(self):
        self.config_manager = get_config_manager()

        # The env var SAKURA_LOCAL_DB_PATH takes absolute priority over the
        # config file. The portable PyInstaller bundle sets this to an
        # absolute path next to the .exe so the database lives in a
        # user-writable location instead of inside the read-only _MEIPASS
        # extraction directory.
        env_override = os.environ.get("SAKURA_LOCAL_DB_PATH")
        if env_override:
            self.local_db_path = Path(env_override)
        else:
            self.local_db_path = Path(self.config_manager.get_config(
                "database.local_db_path",
                "data/local/dev/database/local.db",
            ))

        # Ensure directory exists
        self.local_db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Local database service initialized with path: {self.local_db_path}")
    
    def initialize(self) -> bool:
        """Initialize the local database with required tables"""
        try:
            logger.info("Initializing local database...")
            
            # Ensure tables exist
            self.ensure_tables_exist()
            
            logger.info("Local database initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize local database: {e}")
            return False
    
    def ensure_tables_exist(self) -> bool:
        """Ensure required local database tables exist"""
        try:
            logger.info("Ensuring local database tables exist...")
            
            # Get table names from configuration
            users_table = self.config_manager.get_table_name("users")
            test_cases_table = self.config_manager.get_table_name("test_cases")
            requirements_table = self.config_manager.get_table_name("requirements")
            
            # Create users table
            create_users_table = f"""
                CREATE TABLE IF NOT EXISTS {users_table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT,
                    secret_key_hash TEXT,
                    git_token_encrypted TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    role TEXT DEFAULT 'user',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Create test_cases table. NOTE: when adding new columns here, also
            # add them to `_test_case_column_additions` below so existing
            # databases get the columns via ALTER TABLE on the next startup.
            # Fresh databases get the post-June-2026 shape: no `description`
            # (use `test_objective` instead) and no `vehicle_mode`
            # (`vehicle_specification` is now multi-value and absorbs that role).
            # Existing databases keep the old columns intact — see the migration
            # block below for how legacy data is forwarded onto the new columns.
            create_test_cases_table = f"""
                CREATE TABLE IF NOT EXISTS {test_cases_table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_case_id TEXT UNIQUE NOT NULL,
                    title TEXT,
                    vehicle_model TEXT,
                    severity TEXT,
                    reference_document TEXT,
                    associated_requirement_id TEXT,
                    screen_id TEXT,
                    feature TEXT,
                    dr_applicable_screens TEXT,
                    dr_id TEXT,
                    test_objective TEXT,
                    preconditions TEXT,
                    procedure TEXT,
                    expected_behavior TEXT,
                    test_type TEXT,
                    region TEXT,
                    brand TEXT,
                    vehicle_variant TEXT,
                    vehicle_specification TEXT,
                    env_dependency TEXT,
                    requirement_type TEXT,
                    regulation TEXT,
                    priority TEXT,
                    testsuite_type TEXT,
                    created_by TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Create requirements table
            create_requirements_table = f"""
                CREATE TABLE IF NOT EXISTS {requirements_table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requirement_id TEXT UNIQUE NOT NULL,
                    srs_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    given TEXT,
                    when_action TEXT,
                    then_result TEXT,
                    requirement_type TEXT CHECK(requirement_type IN ('Functional', 'HMI', 'Safety', 'Performance', 'Usability')),
                    priority TEXT CHECK(priority IN ('P1', 'P2', 'P3', 'P4')),
                    status TEXT CHECK(status IN ('Draft', 'Approved', 'Implemented', 'Tested', 'Closed')) DEFAULT 'Draft',
                    assignee TEXT,
                    tags TEXT,
                    feature TEXT,
                    region TEXT,
                    brand TEXT,
                    reference_spec_id TEXT,
                    reference_spec_version TEXT,
                    requirement_version TEXT,
                    verification_method TEXT,
                    linked_epic_jira_id TEXT,
                    linked_test_case_ids TEXT,
                    linked_design_ids TEXT,
                    created_by TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    version TEXT DEFAULT '1.0'
                )
            """
            
            # Create user preferences table
            create_user_preferences_table = """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    preference_key TEXT NOT NULL,
                    preference_value TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, preference_key)
                )
            """
            
            # Create user sessions table
            create_user_sessions_table = """
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT UNIQUE NOT NULL,
                    expires_at DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Create local cache table for remote data
            create_local_cache_table = """
                CREATE TABLE IF NOT EXISTS local_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE NOT NULL,
                    cache_data TEXT NOT NULL,
                    last_synced DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Create sync status table
            create_sync_status_table = """
                CREATE TABLE IF NOT EXISTS sync_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT UNIQUE NOT NULL,
                    last_sync_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sync_status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Create database metadata table for version tracking
            create_database_metadata_table = """
                CREATE TABLE IF NOT EXISTS database_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metadata_key TEXT UNIQUE NOT NULL,
                    metadata_value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """

            # design_tickets used to live in scripts/migrate_add_design_tickets.py only,
            # which meant a fresh DB (e.g. after clean_db.ps1) lacked the table and
            # GET /api/design-tickets crashed with "no such table: design_tickets".
            # Mirror the migration's schema here so startup recreates it idempotently.
            create_design_tickets_table = """
                CREATE TABLE IF NOT EXISTS design_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    design_ticket_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    design_type TEXT,
                    diagram_type TEXT,
                    image_url TEXT,
                    priority TEXT,
                    status TEXT,
                    linked_requirement_id TEXT,
                    assignee TEXT,
                    tags TEXT,
                    created_by TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """

            # Schema migrations audit table — populated by SchemaService
            # whenever an admin applies a runtime DDL change. Created here
            # so the table is available even before SchemaService is first
            # touched by a request.
            create_schema_migrations_table = """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    applied_by TEXT,
                    operation TEXT NOT NULL,
                    table_name TEXT,
                    column_name TEXT,
                    details TEXT,
                    succeeded INTEGER NOT NULL DEFAULT 1,
                    error TEXT,
                    backup_path TEXT
                )
            """

            # Git-style activity log for data changes. Every create / update /
            # delete on a tracked entity (requirements, test cases, design
            # tickets, ...) writes one row here with a stable commit hash,
            # the author, and a JSON diff. The frontend renders this as a
            # history panel on the entity detail pages and the global
            # /activity feed.
            #
            # parent_hash chains commits on the same entity, mirroring git's
            # parent pointer so a future "revert to revision X" endpoint can
            # walk backwards through the history.
            create_activity_log_table = """
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    commit_hash TEXT UNIQUE NOT NULL,
                    parent_hash TEXT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    entity_pk INTEGER,
                    action TEXT NOT NULL,
                    field_changes TEXT,
                    snapshot_before TEXT,
                    snapshot_after TEXT,
                    summary TEXT,
                    author_username TEXT,
                    author_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            create_activity_log_entity_idx = (
                "CREATE INDEX IF NOT EXISTS idx_activity_log_entity "
                "ON activity_log(entity_type, entity_id, created_at DESC)"
            )
            create_activity_log_recent_idx = (
                "CREATE INDEX IF NOT EXISTS idx_activity_log_recent "
                "ON activity_log(created_at DESC)"
            )

            # Execute table creation queries
            self.execute_query(create_users_table, "default")
            self.execute_query(create_test_cases_table, "default")
            self.execute_query(create_requirements_table, "default")
            self.execute_query(create_user_preferences_table, "default")
            self.execute_query(create_user_sessions_table, "default")
            self.execute_query(create_local_cache_table, "default")
            self.execute_query(create_sync_status_table, "default")
            self.execute_query(create_database_metadata_table, "default")
            self.execute_query(create_design_tickets_table, "default")
            self.execute_query(create_schema_migrations_table, "default")
            self.execute_query(create_activity_log_table, "default")
            self.execute_query(create_activity_log_entity_idx, "default")
            self.execute_query(create_activity_log_recent_idx, "default")

            # Pair the design_tickets table with the requirements.design_ticket_id
            # column the migration script also adds, so the link from a requirement
            # to its design ticket survives a clean rebuild.
            self._add_missing_columns(
                requirements_table,
                {
                    "design_ticket_id": "TEXT",
                    "srs_id": "TEXT",
                    "feature": "TEXT",
                    "region": "TEXT",
                    "brand": "TEXT",
                    "reference_spec_id": "TEXT",
                    "reference_spec_version": "TEXT",
                    "requirement_version": "TEXT",
                    "verification_method": "TEXT",
                    "linked_epic_jira_id": "TEXT",
                    "linked_test_case_ids": "TEXT",
                    "linked_design_ids": "TEXT",
                },
            )
            
            # Idempotent column additions for existing databases that pre-date
            # newer columns. SQLite < 3.35 does not support `ADD COLUMN IF NOT
            # EXISTS`, so we ask the table for its current columns first and
            # only run ALTER for columns that are missing.
            #
            # `description` and `vehicle_mode` were retired in June 2026; we
            # don't add them on fresh DBs but do leave any existing copies in
            # place so the one-shot migration below can copy their data into
            # the canonical replacement columns before they fall out of the
            # API surface.
            self._add_missing_columns(
                test_cases_table,
                {
                    "title": "TEXT",
                    "vehicle_model": "TEXT",
                    "severity": "TEXT",
                    "vehicle_specification": "TEXT",
                    "reference_spec_id": "TEXT",
                    "reference_spec_version": "TEXT",
                },
            )

            # One-shot data migration: forward retired columns onto their
            # replacements when the new columns are still empty. Idempotent —
            # subsequent runs will find the destination already populated and
            # be a no-op.
            self._migrate_retired_test_case_columns(test_cases_table)
            
            # Initialize database version if not exists
            self.execute_query("""
                INSERT OR IGNORE INTO database_metadata (metadata_key, metadata_value)
                VALUES ('version', '1')
            """, "default")
            
            logger.info("Local database tables ensured successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure local tables exist: {e}")
            return False

    def _add_missing_columns(self, table_name: str, columns: Dict[str, str]) -> None:
        """Add columns to an existing table when they do not yet exist.

        SQLite does not have `ADD COLUMN IF NOT EXISTS`, so we query the
        existing schema with PRAGMA and only run ALTER for missing columns.
        Idempotent; safe to run on every startup.

        We open a direct sqlite3 connection here because the generic
        `execute_query` wrapper only fetches rows when the query starts with
        `SELECT`, so PRAGMA results would otherwise come back empty.
        """
        try:
            conn = sqlite3.connect(str(self.local_db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info({table_name})")
                existing = {row[1] for row in cursor.fetchall()}  # row[1] is the column name
                for column, column_type in columns.items():
                    if column in existing:
                        continue
                    try:
                        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column} {column_type}")
                        conn.commit()
                        logger.info(f"Migration: added column {table_name}.{column} ({column_type})")
                    except sqlite3.OperationalError as alter_exc:
                        # Either the column already exists (race) or some other
                        # benign mismatch — log but don't block startup.
                        if "duplicate column" in str(alter_exc).lower():
                            logger.debug(
                                f"Migration: column {table_name}.{column} already exists, skipping"
                            )
                        else:
                            logger.warning(
                                f"Migration: failed to add column {table_name}.{column}: {alter_exc}"
                            )
            finally:
                conn.close()
        except Exception as exc:
            logger.warning(f"Migration: column-addition check failed for {table_name}: {exc}")

    def _migrate_retired_test_case_columns(self, table_name: str) -> None:
        """Forward data from retired columns onto their replacements.

        The June 2026 schema removed two columns from the API surface but we
        don't physically drop them in SQLite (DROP COLUMN landed in 3.35 and
        not all environments ship a recent build). Instead, on every startup
        we copy:

            description    -> test_objective         when test_objective IS NULL
            vehicle_mode   -> vehicle_specification  when vehicle_specification IS NULL

        After the copy the legacy columns are still present on disk but the
        repository's _hydrate_row strips them from every response, so they
        become invisible to the API.

        Operation is idempotent: subsequent runs hit the IS NULL guard and
        no-op once every row has been migrated.
        """
        try:
            conn = sqlite3.connect(str(self.local_db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info({table_name})")
                existing = {row[1] for row in cursor.fetchall()}

                migrations = [
                    ("description", "test_objective"),
                    ("vehicle_mode", "vehicle_specification"),
                ]
                for legacy, canonical in migrations:
                    if legacy not in existing or canonical not in existing:
                        continue
                    cursor.execute(
                        f"UPDATE {table_name} "
                        f"SET {canonical} = {legacy} "
                        f"WHERE ({canonical} IS NULL OR {canonical} = '') "
                        f"  AND {legacy} IS NOT NULL "
                        f"  AND {legacy} <> ''"
                    )
                    moved = cursor.rowcount
                    if moved:
                        logger.info(
                            f"Migration: copied {moved} row(s) "
                            f"{table_name}.{legacy} -> {table_name}.{canonical}"
                        )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            logger.warning(
                f"Migration: retired-column copy failed for {table_name}: {exc}"
            )

    def get_database_version(self) -> int:
        """Get the current database version"""
        try:
            query = "SELECT metadata_value FROM database_metadata WHERE metadata_key = 'version'"
            result = self.execute_query(query, "default")
            
            if result.get("success") and result.get("data"):
                return int(result["data"][0]["metadata_value"])
            else:
                # If no version exists, initialize it to 1
                self.execute_query("""
                    INSERT OR REPLACE INTO database_metadata (metadata_key, metadata_value)
                    VALUES ('version', '1')
                """, "default")
                return 1
        except Exception as e:
            logger.error(f"Failed to get database version: {e}")
            return 1
    
    def increment_database_version(self) -> int:
        """Increment the database version"""
        try:
            current_version = self.get_database_version()
            new_version = current_version + 1
            
            query = """
                INSERT OR REPLACE INTO database_metadata (metadata_key, metadata_value, updated_at)
                VALUES ('version', ?, CURRENT_TIMESTAMP)
            """
            self.execute_query(f"UPDATE database_metadata SET metadata_value = '{new_version}' WHERE metadata_key = 'version'", "default")
            
            logger.info(f"Database version incremented: {current_version} -> {new_version}")
            return new_version
        except Exception as e:
            logger.error(f"Failed to increment database version: {e}")
            return self.get_database_version()
    
    def execute_query(self, query: str, database_name: str = "default", params: tuple = (), **kwargs) -> Dict[str, Any]:
        """Execute a query on the local database
        
        Args:
            query: SQL query string
            database_name: Database name (ignored for local service)
            params: Optional tuple of parameters for the query
            **kwargs: Additional parameters for compatibility
        """
        try:
            conn = sqlite3.connect(str(self.local_db_path))
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            try:
                # Execute the query with parameters if provided
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                # Determine if this is a SELECT query
                if query.strip().upper().startswith('SELECT'):
                    rows = cursor.fetchall()
                    data = [dict(row) for row in rows]
                    return {
                        "success": True,
                        "data": data,
                        "row_count": len(data)
                    }
                else:
                    # For INSERT, UPDATE, DELETE
                    conn.commit()
                    return {
                        "success": True,
                        "row_count": cursor.rowcount,
                        "lastrowid": cursor.lastrowid
                    }
                    
            finally:
                cursor.close()
                conn.close()
                
        except Exception as e:
            logger.error(f"Local database query failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": []
            }
    
    def _execute_query_with_params(self, query: str, params: tuple = ()) -> Dict[str, Any]:
        """Execute a query with parameters"""
        try:
            conn = sqlite3.connect(str(self.local_db_path))
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            try:
                cursor.execute(query, params)
                
                # Determine if this is a SELECT query
                if query.strip().upper().startswith('SELECT'):
                    rows = cursor.fetchall()
                    data = [dict(row) for row in rows]
                    return {
                        "success": True,
                        "data": data,
                        "row_count": len(data)
                    }
                else:
                    # For INSERT, UPDATE, DELETE
                    conn.commit()
                    return {
                        "success": True,
                        "row_count": cursor.rowcount,
                        "lastrowid": cursor.lastrowid
                    }
                    
            finally:
                cursor.close()
                conn.close()
                
        except Exception as e:
            logger.error(f"Local database query with params failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": []
            }
    
    def get_user_preference(self, user_id: int, preference_key: str) -> Optional[str]:
        """Get a user preference value"""
        result = self._execute_query_with_params(
            "SELECT preference_value FROM user_preferences WHERE user_id = ? AND preference_key = ?",
            (user_id, preference_key)
        )
        
        if result["success"] and result["data"]:
            return result["data"][0]["preference_value"]
        return None
    
    def set_user_preference(self, user_id: int, preference_key: str, preference_value: str) -> bool:
        """Set a user preference value"""
        result = self._execute_query_with_params(
            """INSERT OR REPLACE INTO user_preferences (user_id, preference_key, preference_value, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (user_id, preference_key, preference_value)
        )
        return result["success"]
    
    def get_user_preferences(self, user_id: int) -> Dict[str, str]:
        """Get all user preferences"""
        result = self._execute_query_with_params(
            "SELECT preference_key, preference_value FROM user_preferences WHERE user_id = ?",
            (user_id,)
        )
        
        if result["success"]:
            return {row["preference_key"]: row["preference_value"] for row in result["data"]}
        return {}
    
    def cache_data(self, cache_key: str, data: str, expires_at: Optional[str] = None) -> bool:
        """Cache data locally"""
        result = self._execute_query_with_params(
            """INSERT OR REPLACE INTO local_cache (cache_key, cache_data, expires_at, last_synced)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (cache_key, data, expires_at)
        )
        return result["success"]
    
    def get_cached_data(self, cache_key: str) -> Optional[str]:
        """Get cached data"""
        result = self._execute_query_with_params(
            "SELECT cache_data FROM local_cache WHERE cache_key = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",
            (cache_key,)
        )
        
        if result["success"] and result["data"]:
            return result["data"][0]["cache_data"]
        return None
    
    def update_sync_status(self, table_name: str, status: str, error_message: str = None) -> bool:
        """Update sync status for a table"""
        result = self._execute_query_with_params(
            """INSERT OR REPLACE INTO sync_status (table_name, sync_status, error_message, last_sync_time, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (table_name, status, error_message)
        )
        return result["success"]
    
    def get_sync_status(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get sync status for a table"""
        result = self._execute_query_with_params(
            "SELECT * FROM sync_status WHERE table_name = ?",
            (table_name,)
        )
        
        if result["success"] and result["data"]:
            return result["data"][0]
        return None
    
    def get_all_sync_statuses(self) -> List[Dict[str, Any]]:
        """Get all sync statuses"""
        result = self.execute_query("SELECT * FROM sync_status ORDER BY table_name")
        
        if result["success"]:
            return result["data"]
        return []
    
    def clear_table_cache(self, table_name: str) -> bool:
        """Clear cache entries related to a specific table"""
        try:
            # Clear all query-based cache entries (since we can't easily match them to specific tables)
            result = self.execute_query(
                "DELETE FROM local_cache WHERE cache_key LIKE 'query_%'"
            )
            
            # Also clear remote table cache entries
            result2 = self.execute_query(
                "DELETE FROM local_cache WHERE cache_key = ?",
                "default",
                (f"remote_{table_name}",)
            )
            
            logger.info(f"Cleared all query cache entries for table: {table_name}")
            return result["success"] and result2["success"]
            
        except Exception as e:
            logger.error(f"Failed to clear cache for table {table_name}: {e}")
            return False