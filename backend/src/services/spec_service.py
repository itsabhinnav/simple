import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from src.schemas.spec_schema import SpecCreateSchema, SpecUpdateSchema
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)

_SPEC_COLUMNS = (
    "id, spec_id, title, project, tags, category, version, status, "
    "file_url, file_name, source_url, created_by, created_at, updated_at"
)


class ISpecService(ABC):
    @abstractmethod
    def get_all_specs(self, search: Optional[str] = None, project: Optional[str] = None) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def get_projects(self) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def get_spec_by_id(self, spec_pk: int) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def get_spec_versions(self, spec_id: str, project: Optional[str] = None) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def create_spec(self, data: SpecCreateSchema) -> Dict[str, Any]: ...

    @abstractmethod
    def update_spec(self, spec_pk: int, data: SpecUpdateSchema) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def delete_spec(self, spec_pk: int) -> bool: ...


class SpecService(ISpecService):
    def __init__(self, database_service):
        self.database_service = database_service
        self._ensure_table()

    def _db_path(self) -> Path:
        if hasattr(self.database_service, "local_db"):
            return Path(self.database_service.local_db.local_db_path)
        return Path(getattr(self.database_service, "local_db_path", "data/local/dev/database/sakura_db.db"))

    def _ensure_table(self):
        ddl = (
            "CREATE TABLE IF NOT EXISTS specifications ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "spec_id TEXT, title TEXT, project TEXT, tags TEXT, category TEXT, version TEXT, status TEXT,"
            "file_url TEXT, file_name TEXT, source_url TEXT, created_by TEXT,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
        try:
            self.database_service.execute_query(ddl, "default")
        except Exception:
            pass
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        columns = {
            "tags": "TEXT",
            "file_name": "TEXT",
            "source_url": "TEXT",
            "project": "TEXT",
        }
        try:
            db_path = self._db_path()
            with sqlite3.connect(str(db_path)) as conn:
                existing = {row[1] for row in conn.execute("PRAGMA table_info(specifications)")}
                for col, col_type in columns.items():
                    if col not in existing:
                        conn.execute(f"ALTER TABLE specifications ADD COLUMN {col} {col_type}")
                conn.commit()
        except Exception as exc:
            logger.warning(f"Could not migrate specifications columns: {exc}")

    def get_all_specs(self, search: Optional[str] = None, project: Optional[str] = None) -> List[Dict[str, Any]]:
        query = f"SELECT {_SPEC_COLUMNS} FROM specifications WHERE 1=1"
        params: list = []
        if project and project.strip():
            if project.strip().lower() == "unassigned":
                query += " AND (project IS NULL OR trim(project) = '')"
            else:
                query += " AND lower(project) = lower(?)"
                params.append(project.strip())
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            query += """
                AND (
                    lower(spec_id) LIKE ?
                    OR lower(title) LIKE ?
                    OR lower(tags) LIKE ?
                    OR lower(category) LIKE ?
                    OR lower(project) LIKE ?
                )
            """
            params.extend([term, term, term, term, term])
        query += " ORDER BY project ASC, spec_id ASC, version DESC, created_at DESC"
        result = self.database_service.execute_query(query, "default", params=tuple(params))
        return result.get("data", [])

    def get_projects(self) -> List[Dict[str, Any]]:
        query = """
            SELECT
                COALESCE(NULLIF(trim(project), ''), 'Unassigned') AS project,
                COUNT(*) AS spec_count,
                COUNT(DISTINCT spec_id) AS spec_families,
                MAX(updated_at) AS last_updated
            FROM specifications
            GROUP BY COALESCE(NULLIF(trim(project), ''), 'Unassigned')
            ORDER BY project ASC
        """
        result = self.database_service.execute_query(query, "default")
        return result.get("data", [])

    def get_spec_by_id(self, spec_pk: int) -> Optional[Dict[str, Any]]:
        query = f"SELECT {_SPEC_COLUMNS} FROM specifications WHERE id = ?"
        result = self.database_service.execute_query(query, "default", params=(spec_pk,))
        rows = result.get("data", [])
        return rows[0] if rows else None

    def get_spec_versions(self, spec_id: str, project: Optional[str] = None) -> List[Dict[str, Any]]:
        query = f"SELECT {_SPEC_COLUMNS} FROM specifications WHERE spec_id = ?"
        params: list = [spec_id]
        if project and project.strip():
            if project.strip().lower() == "unassigned":
                query += " AND (project IS NULL OR trim(project) = '')"
            else:
                query += " AND lower(project) = lower(?)"
                params.append(project.strip())
        query += " ORDER BY version DESC, created_at DESC"
        result = self.database_service.execute_query(query, "default", params=tuple(params))
        return result.get("data", [])

    def create_spec(self, data: SpecCreateSchema) -> Dict[str, Any]:
        if self._find_by_identity(data.spec_id, data.project, data.version):
            logger.warning(
                f"Spec version already exists: {data.spec_id} / {data.project} / {data.version}"
            )
            return {
                "_error": "duplicate_version",
                "_message": "This spec version already exists for the project.",
            }

        query = """
            INSERT INTO specifications (
                spec_id, title, project, tags, category, version, status,
                file_url, file_name, source_url, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
        params = (
            data.spec_id,
            data.title,
            data.project or "",
            data.tags or "",
            data.category or "",
            data.version or "",
            data.status or "Draft",
            data.file_url or "",
            data.file_name or "",
            data.source_url or "",
        )
        result = self.database_service.execute_query(query, "default", params=params)
        if not result.get("success"):
            logger.error(f"Spec insert failed: {result.get('error')}")
            return {}
        row_id = result.get("lastrowid")
        if row_id:
            created = self.get_spec_by_id(int(row_id))
            if created:
                return created
        return self._find_by_identity(data.spec_id, data.project, data.version) or {}

    def update_spec(self, spec_pk: int, data: SpecUpdateSchema) -> Optional[Dict[str, Any]]:
        fields = []
        params: list = []
        for key, value in data.dict(exclude_unset=True).items():
            fields.append(f"{key} = ?")
            params.append(value if value is not None else "")
        if not fields:
            return self.get_spec_by_id(spec_pk)
        params.append(spec_pk)
        set_clause = ", ".join(fields) + ", updated_at = CURRENT_TIMESTAMP"
        query = f"UPDATE specifications SET {set_clause} WHERE id = ?"
        result = self.database_service.execute_query(query, "default", params=tuple(params))
        if not result.get("success"):
            return None
        return self.get_spec_by_id(spec_pk)

    def delete_spec(self, spec_pk: int) -> bool:
        query = "DELETE FROM specifications WHERE id = ?"
        self.database_service.execute_query(query, "default", params=(spec_pk,))
        return True

    def _find_by_identity(
        self, spec_id: str, project: Optional[str], version: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        query = f"""
            SELECT {_SPEC_COLUMNS}
            FROM specifications
            WHERE spec_id = ?
              AND COALESCE(project, '') = ?
              AND COALESCE(version, '') = ?
            ORDER BY id DESC
            LIMIT 1
        """
        result = self.database_service.execute_query(
            query, "default", params=(spec_id, project or "", version or "")
        )
        rows = result.get("data", [])
        return rows[0] if rows else None
