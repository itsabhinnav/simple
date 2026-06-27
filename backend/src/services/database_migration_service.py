"""Centralized, idempotent SQLite schema migrations.

Runs on every startup after base tables are created:
  * ADD COLUMN for any registered column missing from an existing table
  * forward data from retired columns onto replacements
  * back-fill NULL / empty cells with configured defaults
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger
from src.services.local_database_service import LocalDatabaseService

logger = get_logger(__name__)

# Columns to add on existing databases. Keys are logical table names; values
# map column_name -> SQLite type declaration.
TABLE_COLUMN_MIGRATIONS: Dict[str, Dict[str, str]] = {
    "requirements": {
        "srs_id": "TEXT",
        "given": "TEXT",
        "when_action": "TEXT",
        "then_result": "TEXT",
        "assignee": "TEXT",
        "tags": "TEXT",
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
        "design_ticket_id": "TEXT",
        "status": "TEXT DEFAULT 'Draft'",
    },
    "test_cases": {
        "title": "TEXT",
        "vehicle_model": "TEXT",
        "severity": "TEXT",
        "reference_document": "TEXT",
        "associated_requirement_id": "TEXT",
        "screen_id": "TEXT",
        "feature": "TEXT",
        "dr_applicable_screens": "TEXT",
        "dr_id": "TEXT",
        "test_objective": "TEXT",
        "preconditions": "TEXT",
        "procedure": "TEXT",
        "expected_behavior": "TEXT",
        "test_type": "TEXT",
        "region": "TEXT",
        "brand": "TEXT",
        "vehicle_variant": "TEXT",
        "vehicle_specification": "TEXT",
        "env_dependency": "TEXT",
        "requirement_type": "TEXT",
        "regulation": "TEXT",
        "priority": "TEXT",
        "testsuite_type": "TEXT",
        "created_by": "TEXT",
        "reference_spec_id": "TEXT",
        "reference_spec_version": "TEXT",
    },
    "design_tickets": {
        "description": "TEXT",
        "design_type": "TEXT",
        "diagram_type": "TEXT",
        "image_url": "TEXT",
        "priority": "TEXT",
        "status": "TEXT",
        "linked_requirement_id": "TEXT",
        "assignee": "TEXT",
        "tags": "TEXT",
        "created_by": "TEXT",
    },
    "specifications": {
        "spec_id": "TEXT",
        "title": "TEXT",
        "project": "TEXT",
        "tags": "TEXT",
        "category": "TEXT",
        "version": "TEXT",
        "status": "TEXT",
        "file_url": "TEXT",
        "file_name": "TEXT",
        "source_url": "TEXT",
        "created_by": "TEXT",
    },
}

# Back-fill defaults for rows where a column is NULL or empty string.
TABLE_COLUMN_DEFAULTS: Dict[str, Dict[str, str]] = {
    "requirements": {
        "status": "Draft",
        "priority": "P2",
        "version": "1.0",
    },
    "design_tickets": {
        "status": "Draft",
        "priority": "P2",
    },
    "specifications": {
        "status": "Draft",
    },
}

# Copy legacy column values into replacements when the target is empty.
RETIRED_COLUMN_MIGRATIONS: List[Tuple[str, str, str]] = [
    ("test_cases", "description", "test_objective"),
    ("test_cases", "vehicle_mode", "vehicle_specification"),
]

SPECIFICATIONS_DDL = """
    CREATE TABLE IF NOT EXISTS specifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        spec_id TEXT NOT NULL,
        title TEXT NOT NULL,
        project TEXT,
        tags TEXT,
        category TEXT,
        version TEXT,
        status TEXT,
        file_url TEXT,
        file_name TEXT,
        source_url TEXT,
        created_by TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(project, spec_id, version)
    )
"""

TEST_SUITE_PRESETS_DDL = """
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

APP_MIGRATIONS_DDL = """
    CREATE TABLE IF NOT EXISTS app_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
"""

# (index_name, logical_table, column)
PERFORMANCE_INDEXES: List[Tuple[str, str, str]] = [
    ("idx_requirements_status", "requirements", "status"),
    ("idx_requirements_feature", "requirements", "feature"),
    ("idx_requirements_priority", "requirements", "priority"),
    ("idx_requirements_requirement_id", "requirements", "requirement_id"),
    ("idx_test_cases_feature", "test_cases", "feature"),
    ("idx_test_cases_priority", "test_cases", "priority"),
    ("idx_test_cases_test_type", "test_cases", "test_type"),
    ("idx_design_tickets_status", "design_tickets", "status"),
    ("idx_design_tickets_linked_req", "design_tickets", "linked_requirement_id"),
    ("idx_specifications_project", "specifications", "project"),
    ("idx_specifications_status", "specifications", "status"),
]

# Numbered, one-time migrations recorded in app_migrations.
VERSIONED_MIGRATIONS: List[Tuple[int, str]] = [
    (1, "performance_indexes"),
]


class DatabaseMigrationService:
    """Applies registered schema migrations against the local SQLite file."""

    def __init__(self, local_db: LocalDatabaseService):
        self.local_db = local_db
        self._config = get_config_manager()

    def run_all(self) -> bool:
        try:
            self._ensure_app_migrations_table()
            self._ensure_specifications_table()
            self._ensure_test_suite_presets_table()
            self._run_versioned_migrations()
            self._apply_column_migrations()
            self._migrate_retired_columns()
            self._apply_column_defaults()
            self._record_schema_version()
            return True
        except Exception:
            logger.exception("Database migration run failed")
            return False

    def _ensure_app_migrations_table(self) -> None:
        self.local_db.execute_query(APP_MIGRATIONS_DDL.strip(), "default")

    def _get_applied_migration_version(self) -> int:
        result = self.local_db.execute_query(
            "SELECT COALESCE(MAX(version), 0) AS v FROM app_migrations",
            "default",
        )
        if result.get("success") and result.get("data"):
            return int(result["data"][0]["v"])
        return 0

    def _mark_migration_applied(self, version: int, name: str) -> None:
        self.local_db.execute_query(
            "INSERT OR IGNORE INTO app_migrations (version, name) VALUES (?, ?)",
            "default",
            params=(version, name),
        )

    def _run_versioned_migrations(self) -> None:
        current = self._get_applied_migration_version()
        for version, name in VERSIONED_MIGRATIONS:
            if version <= current:
                continue
            if name == "performance_indexes":
                self._apply_index_migrations()
            self._mark_migration_applied(version, name)
            logger.info("Applied app migration v%s (%s)", version, name)

    def _apply_index_migrations(self) -> None:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            for index_name, logical_table, column in PERFORMANCE_INDEXES:
                table = self._resolve_table(logical_table)
                if not self._table_exists(cursor, table):
                    continue
                cursor.execute(f"PRAGMA table_info({table})")
                existing_cols = {row[1] for row in cursor.fetchall()}
                if column not in existing_cols:
                    continue
                ddl = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})"
                try:
                    cursor.execute(ddl)
                    conn.commit()
                    logger.info("Migration: ensured index %s on %s(%s)", index_name, table, column)
                except sqlite3.OperationalError as exc:
                    logger.warning("Migration: index %s failed: %s", index_name, exc)
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.local_db.local_db_path), timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _resolve_table(self, logical_name: str) -> str:
        return self._config.get_table_name(logical_name)

    def _table_exists(self, cursor: sqlite3.Cursor, table: str) -> bool:
        row = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table,),
        ).fetchone()
        return row is not None

    def _ensure_specifications_table(self) -> None:
        self.local_db.execute_query(SPECIFICATIONS_DDL.strip(), "default")

    def _ensure_test_suite_presets_table(self) -> None:
        self.local_db.execute_query(TEST_SUITE_PRESETS_DDL.strip(), "default")

    def _apply_column_migrations(self) -> None:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            for logical_table, columns in TABLE_COLUMN_MIGRATIONS.items():
                table = self._resolve_table(logical_table)
                if not self._table_exists(cursor, table):
                    continue
                cursor.execute(f"PRAGMA table_info({table})")
                existing = {row[1] for row in cursor.fetchall()}
                for column, col_type in columns.items():
                    if column in existing:
                        continue
                    try:
                        cursor.execute(
                            f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                        )
                        conn.commit()
                        logger.info(
                            "Migration: added column %s.%s (%s)", table, column, col_type
                        )
                    except sqlite3.OperationalError as exc:
                        if "duplicate column" in str(exc).lower():
                            logger.debug(
                                "Migration: column %s.%s already exists", table, column
                            )
                        else:
                            logger.warning(
                                "Migration: failed to add %s.%s: %s", table, column, exc
                            )
        finally:
            conn.close()

    def _migrate_retired_columns(self) -> None:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            for logical_table, legacy, canonical in RETIRED_COLUMN_MIGRATIONS:
                table = self._resolve_table(logical_table)
                if not self._table_exists(cursor, table):
                    continue
                cursor.execute(f"PRAGMA table_info({table})")
                existing = {row[1] for row in cursor.fetchall()}
                if legacy not in existing or canonical not in existing:
                    continue
                cursor.execute(
                    f"UPDATE {table} "
                    f"SET {canonical} = {legacy} "
                    f"WHERE ({canonical} IS NULL OR {canonical} = '') "
                    f"  AND {legacy} IS NOT NULL "
                    f"  AND {legacy} <> ''"
                )
                moved = cursor.rowcount
                if moved:
                    logger.info(
                        "Migration: copied %d row(s) %s.%s -> %s.%s",
                        moved, table, legacy, table, canonical,
                    )
            conn.commit()
        finally:
            conn.close()

    def _apply_column_defaults(self) -> None:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            for logical_table, defaults in TABLE_COLUMN_DEFAULTS.items():
                table = self._resolve_table(logical_table)
                if not self._table_exists(cursor, table):
                    continue
                cursor.execute(f"PRAGMA table_info({table})")
                existing = {row[1] for row in cursor.fetchall()}
                for column, default_value in defaults.items():
                    if column not in existing:
                        continue
                    cursor.execute(
                        f"UPDATE {table} SET {column} = ? "
                        f"WHERE {column} IS NULL OR {column} = ''",
                        (default_value,),
                    )
                    updated = cursor.rowcount
                    if updated:
                        logger.info(
                            "Migration: back-filled %d row(s) %s.%s = %r",
                            updated, table, column, default_value,
                        )
            conn.commit()
        finally:
            conn.close()

    def _record_schema_version(self) -> None:
        version = self._config.get_config("database.schema_version", "2")
        self.local_db.execute_query(
            """
            INSERT OR REPLACE INTO database_metadata
                (metadata_key, metadata_value, updated_at)
            VALUES ('schema_version', ?, CURRENT_TIMESTAMP)
            """,
            "default",
            params=(str(version),),
        )
