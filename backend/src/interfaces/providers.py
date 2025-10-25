"""
Storage Provider Interfaces

This module defines interfaces for different storage providers,
making the system easily extensible to support GitLab, GitHub, Artifactory, etc.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, BinaryIO
from pathlib import Path
from enum import Enum


class StorageProviderType(Enum):
    """Types of storage providers"""
    GIT = "git"
    ARTIFACTORY = "artifactory"
    GITHUB = "github"
    GITLAB = "gitlab"
    LOCAL = "local"
    S3 = "s3"
    AZURE_BLOB = "azure_blob"


class IStorageProvider(ABC):
    """Base interface for all storage providers"""
    
    @abstractmethod
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate with the storage provider"""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the storage provider is healthy"""
        pass
    
    @abstractmethod
    def list_files(self, pattern: str = "*") -> List[str]:
        """List files in the storage"""
        pass
    
    @abstractmethod
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists"""
        pass
    
    @abstractmethod
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get file information"""
        pass
    
    @abstractmethod
    def download_file(self, file_path: str, local_path: str) -> bool:
        """Download file to local path"""
        pass
    
    @abstractmethod
    def upload_file(self, local_path: str, file_path: str) -> bool:
        """Upload file from local path"""
        pass
    
    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        """Delete file"""
        pass
    
    @abstractmethod
    def get_provider_type(self) -> StorageProviderType:
        """Get the provider type"""
        pass


class IGitProvider(IStorageProvider):
    """Interface for Git-based storage providers"""
    
    @abstractmethod
    def clone_or_fetch_repo(self) -> bool:
        """Clone repository if not exists, or fetch latest changes if exists"""
        pass
    
    @abstractmethod
    def push_changes(self, commit_message: str = "Update files") -> bool:
        """Push local changes to remote repository"""
        pass
    
    @abstractmethod
    def get_repo_status(self) -> Dict[str, Any]:
        """Get repository status information"""
        pass
    
    @abstractmethod
    def create_branch(self, branch_name: str) -> bool:
        """Create a new branch"""
        pass
    
    @abstractmethod
    def switch_branch(self, branch_name: str) -> bool:
        """Switch to a different branch"""
        pass
    
    @abstractmethod
    def merge_branch(self, source_branch: str, target_branch: str) -> bool:
        """Merge branches"""
        pass


class IArtifactoryProvider(IStorageProvider):
    """Interface for Artifactory storage provider"""
    
    @abstractmethod
    def get_repository_info(self) -> Dict[str, Any]:
        """Get repository information"""
        pass
    
    @abstractmethod
    def search_artifacts(self, query: str) -> List[Dict[str, Any]]:
        """Search for artifacts"""
        pass
    
    @abstractmethod
    def get_artifact_properties(self, file_path: str) -> Dict[str, Any]:
        """Get artifact properties"""
        pass
    
    @abstractmethod
    def set_artifact_properties(self, file_path: str, properties: Dict[str, str]) -> bool:
        """Set artifact properties"""
        pass
    
    @abstractmethod
    def promote_artifact(self, file_path: str, target_repo: str) -> bool:
        """Promote artifact to target repository"""
        pass


class ICloudStorageProvider(IStorageProvider):
    """Interface for cloud storage providers (S3, Azure Blob, etc.)"""
    
    @abstractmethod
    def create_bucket(self, bucket_name: str) -> bool:
        """Create a new bucket/container"""
        pass
    
    @abstractmethod
    def delete_bucket(self, bucket_name: str) -> bool:
        """Delete a bucket/container"""
        pass
    
    @abstractmethod
    def list_buckets(self) -> List[str]:
        """List all buckets/containers"""
        pass
    
    @abstractmethod
    def get_bucket_info(self, bucket_name: str) -> Dict[str, Any]:
        """Get bucket information"""
        pass
    
    @abstractmethod
    def set_file_metadata(self, file_path: str, metadata: Dict[str, str]) -> bool:
        """Set file metadata"""
        pass
    
    @abstractmethod
    def get_file_metadata(self, file_path: str) -> Dict[str, str]:
        """Get file metadata"""
        pass


class IDatabaseProvider(ABC):
    """Interface for database providers"""
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to database"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from database"""
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a query"""
        pass
    
    @abstractmethod
    def execute_transaction(self, queries: List[str]) -> bool:
        """Execute multiple queries in a transaction"""
        pass
    
    @abstractmethod
    def create_table(self, table_name: str, schema: Dict[str, str]) -> bool:
        """Create a table"""
        pass
    
    @abstractmethod
    def drop_table(self, table_name: str) -> bool:
        """Drop a table"""
        pass
    
    @abstractmethod
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists"""
        pass
    
    @abstractmethod
    def get_table_schema(self, table_name: str) -> Dict[str, str]:
        """Get table schema"""
        pass
    
    @abstractmethod
    def backup_database(self, backup_path: str) -> bool:
        """Backup database"""
        pass
    
    @abstractmethod
    def restore_database(self, backup_path: str) -> bool:
        """Restore database from backup"""
        pass


class IAuthenticationProvider(ABC):
    """Interface for authentication providers"""
    
    @abstractmethod
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate a user"""
        pass
    
    @abstractmethod
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user"""
        pass
    
    @abstractmethod
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """Update user data"""
        pass
    
    @abstractmethod
    def delete_user(self, user_id: str) -> bool:
        """Delete a user"""
        pass
    
    @abstractmethod
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        pass
    
    @abstractmethod
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        pass
    
    @abstractmethod
    def list_users(self) -> List[Dict[str, Any]]:
        """List all users"""
        pass
    
    @abstractmethod
    def validate_password(self, password: str) -> bool:
        """Validate password strength"""
        pass
    
    @abstractmethod
    def hash_password(self, password: str) -> str:
        """Hash password"""
        pass
    
    @abstractmethod
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        pass


class IConfigurationProvider(ABC):
    """Interface for configuration providers"""
    
    @abstractmethod
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        pass
    
    @abstractmethod
    def set_config(self, key: str, value: Any) -> bool:
        """Set configuration value"""
        pass
    
    @abstractmethod
    def get_all_configs(self) -> Dict[str, Any]:
        """Get all configuration values"""
        pass
    
    @abstractmethod
    def reload_config(self) -> bool:
        """Reload configuration from source"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate configuration"""
        pass


class ILoggingProvider(ABC):
    """Interface for logging providers"""
    
    @abstractmethod
    def log(self, level: str, message: str, **kwargs) -> None:
        """Log a message"""
        pass
    
    @abstractmethod
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message"""
        pass
    
    @abstractmethod
    def info(self, message: str, **kwargs) -> None:
        """Log info message"""
        pass
    
    @abstractmethod
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message"""
        pass
    
    @abstractmethod
    def error(self, message: str, **kwargs) -> None:
        """Log error message"""
        pass
    
    @abstractmethod
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message"""
        pass
    
    @abstractmethod
    def set_level(self, level: str) -> None:
        """Set logging level"""
        pass
    
    @abstractmethod
    def add_handler(self, handler) -> None:
        """Add logging handler"""
        pass
    
    @abstractmethod
    def remove_handler(self, handler) -> None:
        """Remove logging handler"""
        pass
