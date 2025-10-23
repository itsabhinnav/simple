"""
Custom Exception Classes

This module defines custom exceptions for the Artifactory integration,
providing clear error handling and debugging information.
"""

from typing import Optional, Dict, Any


class ArtifactoryError(Exception):
    """Base exception for all Artifactory-related errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ArtifactoryAuthenticationError(ArtifactoryError):
    """Exception raised when Artifactory authentication fails."""
    pass


class ArtifactoryConnectionError(ArtifactoryError):
    """Exception raised when connection to Artifactory fails."""
    pass


class ArtifactoryUploadError(ArtifactoryError):
    """Exception raised when artifact upload fails."""
    pass


class ArtifactoryDownloadError(ArtifactoryError):
    """Exception raised when artifact download fails."""
    pass


class ArtifactorySearchError(ArtifactoryError):
    """Exception raised when artifact search fails."""
    pass


class ArtifactoryDeleteError(ArtifactoryError):
    """Exception raised when artifact deletion fails."""
    pass


class ArtifactoryNotFoundError(ArtifactoryError):
    """Exception raised when requested artifact is not found."""
    pass


class ConfigError(Exception):
    """Base exception for all configuration-related errors."""
    
    def __init__(
        self, 
        message: str, 
        config_name: Optional[str] = None,
        config_type: Optional[str] = None,
        environment: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.config_name = config_name
        self.config_type = config_type
        self.environment = environment
        self.details = details or {}


class ConfigStorageError(ConfigError):
    """Exception raised when configuration storage fails."""
    pass


class ConfigRetrievalError(ConfigError):
    """Exception raised when configuration retrieval fails."""
    pass


class ConfigListError(ConfigError):
    """Exception raised when configuration listing fails."""
    pass


class ConfigDeleteError(ConfigError):
    """Exception raised when configuration deletion fails."""
    pass


class ConfigValidationError(ConfigError):
    """Exception raised when configuration validation fails."""
    pass


class ConfigNotFoundError(ConfigError):
    """Exception raised when requested configuration is not found."""
    pass


class DatabaseConfigError(Exception):
    """Base exception for database configuration errors."""
    
    def __init__(
        self, 
        message: str, 
        database_type: Optional[str] = None,
        environment: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.database_type = database_type
        self.environment = environment
        self.details = details or {}


class DatabaseConnectionError(DatabaseConfigError):
    """Exception raised when database connection fails."""
    pass


class DatabaseConfigValidationError(DatabaseConfigError):
    """Exception raised when database configuration validation fails."""
    pass


class MockServerError(Exception):
    """Exception raised by mock server operations."""
    
    def __init__(
        self, 
        message: str, 
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


# ============================================================================
# Version Control and Conflict Resolution Exceptions
# ============================================================================

class VersionControlError(Exception):
    """Base exception for all version control-related errors."""
    
    def __init__(
        self, 
        message: str, 
        database_name: Optional[str] = None,
        environment: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.database_name = database_name
        self.environment = environment
        self.details = details or {}


class ConflictResolutionError(Exception):
    """Exception raised when conflict resolution fails."""
    
    def __init__(
        self, 
        message: str, 
        conflict_id: Optional[str] = None,
        resolution_strategy: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.conflict_id = conflict_id
        self.resolution_strategy = resolution_strategy
        self.details = details or {}


class NotificationError(Exception):
    """Exception raised when notification operations fail."""
    
    def __init__(
        self, 
        message: str, 
        user_id: Optional[str] = None,
        notification_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.user_id = user_id
        self.notification_type = notification_type
        self.details = details or {}


class SessionError(Exception):
    """Exception raised when session management operations fail."""
    
    def __init__(
        self, 
        message: str, 
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.session_id = session_id
        self.user_id = user_id
        self.details = details or {}