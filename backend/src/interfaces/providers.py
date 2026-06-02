"""Provider interfaces for cross-cutting concerns.

The remote/Git storage layer was removed when the app moved to local-only
mode, so the storage-provider interfaces (IStorageProvider, IGitProvider,
IArtifactoryProvider, ICloudStorageProvider, StorageProviderType) have
been deleted with it. What remains are the still-used interfaces.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IDatabaseProvider(ABC):
    """Interface for database providers."""

    @abstractmethod
    def connect(self) -> bool: ...

    @abstractmethod
    def disconnect(self) -> bool: ...

    @abstractmethod
    def execute_query(self, query: str, params: Optional[Dict] = None) -> Dict[str, Any]: ...

    @abstractmethod
    def execute_transaction(self, queries: List[str]) -> bool: ...

    @abstractmethod
    def create_table(self, table_name: str, schema: Dict[str, str]) -> bool: ...

    @abstractmethod
    def drop_table(self, table_name: str) -> bool: ...

    @abstractmethod
    def table_exists(self, table_name: str) -> bool: ...

    @abstractmethod
    def get_table_schema(self, table_name: str) -> Dict[str, str]: ...

    @abstractmethod
    def backup_database(self, backup_path: str) -> bool: ...

    @abstractmethod
    def restore_database(self, backup_path: str) -> bool: ...


class IAuthenticationProvider(ABC):
    """Interface for authentication providers."""

    @abstractmethod
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]: ...

    @abstractmethod
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> bool: ...

    @abstractmethod
    def delete_user(self, user_id: str) -> bool: ...

    @abstractmethod
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def list_users(self) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def validate_password(self, password: str) -> bool: ...

    @abstractmethod
    def hash_password(self, password: str) -> str: ...

    @abstractmethod
    def verify_password(self, password: str, hashed_password: str) -> bool: ...


class IConfigurationProvider(ABC):
    """Interface for configuration providers."""

    @abstractmethod
    def get_config(self, key: str, default: Any = None) -> Any: ...

    @abstractmethod
    def set_config(self, key: str, value: Any) -> bool: ...

    @abstractmethod
    def get_all_configs(self) -> Dict[str, Any]: ...

    @abstractmethod
    def reload_config(self) -> bool: ...

    @abstractmethod
    def validate_config(self) -> bool: ...


class ILoggingProvider(ABC):
    """Interface for logging providers."""

    @abstractmethod
    def log(self, level: str, message: str, **kwargs) -> None: ...

    @abstractmethod
    def debug(self, message: str, **kwargs) -> None: ...

    @abstractmethod
    def info(self, message: str, **kwargs) -> None: ...

    @abstractmethod
    def warning(self, message: str, **kwargs) -> None: ...

    @abstractmethod
    def error(self, message: str, **kwargs) -> None: ...

    @abstractmethod
    def critical(self, message: str, **kwargs) -> None: ...

    @abstractmethod
    def set_level(self, level: str) -> None: ...

    @abstractmethod
    def add_handler(self, handler) -> None: ...

    @abstractmethod
    def remove_handler(self, handler) -> None: ...
