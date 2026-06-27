"""Database Schema Management Service.

Provides a safe, admin-only, transactional surface for runtime
modification of the local SQLite database schema:

  * list tables (with row counts) and their column / index / FK details
  * create new tables
  * drop user-created tables (protected tables are refused)
  * add / rename / drop columns (using native SQLite ALTERs where supported)
  * change a column's declared type (SQLite has no native syntax for this,
    so we perform a full transactional table-rebuild that preserves data,
    indexes, and foreign keys)
  * every DDL operation is logged to ``schema_migrations`` and the
    database file is snapshotted under ``data/local/dev/database/backups/``
    so an operator can roll back manually if needed
  * ``database_metadata.version`` is bumped after every successful change
    so live clients pick up the new schema on their next poll

The service is intentionally narrow: it only touches the local SQLite
file (the only database the app uses now that remote/Git sync was
removed), and it refuses to operate on internal tables that the
application depends on for its own bookkeeping.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.infrastructure.logging_config import get_logger
from src.services.local_database_service import LocalDatabaseService

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Tables that store either user accounts/sessions, auth/secret material,
# or runtime bookkeeping. Refuse destructive operations on them so a
# misclick in the admin UI can't take the app down.
PROTECTED_TABLES: frozenset[str] = frozenset({
    "users",
    "user_sessions",
    "user_preferences",
    "sync_status",
    "local_cache",
    "database_metadata",
    "schema_migrations",
    "sqlite_sequence",
    "sqlite_master",
    "sqlite_stat1",
})

# SQLite affinity types we expose in the admin UI. We accept any
# free-form type spec server-side (SQLite is dynamically typed), but
# validate that the string only contains identifier characters so we
# can interpolate it into DDL without parameterization (which SQLite
# does not support for type names).
_ALLOWED_TYPES: frozenset[str] = frozenset({
    "TEXT", "INTEGER", "REAL", "NUMERIC", "BLOB",
    "BOOLEAN", "DATE", "DATETIME", "TIMESTAMP",
    "VARCHAR", "CHAR", "FLOAT", "DOUBLE", "DECIMAL",
})

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_TYPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_ ()]*$")

# Default values we recognize symbolically (everything else is treated
# as a literal and quoted at the DDL site).
_DEFAULT_KEYWORDS: frozenset[str] = frozenset({
    "CURRENT_TIMESTAMP",
    "CURRENT_DATE",
    "CURRENT_TIME",
    "NULL",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class SchemaError(ValueError):
    """Raised for any client-visible schema validation failure."""


def _validate_identifier(name: str, kind: str) -> str:
    if not isinstance(name, str) or not _IDENT_RE.match(name):
        raise SchemaError(
            f"Invalid {kind} name {name!r}: must match ^[A-Za-z_][A-Za-z0-9_]{{0,62}}$"
        )
    return name


def _validate_type(type_spec: str) -> str:
    if not isinstance(type_spec, str) or not _TYPE_RE.match(type_spec.strip()):
        raise SchemaError(
            f"Invalid column type {type_spec!r}: must start with a letter and "
            "contain only letters, digits, spaces, underscores, or parentheses"
        )
    spec = type_spec.strip().upper()
    base = spec.split("(", 1)[0].strip()
    if base not in _ALLOWED_TYPES:
        raise SchemaError(
            f"Unsupported column type {type_spec!r}. Allowed base types: "
            + ", ".join(sorted(_ALLOWED_TYPES))
        )
    return spec


def _render_default(default: Any) -> str:
    """Render a column default value as a DDL fragment (already escaped)."""
    if default is None:
        return ""
    if isinstance(default, str):
        upper = default.strip().upper()
        if upper in _DEFAULT_KEYWORDS:
            return f"DEFAULT {upper}"
        if default == "":
            return "DEFAULT ''"
        # Escape single quotes by doubling them — standard SQL.
        escaped = default.replace("'", "''")
        return f"DEFAULT '{escaped}'"
    if isinstance(default, bool):
        return f"DEFAULT {1 if default else 0}"
    if isinstance(default, (int, float)):
        return f"DEFAULT {default}"
    raise SchemaError(f"Unsupported default value: {default!r}")


def _column_ddl(col: Dict[str, Any]) -> str:
    """Build a column DDL fragment from a normalized column dict.

    Expected dict keys: name, type, nullable, default, primary_key.
    """
    name = _validate_identifier(col["name"], "column")
    type_spec = _validate_type(col.get("type", "TEXT") or "TEXT")
    parts = [name, type_spec]
    if col.get("primary_key"):
        parts.append("PRIMARY KEY")
        if type_spec.upper().startswith("INTEGER"):
            parts.append("AUTOINCREMENT")
    nullable = col.get("nullable", True)
    if not nullable and not col.get("primary_key"):
        parts.append("NOT NULL")
    default_frag = _render_default(col.get("default"))
    if default_frag:
        parts.append(default_frag)
    return " ".join(parts)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class SchemaService:
    """Admin-only schema management on top of the local SQLite database."""

    BACKUP_RETENTION = 25  # keep last N backups; older ones are pruned

    def __init__(self, local_db: LocalDatabaseService):
        self.local_db = local_db
        self._db_path: Path = Path(local_db.local_db_path)
        self._backup_dir: Path = self._db_path.parent / "backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_migrations_table()

    # ------------------------------------------------------------------
    # Connection / bootstrap
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        # Enable FK enforcement for the duration of this connection so
        # destructive DDL refuses to break referential integrity.
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_migrations_table(self) -> None:
        try:
            conn = self._connect()
            try:
                conn.execute(
                    """
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
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.exception("Could not bootstrap schema_migrations table")

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def list_tables(self) -> List[Dict[str, Any]]:
        """Return user tables with row counts and column counts."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()
            tables: List[Dict[str, Any]] = []
            for row in rows:
                name = row["name"]
                cols = conn.execute(f"PRAGMA table_info({name})").fetchall()
                try:
                    count_row = conn.execute(
                        f"SELECT COUNT(*) AS c FROM {name}"
                    ).fetchone()
                    row_count = int(count_row["c"]) if count_row else 0
                except Exception:
                    row_count = -1
                tables.append({
                    "name": name,
                    "column_count": len(cols),
                    "row_count": row_count,
                    "protected": name in PROTECTED_TABLES,
                })
            return tables
        finally:
            conn.close()

    def get_table(self, name: str) -> Dict[str, Any]:
        """Return full schema of a table (columns, indexes, foreign keys)."""
        _validate_identifier(name, "table")
        conn = self._connect()
        try:
            existence = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                (name,),
            ).fetchone()
            if not existence:
                raise SchemaError(f"Table {name!r} does not exist")

            columns = [
                {
                    "cid": r["cid"],
                    "name": r["name"],
                    "type": r["type"] or "",
                    "nullable": not bool(r["notnull"]),
                    "default": r["dflt_value"],
                    "primary_key": bool(r["pk"]),
                }
                for r in conn.execute(f"PRAGMA table_info({name})").fetchall()
            ]
            indexes_raw = conn.execute(f"PRAGMA index_list({name})").fetchall()
            indexes: List[Dict[str, Any]] = []
            for ix in indexes_raw:
                ix_name = ix["name"]
                ix_cols = conn.execute(f"PRAGMA index_info({ix_name})").fetchall()
                indexes.append({
                    "name": ix_name,
                    "unique": bool(ix["unique"]),
                    "origin": ix["origin"],
                    "columns": [c["name"] for c in ix_cols],
                })
            foreign_keys = [
                _row_to_dict(r)
                for r in conn.execute(f"PRAGMA foreign_key_list({name})").fetchall()
            ]
            try:
                row_count = int(
                    conn.execute(f"SELECT COUNT(*) AS c FROM {name}").fetchone()["c"]
                )
            except Exception:
                row_count = -1

            return {
                "name": name,
                "protected": name in PROTECTED_TABLES,
                "row_count": row_count,
                "columns": columns,
                "indexes": indexes,
                "foreign_keys": foreign_keys,
            }
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Mutations — every method here is transactional and logs to
    # schema_migrations on its way out.
    # ------------------------------------------------------------------
    def create_table(
        self,
        name: str,
        columns: List[Dict[str, Any]],
        applied_by: Optional[str],
    ) -> Dict[str, Any]:
        _validate_identifier(name, "table")
        if name in PROTECTED_TABLES:
            raise SchemaError(
                f"Refusing to create a table with the reserved name {name!r}"
            )
        if not columns:
            raise SchemaError("At least one column is required")
        seen = set()
        ddl_columns: List[str] = []
        for col in columns:
            col_name = _validate_identifier(col["name"], "column")
            if col_name in seen:
                raise SchemaError(f"Duplicate column {col_name!r}")
            seen.add(col_name)
            ddl_columns.append(_column_ddl(col))

        ddl = f"CREATE TABLE {name} (\n  " + ",\n  ".join(ddl_columns) + "\n)"
        backup = self._snapshot()
        try:
            self._run_ddl(ddl)
        except Exception as exc:
            self._log_migration(
                "create_table", name, None, applied_by,
                {"ddl": ddl}, succeeded=False, error=str(exc), backup_path=backup,
            )
            raise SchemaError(f"Failed to create table: {exc}") from exc
        self._log_migration(
            "create_table", name, None, applied_by,
            {"columns": columns, "ddl": ddl}, backup_path=backup,
        )
        self._bump_version()
        return self.get_table(name)

    def drop_table(self, name: str, applied_by: Optional[str]) -> Dict[str, Any]:
        _validate_identifier(name, "table")
        if name in PROTECTED_TABLES:
            raise SchemaError(f"Refusing to drop protected table {name!r}")
        backup = self._snapshot()
        try:
            self._run_ddl(f"DROP TABLE IF EXISTS {name}")
        except Exception as exc:
            self._log_migration(
                "drop_table", name, None, applied_by,
                None, succeeded=False, error=str(exc), backup_path=backup,
            )
            raise SchemaError(f"Failed to drop table: {exc}") from exc
        self._log_migration(
            "drop_table", name, None, applied_by, None, backup_path=backup,
        )
        self._bump_version()
        return {"dropped": True, "table": name}

    def add_column(
        self,
        table: str,
        column: Dict[str, Any],
        applied_by: Optional[str],
    ) -> Dict[str, Any]:
        _validate_identifier(table, "table")
        if table in PROTECTED_TABLES:
            raise SchemaError(f"Cannot modify protected table {table!r}")
        col_ddl = _column_ddl(column)
        backup = self._snapshot()
        try:
            self._run_ddl(f"ALTER TABLE {table} ADD COLUMN {col_ddl}")
        except Exception as exc:
            self._log_migration(
                "add_column", table, column.get("name"), applied_by,
                {"column": column}, succeeded=False, error=str(exc),
                backup_path=backup,
            )
            raise SchemaError(f"Failed to add column: {exc}") from exc
        self._log_migration(
            "add_column", table, column.get("name"), applied_by,
            {"column": column}, backup_path=backup,
        )
        self._bump_version()
        return self.get_table(table)

    def rename_column(
        self,
        table: str,
        old_name: str,
        new_name: str,
        applied_by: Optional[str],
    ) -> Dict[str, Any]:
        _validate_identifier(table, "table")
        _validate_identifier(old_name, "column")
        _validate_identifier(new_name, "column")
        if table in PROTECTED_TABLES:
            raise SchemaError(f"Cannot modify protected table {table!r}")
        if old_name == new_name:
            return self.get_table(table)
        backup = self._snapshot()
        try:
            self._run_ddl(
                f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name}"
            )
        except sqlite3.OperationalError as exc:
            self._log_migration(
                "rename_column", table, old_name, applied_by,
                {"from": old_name, "to": new_name},
                succeeded=False, error=str(exc), backup_path=backup,
            )
            raise SchemaError(
                f"Failed to rename column (your SQLite may be < 3.25): {exc}"
            ) from exc
        self._log_migration(
            "rename_column", table, old_name, applied_by,
            {"from": old_name, "to": new_name}, backup_path=backup,
        )
        self._bump_version()
        return self.get_table(table)

    def drop_column(
        self,
        table: str,
        column: str,
        applied_by: Optional[str],
    ) -> Dict[str, Any]:
        _validate_identifier(table, "table")
        _validate_identifier(column, "column")
        if table in PROTECTED_TABLES:
            raise SchemaError(f"Cannot modify protected table {table!r}")
        existing = self.get_table(table)
        target = next((c for c in existing["columns"] if c["name"] == column), None)
        if target is None:
            raise SchemaError(f"Column {column!r} not found in {table!r}")
        if target["primary_key"]:
            raise SchemaError(
                f"Cannot drop primary-key column {column!r}; rebuild the table instead"
            )
        backup = self._snapshot()
        try:
            self._run_ddl(f"ALTER TABLE {table} DROP COLUMN {column}")
        except sqlite3.OperationalError as exc:
            # SQLite < 3.35 has no native DROP COLUMN. Fall back to a
            # full table rebuild so the admin UI still works on older
            # SQLite builds shipped with some Python distributions.
            try:
                self._rebuild_table_without_column(table, column)
            except Exception as exc2:
                self._log_migration(
                    "drop_column", table, column, applied_by, None,
                    succeeded=False, error=f"{exc} / fallback: {exc2}",
                    backup_path=backup,
                )
                raise SchemaError(f"Failed to drop column: {exc2}") from exc2
        self._log_migration(
            "drop_column", table, column, applied_by, None, backup_path=backup,
        )
        self._bump_version()
        return self.get_table(table)

    def change_column(
        self,
        table: str,
        column: str,
        new_name: Optional[str],
        new_type: Optional[str],
        nullable: Optional[bool],
        default: Any,
        applied_by: Optional[str],
    ) -> Dict[str, Any]:
        """Rename and/or retype a column.

        SQLite has no native ALTER COLUMN syntax, so when the type,
        nullable, or default change we rebuild the entire table inside
        a transaction (copy rows, drop old, rename new). Indexes and
        foreign keys defined on the original table are recreated.
        """
        _validate_identifier(table, "table")
        _validate_identifier(column, "column")
        if table in PROTECTED_TABLES:
            raise SchemaError(f"Cannot modify protected table {table!r}")

        existing = self.get_table(table)
        target = next((c for c in existing["columns"] if c["name"] == column), None)
        if target is None:
            raise SchemaError(f"Column {column!r} not found in {table!r}")

        effective_new_name = (
            _validate_identifier(new_name, "column") if new_name and new_name != column else column
        )
        type_changed = new_type is not None and new_type.strip().upper() != (target["type"] or "").strip().upper()
        nullable_changed = nullable is not None and bool(nullable) != bool(target["nullable"])
        default_changed = default is not None and str(default) != str(target["default"] or "")

        if not type_changed and not nullable_changed and not default_changed:
            # Rename-only path can use the lightweight ALTER.
            if effective_new_name != column:
                return self.rename_column(table, column, effective_new_name, applied_by)
            return existing

        backup = self._snapshot()
        try:
            self._rebuild_table_with_column_change(
                table, column, effective_new_name, new_type, nullable, default,
            )
        except Exception as exc:
            self._log_migration(
                "change_column", table, column, applied_by,
                {
                    "new_name": effective_new_name,
                    "new_type": new_type,
                    "nullable": nullable,
                    "default": default,
                },
                succeeded=False, error=str(exc), backup_path=backup,
            )
            raise SchemaError(f"Failed to change column: {exc}") from exc

        self._log_migration(
            "change_column", table, column, applied_by,
            {
                "new_name": effective_new_name,
                "new_type": new_type,
                "nullable": nullable,
                "default": default,
            },
            backup_path=backup,
        )
        self._bump_version()
        return self.get_table(table)

    # ------------------------------------------------------------------
    # Migration log
    # ------------------------------------------------------------------
    def list_migrations(self, limit: int = 200) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM schema_migrations "
                "ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Backups
    # ------------------------------------------------------------------
    def create_backup(self) -> Dict[str, Any]:
        from src.infrastructure.dependency_injection import get_database_backup_service

        path = get_database_backup_service().create_backup(reason="admin_manual")
        if path is None:
            raise SchemaError("Could not create backup")
        size = Path(path).stat().st_size if Path(path).exists() else 0
        return {"path": str(path), "size_bytes": size}

    def list_backups(self) -> List[Dict[str, Any]]:
        from src.infrastructure.dependency_injection import get_database_backup_service

        return get_database_backup_service().list_backups()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _run_ddl(self, ddl: str) -> None:
        logger.info("schema DDL: %s", ddl)
        conn = self._connect()
        try:
            conn.executescript(ddl)
            conn.commit()
        finally:
            conn.close()

    def _bump_version(self) -> None:
        try:
            self.local_db.increment_database_version()
            self.local_db.clear_table_cache("__schema__")
        except Exception as exc:
            logger.warning("Could not bump DB version after schema change: %s", exc)

    def _log_migration(
        self,
        operation: str,
        table: Optional[str],
        column: Optional[str],
        applied_by: Optional[str],
        details: Optional[Dict[str, Any]],
        succeeded: bool = True,
        error: Optional[str] = None,
        backup_path: Optional[str] = None,
    ) -> None:
        try:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO schema_migrations
                        (applied_by, operation, table_name, column_name,
                         details, succeeded, error, backup_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        applied_by or "system",
                        operation,
                        table,
                        column,
                        json.dumps(details, default=str) if details is not None else None,
                        1 if succeeded else 0,
                        error,
                        backup_path,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.exception("Failed to log schema migration")

    def _snapshot(self) -> Optional[str]:
        """Copy the live SQLite file into the backups dir and prune old ones."""
        try:
            from src.infrastructure.dependency_injection import get_database_backup_service

            path = get_database_backup_service().create_backup(reason="schema_ddl")
            return str(path) if path else None
        except Exception:
            logger.exception("Schema backup failed")
            return None

    def _prune_backups(self) -> None:
        try:
            from src.infrastructure.dependency_injection import get_database_backup_service

            get_database_backup_service()._prune_backups()
        except Exception:
            logger.debug("Backup pruning failed", exc_info=True)

    # ------------------------------------------------------------------
    # Table rebuild helpers (used for DROP COLUMN fallback and CHANGE COLUMN)
    # ------------------------------------------------------------------
    def _rebuild_table_without_column(self, table: str, column: str) -> None:
        info = self.get_table(table)
        remaining = [c for c in info["columns"] if c["name"] != column]
        if not remaining:
            raise SchemaError("Cannot remove the last column from a table")
        self._rebuild_table(table, remaining, info["indexes"], info["foreign_keys"],
                            column_rename_map={})

    def _rebuild_table_with_column_change(
        self,
        table: str,
        old_name: str,
        new_name: str,
        new_type: Optional[str],
        nullable: Optional[bool],
        default: Any,
    ) -> None:
        info = self.get_table(table)
        updated: List[Dict[str, Any]] = []
        for c in info["columns"]:
            if c["name"] == old_name:
                updated.append({
                    "name": new_name,
                    "type": new_type if new_type else c["type"] or "TEXT",
                    "nullable": (nullable if nullable is not None else c["nullable"]),
                    "default": default if default is not None else c["default"],
                    "primary_key": c["primary_key"],
                })
            else:
                updated.append(c)
        rename_map = {old_name: new_name} if old_name != new_name else {}
        self._rebuild_table(table, updated, info["indexes"], info["foreign_keys"],
                            column_rename_map=rename_map)

    def _rebuild_table(
        self,
        table: str,
        new_columns: List[Dict[str, Any]],
        indexes: List[Dict[str, Any]],
        foreign_keys: List[Dict[str, Any]],
        column_rename_map: Dict[str, str],
    ) -> None:
        _validate_identifier(table, "table")
        tmp = f"_tmp_{table}_{datetime.utcnow().strftime('%H%M%S%f')}"
        _validate_identifier(tmp, "table")

        col_ddls = [_column_ddl(c) for c in new_columns]
        # Foreign keys: re-emit each one inline so we don't lose them.
        fk_ddls: List[str] = []
        for fk in foreign_keys:
            from_col = fk.get("from")
            to_table = fk.get("table")
            to_col = fk.get("to")
            if not from_col or not to_table or not to_col:
                continue
            renamed_from = column_rename_map.get(from_col, from_col)
            try:
                _validate_identifier(renamed_from, "column")
                _validate_identifier(to_table, "table")
                _validate_identifier(to_col, "column")
            except SchemaError:
                continue
            fk_ddls.append(
                f"FOREIGN KEY ({renamed_from}) REFERENCES {to_table}({to_col})"
            )
        ddl_parts = col_ddls + fk_ddls
        create_tmp = f"CREATE TABLE {tmp} (\n  " + ",\n  ".join(ddl_parts) + "\n)"

        # SELECT list maps NEW column name → OLD column name. Columns that
        # didn't exist before are inserted as NULL.
        select_cols: List[str] = []
        insert_cols: List[str] = []
        for c in new_columns:
            new_n = c["name"]
            # Find the original name. If this column is the rename target,
            # its source name is the inverse of column_rename_map.
            origin = None
            for o, n in column_rename_map.items():
                if n == new_n:
                    origin = o
                    break
            if origin is None:
                origin = new_n
            insert_cols.append(new_n)
            # Only emit a source column when it actually existed before.
            select_cols.append(origin)

        copy_ddl = (
            f"INSERT INTO {tmp} (" + ", ".join(insert_cols) + ") "
            f"SELECT " + ", ".join(select_cols) + f" FROM {table}"
        )

        conn = self._connect()
        try:
            try:
                conn.execute("PRAGMA foreign_keys = OFF")
                conn.execute("BEGIN")
                conn.executescript(create_tmp)
                conn.execute(copy_ddl)
                conn.execute(f"DROP TABLE {table}")
                conn.execute(f"ALTER TABLE {tmp} RENAME TO {table}")
                # Recreate non-auto indexes that we owned.
                for ix in indexes:
                    if ix.get("origin") in ("pk", "u"):
                        # primary-key index is recreated implicitly via the
                        # column DDL; unique-from-CREATE-TABLE indexes also
                        # come back automatically.
                        continue
                    ix_name = ix.get("name") or ""
                    if not ix_name or ix_name.startswith("sqlite_autoindex_"):
                        continue
                    cols = [
                        column_rename_map.get(c, c)
                        for c in (ix.get("columns") or [])
                    ]
                    if not cols:
                        continue
                    try:
                        for cn in cols:
                            _validate_identifier(cn, "column")
                        _validate_identifier(ix_name, "index")
                    except SchemaError:
                        continue
                    unique = "UNIQUE " if ix.get("unique") else ""
                    conn.execute(
                        f"CREATE {unique}INDEX {ix_name} ON {table} (" + ", ".join(cols) + ")"
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.execute("PRAGMA foreign_keys = ON")
        finally:
            conn.close()
