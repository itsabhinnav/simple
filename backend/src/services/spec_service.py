from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from src.schemas.spec_schema import SpecCreateSchema, SpecUpdateSchema
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class ISpecService(ABC):
    @abstractmethod
    def get_all_specs(self) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def get_spec_by_id(self, spec_pk: int) -> Optional[Dict[str, Any]]: ...

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

    def _ensure_table(self):
        ddl = (
            "CREATE TABLE IF NOT EXISTS specifications ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "spec_id TEXT, title TEXT, description TEXT, category TEXT, version TEXT, status TEXT,"
            "file_url TEXT, created_by TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
        try:
            self.database_service.execute_non_query(ddl, "default") if hasattr(self.database_service, 'execute_non_query') else self.database_service.execute_query(ddl, "default")
        except Exception:
            # Best-effort create; ignore if not supported
            pass

    def get_all_specs(self) -> List[Dict[str, Any]]:
        query = """
            SELECT id, spec_id, title, description, category, version, status, file_url,
                   created_by, created_at, updated_at
            FROM specifications
            ORDER BY created_at DESC
        """
        result = self.database_service.execute_query(query, "default")
        return result.get('data', [])

    def get_spec_by_id(self, spec_pk: int) -> Optional[Dict[str, Any]]:
        query = f"""
            SELECT id, spec_id, title, description, category, version, status, file_url,
                   created_by, created_at, updated_at
            FROM specifications WHERE id = {spec_pk}
        """
        result = self.database_service.execute_query(query, "default")
        rows = result.get('data', [])
        return rows[0] if rows else None

    def create_spec(self, data: SpecCreateSchema) -> Dict[str, Any]:
        title = data.title.replace("'", "''")
        spec_id = data.spec_id.replace("'", "''")
        description = (data.description or '').replace("'", "''")
        category = (data.category or '').replace("'", "''")
        version = (data.version or '').replace("'", "''")
        status = (data.status or '').replace("'", "''")
        file_url = (data.file_url or '').replace("'", "''")
        query = f"""
            INSERT INTO specifications (spec_id, title, description, category, version, status, file_url, created_at, updated_at)
            VALUES ('{spec_id}', '{title}', '{description}', '{category}', '{version}', '{status}', '{file_url}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id, spec_id, title, description, category, version, status, file_url, created_at, updated_at
        """
        result = self.database_service.execute_query(query, "default")
        rows = result.get('data', [])
        return rows[0] if rows else {}

    def update_spec(self, spec_pk: int, data: SpecUpdateSchema) -> Optional[Dict[str, Any]]:
        # Build dynamic update
        fields = []
        for key, value in data.dict(exclude_unset=True).items():
            safe = str(value).replace("'", "''") if value is not None else ''
            fields.append(f"{key} = '{safe}'")
        if not fields:
            return self.get_spec_by_id(spec_pk)
        set_clause = ", ".join(fields) + ", updated_at = CURRENT_TIMESTAMP"
        query = f"UPDATE specifications SET {set_clause} WHERE id = {spec_pk} RETURNING id, spec_id, title, description, category, version, status, file_url, created_at, updated_at"
        result = self.database_service.execute_query(query, "default")
        rows = result.get('data', [])
        return rows[0] if rows else None

    def delete_spec(self, spec_pk: int) -> bool:
        query = f"DELETE FROM specifications WHERE id = {spec_pk}"
        self.database_service.execute_query(query, "default")
        return True


