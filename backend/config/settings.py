"""
Application Settings Configuration

This module handles application-wide settings and configuration management,
following the Single Responsibility Principle (SRP) of SOLID.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class Environment(Enum):
    """Application environment enumeration."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class ArtifactorySettings:
    """Artifactory-specific settings."""
    base_url: str
    username: str
    password: str
    repository: str = "configs"
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    verify_ssl: bool = True
    api_version: str = "v1"


@dataclass
class DatabaseSettings:
    """Database-specific settings."""
    config_name: str
    environment: str
    auto_reload: bool = False
    cache_duration: int = 300  # seconds
    fallback_config_path: Optional[str] = None


@dataclass
class LoggingSettings:
    """Logging configuration settings."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    enable_console: bool = True


@dataclass
class ApplicationSettings:
    """Main application settings container."""
    environment: Environment
    artifactory: ArtifactorySettings
    database: DatabaseSettings
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 5000
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    mock_mode: bool = False
    mock_server_port: int = 8080
    
    @classmethod
    def from_environment(cls) -> 'ApplicationSettings':
        """Create settings from environment variables."""
        environment = Environment(os.getenv("ENVIRONMENT", "development"))
        debug = os.getenv("DEBUG", "false").lower() == "true"
        mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"
        
        # Artifactory settings
        artifactory = ArtifactorySettings(
            base_url=os.getenv("ARTIFACTORY_URL", "http://localhost:8080"),
            username=os.getenv("ARTIFACTORY_USERNAME", "admin"),
            password=os.getenv("ARTIFACTORY_PASSWORD", "password"),
            repository=os.getenv("ARTIFACTORY_REPOSITORY", "configs"),
            timeout=int(os.getenv("ARTIFACTORY_TIMEOUT", "30")),
            retry_attempts=int(os.getenv("ARTIFACTORY_RETRY_ATTEMPTS", "3")),
            retry_delay=float(os.getenv("ARTIFACTORY_RETRY_DELAY", "1.0")),
            verify_ssl=os.getenv("ARTIFACTORY_VERIFY_SSL", "true").lower() == "true",
            api_version=os.getenv("ARTIFACTORY_API_VERSION", "v1"),
        )
        
        # Database settings
        database = DatabaseSettings(
            config_name=os.getenv("DB_CONFIG_NAME", "main_db"),
            environment=os.getenv("DB_ENVIRONMENT", environment.value),
            auto_reload=os.getenv("DB_AUTO_RELOAD", "false").lower() == "true",
            cache_duration=int(os.getenv("DB_CACHE_DURATION", "300")),
            fallback_config_path=os.getenv("DB_FALLBACK_CONFIG_PATH"),
        )
        
        # Logging settings
        logging = LoggingSettings(
            level=os.getenv("LOG_LEVEL", "INFO"),
            format=os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            file_path=os.getenv("LOG_FILE_PATH"),
            max_file_size=int(os.getenv("LOG_MAX_FILE_SIZE", str(10 * 1024 * 1024))),
            backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
            enable_console=os.getenv("LOG_ENABLE_CONSOLE", "true").lower() == "true",
        )
        
        return cls(
            environment=environment,
            debug=debug,
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "5000")),
            artifactory=artifactory,
            database=database,
            logging=logging,
            mock_mode=mock_mode,
            mock_server_port=int(os.getenv("MOCK_SERVER_PORT", "8080")),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "environment": self.environment.value,
            "debug": self.debug,
            "host": self.host,
            "port": self.port,
            "artifactory": {
                "base_url": self.artifactory.base_url,
                "username": self.artifactory.username,
                "password": "***",  # Hide password
                "repository": self.artifactory.repository,
                "timeout": self.artifactory.timeout,
                "retry_attempts": self.artifactory.retry_attempts,
                "retry_delay": self.artifactory.retry_delay,
                "verify_ssl": self.artifactory.verify_ssl,
                "api_version": self.artifactory.api_version,
            },
            "database": {
                "config_name": self.database.config_name,
                "environment": self.database.environment,
                "auto_reload": self.database.auto_reload,
                "cache_duration": self.database.cache_duration,
                "fallback_config_path": self.database.fallback_config_path,
            },
            "logging": {
                "level": self.logging.level,
                "format": self.logging.format,
                "file_path": self.logging.file_path,
                "max_file_size": self.logging.max_file_size,
                "backup_count": self.logging.backup_count,
                "enable_console": self.logging.enable_console,
            },
            "mock_mode": self.mock_mode,
            "mock_server_port": self.mock_server_port,
        }


# Global settings instance
settings = ApplicationSettings.from_environment()
