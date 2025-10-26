"""
Configuration-based Dependency Injection Container

This module provides a dependency injection container that uses configuration
to instantiate services, making the system easily extensible and configurable.
"""

from typing import Dict, Any, Optional, Type, TypeVar, Callable
from functools import lru_cache
import asyncio

from src.interfaces.git_file_storage import IGitFileStorage
from src.interfaces.providers import IStorageProvider
from src.implementations.git_file_storage import GitFileStorage
from src.implementations.storage_providers import create_storage_provider
from src.services.local_database_service import LocalDatabaseService
from src.services.hybrid_database_service import HybridDatabaseService
from src.services.git_database_service import GitDatabaseService
from src.repositories.user_repository import IUserRepository, UserRepository
from src.repositories.test_case_repository import ITestCaseRepository, TestCaseRepository
from src.services.user_service import IUserService, UserService
from src.services.test_case_service import ITestCaseService, TestCaseService
from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class DIContainer:
    """
    Configuration-based dependency injection container for managing application dependencies.
    
    This container follows the Dependency Inversion Principle (DIP) of SOLID,
    allowing high-level modules to depend on abstractions rather than concrete implementations.
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, bool] = {}
        self._config_manager = get_config_manager()
    
    def register_singleton(
        self, 
        interface: Type[T], 
        implementation: Type[T], 
        factory: Optional[Callable] = None
    ):
        """Register a singleton service."""
        key = interface.__name__
        self._singletons[key] = True
        
        if factory:
            self._factories[key] = factory
        else:
            self._factories[key] = lambda: implementation()
        
        logger.debug(f"Registered singleton: {key}")
    
    def register_transient(
        self, 
        interface: Type[T], 
        implementation: Type[T], 
        factory: Optional[Callable] = None
    ):
        """Register a transient service."""
        key = interface.__name__
        self._singletons[key] = False
        
        if factory:
            self._factories[key] = factory
        else:
            self._factories[key] = lambda: implementation()
        
        logger.debug(f"Registered transient: {key}")
    
    def register_instance(self, interface: Type[T], instance: T):
        """Register a service instance."""
        key = interface.__name__
        self._services[key] = instance
        self._singletons[key] = True
        logger.debug(f"Registered instance: {key}")
    
    def get(self, interface: Type[T]) -> T:
        """Get a service instance."""
        key = interface.__name__
        
        # Return existing instance if singleton
        if key in self._services and self._singletons.get(key, False):
            return self._services[key]
        
        # Create new instance
        if key not in self._factories:
            raise ValueError(f"Service not registered: {key}")
        
        instance = self._factories[key]()
        
        # Store instance if singleton
        if self._singletons.get(key, False):
            self._services[key] = instance
        
        return instance
    
    def is_registered(self, interface: Type[T]) -> bool:
        """Check if a service is registered."""
        return interface.__name__ in self._factories or interface.__name__ in self._services


class ApplicationContainer:
    """
    Configuration-based application dependency injection container.
    
    This container configures all the dependencies needed for the application,
    using configuration to determine which implementations to use.
    """
    
    def __init__(self):
        self.container = DIContainer()
        self._config_manager = get_config_manager()
        self._setup_services()
    
    def _setup_services(self):
        """Set up all application services based on configuration."""
        logger.info("Setting up configuration-based application services")
        
        # Get configuration
        storage_config = self._config_manager.get_storage_config()
        database_config = self._config_manager.get_database_config()
        
        # Register storage provider based on configuration
        storage_provider_type = storage_config.get("provider", "git")
        logger.info(f"Using storage provider: {storage_provider_type}")
        
        if storage_provider_type == "git":
            # Register Git file storage (legacy interface for backward compatibility)
            self.container.register_singleton(
                IGitFileStorage,
                GitFileStorage,
                factory=lambda: GitFileStorage(
                    repo_url=storage_config.get("base_url", "https://gitlab.com/android-devops/sakura-db"),
                    local_repo_path=storage_config.get("local_repo_path", "remote"),
                    data_path=storage_config.get("data_path", "data")
                )
            )
            
            # Register new storage provider interface
            self.container.register_singleton(
                IStorageProvider,
                create_storage_provider(storage_config)
            )
            
        elif storage_provider_type == "artifactory":
            # Register Artifactory storage provider
            self.container.register_singleton(
                IStorageProvider,
                create_storage_provider(storage_config)
            )
            
            # Create a Git file storage adapter for backward compatibility
            self.container.register_singleton(
                IGitFileStorage,
                GitFileStorage,
                factory=lambda: GitFileStorage(
                    repo_url=storage_config.get("base_url", "http://localhost:8080"),
                    local_repo_path=storage_config.get("local_repo_path", "remote"),
                    data_path=storage_config.get("data_path", "data")
                )
            )
            
        elif storage_provider_type == "local":
            # Register local storage provider
            self.container.register_singleton(
                IStorageProvider,
                create_storage_provider(storage_config)
            )
            
            # Create a Git file storage adapter for backward compatibility
            self.container.register_singleton(
                IGitFileStorage,
                GitFileStorage,
                factory=lambda: GitFileStorage(
                    repo_url=storage_config.get("base_url", "file:///tmp/sakura"),
                    local_repo_path=storage_config.get("local_repo_path", "remote"),
                    data_path=storage_config.get("data_path", "data")
                )
            )
        
        # Register Git database service
        self.container.register_singleton(
            GitDatabaseService,
            GitDatabaseService,
            factory=lambda: GitDatabaseService(
                git_storage=self.container.get(IGitFileStorage)
            )
        )
        
        # Register Local database service
        self.container.register_singleton(
            LocalDatabaseService,
            LocalDatabaseService,
            factory=lambda: LocalDatabaseService()
        )
        
        # Register Hybrid database service
        self.container.register_singleton(
            HybridDatabaseService,
            HybridDatabaseService,
            factory=lambda: HybridDatabaseService(
                local_db_service=self.container.get(LocalDatabaseService),
                remote_db_service=self.container.get(GitDatabaseService)
            )
        )
        
        # Register repositories with configuration-based table names
        users_table = self._config_manager.get_table_name("users")
        test_cases_table = self._config_manager.get_table_name("test_cases")
        
        self.container.register_singleton(
            IUserRepository,
            UserRepository,
            factory=lambda: UserRepository(
                database_service=self.container.get(HybridDatabaseService),
                table_name=users_table
            )
        )
        
        self.container.register_singleton(
            ITestCaseRepository,
            TestCaseRepository,
            factory=lambda: TestCaseRepository(
                database_service=self.container.get(HybridDatabaseService),
                table_name=test_cases_table
            )
        )
        
        # Register services
        self.container.register_singleton(
            IUserService,
            UserService,
            factory=lambda: UserService(
                user_repository=self.container.get(IUserRepository),
                git_database_service=self.container.get(HybridDatabaseService)
            )
        )
        
        self.container.register_singleton(
            ITestCaseService,
            TestCaseService,
            factory=lambda: TestCaseService(
                test_case_repository=self.container.get(ITestCaseRepository),
                git_database_service=self.container.get(HybridDatabaseService)
            )
        )
        
        # Register requirement service
        from src.services.requirement_service import IRequirementService, RequirementService
        
        self.container.register_singleton(
            IRequirementService,
            RequirementService,
            factory=lambda: RequirementService(
                database_service=self.container.get(HybridDatabaseService)
            )
        )
        
        logger.info("Configuration-based application services configured successfully")
    
    async def initialize(self):
        """Initialize the application container."""
        logger.info("Initializing configuration-based application container")
        
        try:
            # Initialize storage provider
            if self.container.is_registered(IStorageProvider):
                storage_provider = self.container.get(IStorageProvider)
                
                # Authenticate with storage provider
                storage_config = self._config_manager.get_storage_config()
                if hasattr(storage_provider, 'authenticate'):
                    auth_success = storage_provider.authenticate(
                        storage_config.get("username", ""),
                        storage_config.get("password", "")
                    )
                    if not auth_success:
                        logger.warning("Storage provider authentication failed")
                
                # Perform health check
                if hasattr(storage_provider, 'health_check'):
                    is_healthy = storage_provider.health_check()
                    if not is_healthy:
                        logger.warning("Storage provider health check failed")
                    else:
                        logger.info("Storage provider health check passed")
            
            # Initialize Git database service if using Git
            if self._config_manager.get_storage_provider() == "git":
                git_db_service = self.container.get(GitDatabaseService)
                if hasattr(git_db_service, 'initialize'):
                    init_success = git_db_service.initialize()
                    if not init_success:
                        logger.warning("Git database service initialization failed")
                    else:
                        logger.info("Git database service initialized successfully")
            
            logger.info("Configuration-based application container initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize application container: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup application resources."""
        logger.info("Cleaning up application resources")
        
        try:
            # Close storage provider connections if needed
            if self.container.is_registered(IStorageProvider):
                storage_provider = self.container.get(IStorageProvider)
                if hasattr(storage_provider, 'close'):
                    await storage_provider.close()
            
            # Close Git database service connections if needed
            if self.container.is_registered(GitDatabaseService):
                git_db_service = self.container.get(GitDatabaseService)
                if hasattr(git_db_service, 'close'):
                    await git_db_service.close()
            
            logger.info("Application cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def reload_configuration(self):
        """Reload configuration and reinitialize services."""
        logger.info("Reloading configuration")
        
        try:
            # Reload configuration
            self._config_manager.reload_config()
            
            # Clear existing services
            self.container._services.clear()
            
            # Re-setup services with new configuration
            self._setup_services()
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            raise


# Global application container
app_container = ApplicationContainer()


@lru_cache()
def get_container() -> ApplicationContainer:
    """Get the global application container."""
    return app_container


# Convenience functions for common services

def get_storage_provider() -> IStorageProvider:
    """Get the storage provider service."""
    return get_container().container.get(IStorageProvider)


def get_git_file_storage() -> IGitFileStorage:
    """Get the Git file storage service."""
    return get_container().container.get(IGitFileStorage)


def get_hybrid_database_service() -> HybridDatabaseService:
    """Get the hybrid database service."""
    return get_container().container.get(HybridDatabaseService)


def get_local_database_service() -> LocalDatabaseService:
    """Get the local database service."""
    return get_container().container.get(LocalDatabaseService)


def get_git_database_service() -> GitDatabaseService:
    """Get the Git database service."""
    return get_container().container.get(GitDatabaseService)


def get_user_service() -> IUserService:
    """Get the user service."""
    return get_container().container.get(IUserService)


def get_test_case_service() -> ITestCaseService:
    """Get the test case service."""
    return get_container().container.get(ITestCaseService)


def get_requirement_service():
    """Get the requirement service."""
    from src.services.requirement_service import IRequirementService
    return get_container().container.get(IRequirementService)


def get_user_repository() -> IUserRepository:
    """Get the user repository."""
    return get_container().container.get(IUserRepository)


def get_test_case_repository() -> ITestCaseRepository:
    """Get the test case repository."""
    return get_container().container.get(ITestCaseRepository)
