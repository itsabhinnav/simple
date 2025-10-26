"""
Environment-specific configuration files

This module defines configuration classes for different environments,
making the system easily extensible and configurable.
"""

import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class StorageProvider(Enum):
    """Supported storage providers"""
    GIT = "git"
    ARTIFACTORY = "artifactory"
    GITHUB = "github"
    GITLAB = "gitlab"
    LOCAL = "local"


class DatabaseProvider(Enum):
    """Supported database providers"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    provider: DatabaseProvider
    name: str
    host: str = "localhost"
    port: int = 5432
    username: str = ""
    password: str = ""
    schema: str = "public"
    connection_pool_size: int = 10
    connection_timeout: int = 30
    ssl_enabled: bool = False
    ssl_cert_path: Optional[str] = None
    
    # Table configurations
    table_names: Dict[str, str] = field(default_factory=lambda: {
        "users": "users",
        "test_cases": "test_cases", 
        "requirements": "requirements"
    })
    
    # File paths for SQLite
    data_directory: str = "data"
    cache_directory: str = "data/cache"
    
    def get_connection_string(self) -> str:
        """Get database connection string based on provider"""
        if self.provider == DatabaseProvider.SQLITE:
            return f"sqlite:///{self.name}"
        elif self.provider == DatabaseProvider.POSTGRESQL:
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"
        elif self.provider == DatabaseProvider.MYSQL:
            return f"mysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"
        else:
            raise ValueError(f"Unsupported database provider: {self.provider}")


@dataclass
class StorageConfig:
    """Storage configuration settings"""
    provider: StorageProvider
    base_url: str
    username: str
    password: str
    repository: str
    branch: str = "main"
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    verify_ssl: bool = True
    api_version: str = "v1"
    
    # Local paths
    local_repo_path: str = "remote"
    data_path: str = "data"
    
    # Git-specific settings
    git_username: Optional[str] = None
    git_token: Optional[str] = None
    
    # Artifactory-specific settings
    artifactory_repo_type: str = "generic-local"
    
    def get_repo_url(self) -> str:
        """Get repository URL based on provider"""
        if self.provider == StorageProvider.GITLAB:
            return f"https://gitlab.com/{self.repository}"
        elif self.provider == StorageProvider.GITHUB:
            return f"https://github.com/{self.repository}"
        elif self.provider == StorageProvider.GIT:
            return self.base_url
        else:
            return self.base_url


@dataclass
class AuthenticationConfig:
    """Authentication configuration settings"""
    # Default admin credentials
    default_admin_username: str = "admin"
    default_admin_password: str = "password"
    default_admin_email: str = "admin@sakura.com"
    
    # Authentication settings
    session_timeout: int = 3600  # 1 hour
    max_login_attempts: int = 5
    lockout_duration: int = 900  # 15 minutes
    
    # Reserved usernames that cannot be used
    reserved_usernames: List[str] = field(default_factory=lambda: [
        "admin", "root", "system", "administrator", "sa"
    ])
    
    # Password requirements
    min_password_length: int = 8
    require_special_chars: bool = True
    require_numbers: bool = True
    require_uppercase: bool = True


@dataclass
class ServerConfig:
    """Server configuration settings"""
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False
    mock_mode: bool = False
    mock_server_port: int = 8080
    
    # CORS settings
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    cors_methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    cors_headers: List[str] = field(default_factory=lambda: ["Content-Type", "Authorization"])
    
    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # 1 hour


@dataclass
class LoggingConfig:
    """Logging configuration settings"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    enable_console: bool = True
    enable_file: bool = False
    
    # Structured logging
    structured_logging: bool = False
    log_json: bool = False


@dataclass
class ApplicationConfig:
    """Main application configuration container"""
    environment: str
    database: DatabaseConfig
    storage: StorageConfig
    authentication: AuthenticationConfig
    server: ServerConfig
    logging: LoggingConfig
    
    # Feature flags
    features: Dict[str, bool] = field(default_factory=lambda: {
        "user_management": True,
        "test_case_management": True,
        "requirement_management": True,
        "git_integration": True,
        "artifactory_integration": False,
        "advanced_logging": False
    })
    
    @classmethod
    def from_environment(cls, env: str = None) -> 'ApplicationConfig':
        """Create configuration from environment variables"""
        if env is None:
            env = os.getenv("ENVIRONMENT", "development")
        
        # Database configuration
        database = DatabaseConfig(
            provider=DatabaseProvider(os.getenv("DB_PROVIDER", "sqlite")),
            name=os.getenv("DB_NAME", "sakura_db"),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            username=os.getenv("DB_USERNAME", ""),
            password=os.getenv("DB_PASSWORD", ""),
            schema=os.getenv("DB_SCHEMA", "public"),
            connection_pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            connection_timeout=int(os.getenv("DB_TIMEOUT", "30")),
            ssl_enabled=os.getenv("DB_SSL", "false").lower() == "true",
            ssl_cert_path=os.getenv("DB_SSL_CERT_PATH"),
            data_directory=os.getenv("DB_DATA_DIR", "data"),
            cache_directory=os.getenv("DB_CACHE_DIR", "data/cache"),
            table_names={
                "users": os.getenv("DB_TABLE_USERS", "users"),
                "test_cases": os.getenv("DB_TABLE_TEST_CASES", "test_cases"),
                "requirements": os.getenv("DB_TABLE_REQUIREMENTS", "requirements")
            }
        )
        
        # Storage configuration
        storage = StorageConfig(
            provider=StorageProvider(os.getenv("STORAGE_PROVIDER", "git")),
            base_url=os.getenv("STORAGE_BASE_URL", "https://gitlab.com/android-devops/sakura-db"),
            username=os.getenv("STORAGE_USERNAME", "admin"),
            password=os.getenv("STORAGE_PASSWORD", "password"),
            repository=os.getenv("STORAGE_REPOSITORY", "android-devops/sakura-db"),
            branch=os.getenv("STORAGE_BRANCH", "main"),
            timeout=int(os.getenv("STORAGE_TIMEOUT", "30")),
            retry_attempts=int(os.getenv("STORAGE_RETRY_ATTEMPTS", "3")),
            retry_delay=float(os.getenv("STORAGE_RETRY_DELAY", "1.0")),
            verify_ssl=os.getenv("STORAGE_VERIFY_SSL", "true").lower() == "true",
            api_version=os.getenv("STORAGE_API_VERSION", "v1"),
            local_repo_path=os.getenv("STORAGE_LOCAL_PATH", "remote"),
            data_path=os.getenv("STORAGE_DATA_PATH", "data"),
            git_username=os.getenv("GIT_USERNAME"),
            git_token=os.getenv("GIT_TOKEN"),
            artifactory_repo_type=os.getenv("ARTIFACTORY_REPO_TYPE", "generic-local")
        )
        
        # Authentication configuration
        authentication = AuthenticationConfig(
            default_admin_username=os.getenv("ADMIN_USERNAME", "admin"),
            default_admin_password=os.getenv("ADMIN_PASSWORD", "password"),
            default_admin_email=os.getenv("ADMIN_EMAIL", "admin@sakura.com"),
            session_timeout=int(os.getenv("AUTH_SESSION_TIMEOUT", "3600")),
            max_login_attempts=int(os.getenv("AUTH_MAX_ATTEMPTS", "5")),
            lockout_duration=int(os.getenv("AUTH_LOCKOUT_DURATION", "900")),
            reserved_usernames=os.getenv("AUTH_RESERVED_USERNAMES", "admin,root,system,administrator,sa").split(","),
            min_password_length=int(os.getenv("AUTH_MIN_PASSWORD_LENGTH", "8")),
            require_special_chars=os.getenv("AUTH_REQUIRE_SPECIAL_CHARS", "true").lower() == "true",
            require_numbers=os.getenv("AUTH_REQUIRE_NUMBERS", "true").lower() == "true",
            require_uppercase=os.getenv("AUTH_REQUIRE_UPPERCASE", "true").lower() == "true"
        )
        
        # Server configuration
        server = ServerConfig(
            host=os.getenv("SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("SERVER_PORT", "5000")),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            mock_mode=os.getenv("MOCK_MODE", "true").lower() == "true",
            mock_server_port=int(os.getenv("MOCK_SERVER_PORT", "8080")),
            cors_origins=os.getenv("CORS_ORIGINS", "*").split(","),
            cors_methods=os.getenv("CORS_METHODS", "GET,POST,PUT,DELETE").split(","),
            cors_headers=os.getenv("CORS_HEADERS", "Content-Type,Authorization").split(","),
            rate_limit_enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
            rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "100")),
            rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", "3600"))
        )
        
        # Logging configuration
        logging = LoggingConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            format=os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            file_path=os.getenv("LOG_FILE_PATH"),
            max_file_size=int(os.getenv("LOG_MAX_FILE_SIZE", str(10 * 1024 * 1024))),
            backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
            enable_console=os.getenv("LOG_ENABLE_CONSOLE", "true").lower() == "true",
            enable_file=os.getenv("LOG_ENABLE_FILE", "false").lower() == "true",
            structured_logging=os.getenv("LOG_STRUCTURED", "false").lower() == "true",
            log_json=os.getenv("LOG_JSON", "false").lower() == "true"
        )
        
        # Feature flags
        features = {
            "user_management": os.getenv("FEATURE_USER_MANAGEMENT", "true").lower() == "true",
            "test_case_management": os.getenv("FEATURE_TEST_CASE_MANAGEMENT", "true").lower() == "true",
            "requirement_management": os.getenv("FEATURE_REQUIREMENT_MANAGEMENT", "true").lower() == "true",
            "git_integration": os.getenv("FEATURE_GIT_INTEGRATION", "true").lower() == "true",
            "artifactory_integration": os.getenv("FEATURE_ARTIFACTORY_INTEGRATION", "false").lower() == "true",
            "advanced_logging": os.getenv("FEATURE_ADVANCED_LOGGING", "false").lower() == "true"
        }
        
        return cls(
            environment=env,
            database=database,
            storage=storage,
            authentication=authentication,
            server=server,
            logging=logging,
            features=features
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "environment": self.environment,
            "database": {
                "provider": self.database.provider.value,
                "name": self.database.name,
                "host": self.database.host,
                "port": self.database.port,
                "username": self.database.username,
                "password": "***",  # Hide password
                "schema": self.database.schema,
                "connection_pool_size": self.database.connection_pool_size,
                "connection_timeout": self.database.connection_timeout,
                "ssl_enabled": self.database.ssl_enabled,
                "ssl_cert_path": self.database.ssl_cert_path,
                "data_directory": self.database.data_directory,
                "cache_directory": self.database.cache_directory,
                "table_names": self.database.table_names
            },
            "storage": {
                "provider": self.storage.provider.value,
                "base_url": self.storage.base_url,
                "username": self.storage.username,
                "password": "***",  # Hide password
                "repository": self.storage.repository,
                "branch": self.storage.branch,
                "timeout": self.storage.timeout,
                "retry_attempts": self.storage.retry_attempts,
                "retry_delay": self.storage.retry_delay,
                "verify_ssl": self.storage.verify_ssl,
                "api_version": self.storage.api_version,
                "local_repo_path": self.storage.local_repo_path,
                "data_path": self.storage.data_path,
                "git_username": self.storage.git_username,
                "git_token": "***" if self.storage.git_token else None,
                "artifactory_repo_type": self.storage.artifactory_repo_type
            },
            "authentication": {
                "default_admin_username": self.authentication.default_admin_username,
                "default_admin_password": "***",  # Hide password
                "default_admin_email": self.authentication.default_admin_email,
                "session_timeout": self.authentication.session_timeout,
                "max_login_attempts": self.authentication.max_login_attempts,
                "lockout_duration": self.authentication.lockout_duration,
                "reserved_usernames": self.authentication.reserved_usernames,
                "min_password_length": self.authentication.min_password_length,
                "require_special_chars": self.authentication.require_special_chars,
                "require_numbers": self.authentication.require_numbers,
                "require_uppercase": self.authentication.require_uppercase
            },
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "debug": self.server.debug,
                "mock_mode": self.server.mock_mode,
                "mock_server_port": self.server.mock_server_port,
                "cors_origins": self.server.cors_origins,
                "cors_methods": self.server.cors_methods,
                "cors_headers": self.server.cors_headers,
                "rate_limit_enabled": self.server.rate_limit_enabled,
                "rate_limit_requests": self.server.rate_limit_requests,
                "rate_limit_window": self.server.rate_limit_window
            },
            "logging": {
                "level": self.logging.level,
                "format": self.logging.format,
                "file_path": self.logging.file_path,
                "max_file_size": self.logging.max_file_size,
                "backup_count": self.logging.backup_count,
                "enable_console": self.logging.enable_console,
                "enable_file": self.logging.enable_file,
                "structured_logging": self.logging.structured_logging,
                "log_json": self.logging.log_json
            },
            "features": self.features
        }


# Environment-specific configurations
class DevelopmentConfig(ApplicationConfig):
    """Development environment configuration"""
    def __init__(self):
        super().__init__(
            environment="development",
            database=DatabaseConfig(
                provider=DatabaseProvider.SQLITE,
                name="sakura_dev.db",
                data_directory="data/local",
                cache_directory="data/local"
            ),
            storage=StorageConfig(
                provider=StorageProvider.GIT,
                base_url="https://gitlab.com/android-devops/sakura-db",
                username="admin",
                password="password",
                repository="android-devops/sakura-db",
                local_repo_path="remote/dev",
                data_path="data/local"
            ),
            authentication=AuthenticationConfig(
                default_admin_username="admin",
                default_admin_password="password",
                default_admin_email="admin@sakura.com"
            ),
            server=ServerConfig(
                host="0.0.0.0",
                port=5000,
                debug=True,
                mock_mode=True,
                mock_server_port=8080
            ),
            logging=LoggingConfig(
                level="DEBUG",
                enable_console=True,
                enable_file=False
            ),
            features={
                "user_management": True,
                "test_case_management": True,
                "requirement_management": True,
                "git_integration": True,
                "artifactory_integration": False,
                "advanced_logging": False
            }
        )


class ProductionConfig(ApplicationConfig):
    """Production environment configuration"""
    def __init__(self):
        super().__init__(
            environment="production",
            database=DatabaseConfig(
                provider=DatabaseProvider.POSTGRESQL,
                name="sakura_prod",
                host="localhost",
                port=5432,
                username="sakura_user",
                password="secure_password",
                ssl_enabled=True
            ),
            storage=StorageConfig(
                provider=StorageProvider.ARTIFACTORY,
                base_url="https://artifactory.company.com",
                username="artifactory_user",
                password="secure_password",
                repository="sakura-configs",
                verify_ssl=True
            ),
            authentication=AuthenticationConfig(
                default_admin_username="admin",
                default_admin_password="secure_admin_password",
                default_admin_email="admin@company.com",
                session_timeout=1800,  # 30 minutes
                max_login_attempts=3,
                lockout_duration=1800  # 30 minutes
            ),
            server=ServerConfig(
                host="0.0.0.0",
                port=5000,
                debug=False,
                mock_mode=False,
                rate_limit_enabled=True,
                rate_limit_requests=50,
                rate_limit_window=3600
            ),
            logging=LoggingConfig(
                level="INFO",
                enable_console=False,
                enable_file=True,
                file_path="/var/log/sakura/app.log",
                structured_logging=True,
                log_json=True
            ),
            features={
                "user_management": True,
                "test_case_management": True,
                "requirement_management": True,
                "git_integration": False,
                "artifactory_integration": True,
                "advanced_logging": True
            }
        )


class TestingConfig(ApplicationConfig):
    """Testing environment configuration"""
    def __init__(self):
        super().__init__(
            environment="testing",
            database=DatabaseConfig(
                provider=DatabaseProvider.SQLITE,
                name="sakura_test.db",
                data_directory="data/test",
                cache_directory="data/cache/test"
            ),
            storage=StorageConfig(
                provider=StorageProvider.LOCAL,
                base_url="file:///tmp/sakura-test",
                username="test",
                password="test",
                repository="test-repo",
                local_repo_path="remote/test",
                data_path="data/test"
            ),
            authentication=AuthenticationConfig(
                default_admin_username="testadmin",
                default_admin_password="testpass",
                default_admin_email="testadmin@sakura.com"
            ),
            server=ServerConfig(
                host="127.0.0.1",
                port=5001,
                debug=True,
                mock_mode=True,
                mock_server_port=8081
            ),
            logging=LoggingConfig(
                level="DEBUG",
                enable_console=True,
                enable_file=False
            ),
            features={
                "user_management": True,
                "test_case_management": True,
                "requirement_management": True,
                "git_integration": False,
                "artifactory_integration": False,
                "advanced_logging": False
            }
        )


def get_config(environment: str = None) -> ApplicationConfig:
    """Get configuration for specified environment"""
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "development":
        return DevelopmentConfig()
    elif environment == "production":
        return ProductionConfig()
    elif environment == "testing":
        return TestingConfig()
    else:
        # Fallback to environment-based configuration
        return ApplicationConfig.from_environment(environment)
