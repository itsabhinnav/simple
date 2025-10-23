"""
Dependency Injection Container

This module provides a dependency injection container following SOLID principles,
managing the lifecycle and dependencies of application components.
"""

from typing import Dict, Any, Optional, Type, TypeVar, Callable
from functools import lru_cache
import asyncio

from src.interfaces.git_file_storage import IGitFileStorage
from src.implementations.git_file_storage import GitFileStorage
from src.services.git_database_service import GitDatabaseService
from src.repositories.user_repository import IUserRepository, UserRepository
from src.repositories.test_case_repository import ITestCaseRepository, TestCaseRepository
from src.services.user_service import IUserService, UserService
from src.services.test_case_service import ITestCaseService, TestCaseService
from config.settings import settings
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class DIContainer:
    """
    Simple dependency injection container for managing application dependencies.
    
    This container follows the Dependency Inversion Principle (DIP) of SOLID,
    allowing high-level modules to depend on abstractions rather than concrete implementations.
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, bool] = {}
    
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
    Application-specific dependency injection container.
    
    This container configures all the dependencies needed for the Artifactory integration,
    following SOLID principles and providing a clean separation of concerns.
    """
    
    def __init__(self):
        self.container = DIContainer()
        self._setup_services()
    
    def _setup_services(self):
        """Set up all application services."""
        logger.info("Setting up Git-based application services")
        
        # Register Git file storage
        self.container.register_singleton(
            IGitFileStorage,
            GitFileStorage,
            factory=lambda: GitFileStorage(
                repo_url="https://gitlab.com/android-devops/sakura-db",
                local_repo_path="remote",
                data_path="data"
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
        
        # Register repositories
        self.container.register_singleton(
            IUserRepository,
            UserRepository,
            factory=lambda: UserRepository(
                database_service=self.container.get(GitDatabaseService)
            )
        )
        
        self.container.register_singleton(
            ITestCaseRepository,
            TestCaseRepository,
            factory=lambda: TestCaseRepository(
                database_service=self.container.get(GitDatabaseService)
            )
        )
        
        # Register services
        self.container.register_singleton(
            IUserService,
            UserService,
            factory=lambda: UserService(
                user_repository=self.container.get(IUserRepository)
            )
        )
        
        self.container.register_singleton(
            ITestCaseService,
            TestCaseService,
            factory=lambda: TestCaseService(
                test_case_repository=self.container.get(ITestCaseRepository)
            )
        )
        
        
        logger.info("Application services configured successfully")
    
    async def initialize(self):
        """Initialize the application container."""
        logger.info("Initializing application container")
        
        try:
            # Authenticate with Artifactory
            client = self.container.get(IArtifactoryClient)
            await client.authenticate(
                settings.artifactory.username,
                settings.artifactory.password
            )
            
            # Perform health check
            is_healthy = await client.health_check()
            if not is_healthy:
                logger.warning("Artifactory health check failed")
            else:
                logger.info("Artifactory health check passed")
            
            logger.info("Application container initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize application container: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup application resources."""
        logger.info("Cleaning up application resources")
        
        try:
            # Close enhanced database connections
            enhanced_db_service = self.container.get(EnhancedSQLiteDatabaseService)
            await enhanced_db_service.close_all_connections()
            
            # Close legacy database connections
            db_service = self.container.get(SQLiteDatabaseService)
            await db_service.close_all_connections()
            
            # Cleanup expired sessions
            session_manager = self.container.get(IUserSessionManager)
            expired_count = await session_manager.cleanup_expired_sessions()
            logger.info(f"Cleaned up {expired_count} expired sessions")
            
            # Close Artifactory client
            client = self.container.get(IArtifactoryClient)
            if hasattr(client, 'close'):
                await client.close()
            
            logger.info("Application cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Global application container
app_container = ApplicationContainer()


@lru_cache()
def get_container() -> ApplicationContainer:
    """Get the global application container."""
    return app_container


# Convenience functions for common services


def get_git_file_storage() -> IGitFileStorage:
    """Get the Git file storage service."""
    return get_container().container.get(IGitFileStorage)


def get_git_database_service() -> GitDatabaseService:
    """Get the Git database service."""
    return get_container().container.get(GitDatabaseService)


def get_user_service() -> IUserService:
    """Get the user service."""
    return get_container().container.get(IUserService)


def get_test_case_service() -> ITestCaseService:
    """Get the test case service."""
    return get_container().container.get(ITestCaseService)


def get_user_repository() -> IUserRepository:
    """Get the user repository."""
    return get_container().container.get(IUserRepository)


def get_test_case_repository() -> ITestCaseRepository:
    """Get the test case repository."""
    return get_container().container.get(ITestCaseRepository)
