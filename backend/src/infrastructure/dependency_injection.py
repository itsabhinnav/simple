"""
Configuration-based Dependency Injection Container

This module provides a dependency injection container that uses configuration
to instantiate services, making the system easily extensible and configurable.
"""

from typing import Dict, Any, Optional, Type, TypeVar, Callable
from functools import lru_cache
import asyncio

from src.services.local_database_service import LocalDatabaseService
from src.services.postgresql_database_service import PostgresDatabaseService
from src.services.hybrid_database_service import HybridDatabaseService
from src.services.database_backup_service import DatabaseBackupService, PeriodicBackupWorker
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
        logger.info("Setting up configuration-based application services (local-only mode)")

        # Get configuration
        database_config = self._config_manager.get_database_config()

        # Remote/Git database sync has been removed: no storage provider, no
        # GitFileStorage, no GitDatabaseService. Everything is local SQLite.

        # Register primary database service based on configuration
        db_provider = database_config.get("provider", "sqlite")
        self._db_provider = db_provider
        
        if db_provider == "postgresql":
            logger.info("Using PostgreSQL as the primary database")
            self.container.register_singleton(
                LocalDatabaseService,
                PostgresDatabaseService,
                factory=lambda: PostgresDatabaseService()
            )
        else:
            logger.info("Using SQLite as the primary database")
            self.container.register_singleton(
                LocalDatabaseService,
                LocalDatabaseService,
                factory=lambda: LocalDatabaseService()
            )
            self.container.register_singleton(
                DatabaseBackupService,
                DatabaseBackupService,
                factory=lambda: DatabaseBackupService(
                    db_path=self.container.get(LocalDatabaseService).local_db_path,
                ),
            )
        
        # Hybrid database service now runs purely against the local SQLite
        # database. Remote/Git mirror was deleted; do not reintroduce it.
        self.container.register_singleton(
            HybridDatabaseService,
            HybridDatabaseService,
            factory=lambda: HybridDatabaseService(
                local_db_service=self.container.get(LocalDatabaseService),
                backup_service=(
                    self.container.get(DatabaseBackupService)
                    if db_provider != "postgresql"
                    else None
                ),
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
        
        # Activity log singleton must be available before the test case
        # repository so we can pass it in at construction time. It's
        # registered above (see _setup_services tail) — but pylint-style
        # ordering is fine since DI resolution is lazy.
        self.container.register_singleton(
            ITestCaseRepository,
            TestCaseRepository,
            factory=lambda: TestCaseRepository(
                database_service=self.container.get(HybridDatabaseService),
                table_name=test_cases_table,
            )
        )
        
        # Register services
        self.container.register_singleton(
            IUserService,
            UserService,
            factory=lambda: UserService(
                user_repository=self.container.get(IUserRepository),
            )
        )

        self.container.register_singleton(
            ITestCaseService,
            TestCaseService,
            factory=lambda: TestCaseService(
                test_case_repository=self.container.get(ITestCaseRepository),
            )
        )
        
        # Activity log service is a thin wrapper over the hybrid DB; one
        # singleton is shared across every entity service so the parent_hash
        # chain stays continuous.
        from src.services.activity_log_service import ActivityLogService

        self.container.register_singleton(
            ActivityLogService,
            ActivityLogService,
            factory=lambda: ActivityLogService(
                database_service=self.container.get(HybridDatabaseService),
            ),
        )

        # Register requirement service
        from src.services.requirement_service import IRequirementService, RequirementService

        self.container.register_singleton(
            IRequirementService,
            RequirementService,
            factory=lambda: RequirementService(
                database_service=self.container.get(HybridDatabaseService),
                activity_log_service=self.container.get(ActivityLogService),
            )
        )
        
        # Register design ticket service
        from src.services.design_ticket_service import IDesignTicketService, DesignTicketService
        
        self.container.register_singleton(
            IDesignTicketService,
            DesignTicketService,
            factory=lambda: DesignTicketService(
                database_service=self.container.get(HybridDatabaseService)
            )
        )

        # Register specification service
        from src.services.spec_service import ISpecService, SpecService
        self.container.register_singleton(
            ISpecService,
            SpecService,
            factory=lambda: SpecService(
                database_service=self.container.get(HybridDatabaseService)
            )
        )
        
        logger.info("Configuration-based application services configured successfully")
    
    async def initialize(self):
        """Initialize the application container (local-only mode)."""
        logger.info("Initializing application container (local-only mode)")

    async def cleanup(self):
        """Cleanup application resources (local-only mode)."""
        logger.info("Application cleanup completed (local-only mode)")
    
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

def get_hybrid_database_service() -> HybridDatabaseService:
    """Get the hybrid database service (local-only)."""
    return get_container().container.get(HybridDatabaseService)


def get_local_database_service() -> LocalDatabaseService:
    """Get the local database service."""
    return get_container().container.get(LocalDatabaseService)


def get_database_backup_service() -> DatabaseBackupService:
    """Get the SQLite backup / recovery service."""
    container = get_container().container
    if not container.is_registered(DatabaseBackupService):
        raise RuntimeError("DatabaseBackupService is only available for SQLite deployments")
    return container.get(DatabaseBackupService)


def get_periodic_backup_worker() -> PeriodicBackupWorker:
    """Return a configured periodic backup worker (not started)."""
    return PeriodicBackupWorker(get_database_backup_service())


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


def get_design_ticket_service():
    """Get the design ticket service."""
    from src.services.design_ticket_service import IDesignTicketService
    return get_container().container.get(IDesignTicketService)


def get_spec_service():
    """Get the specification service."""
    from src.services.spec_service import ISpecService
    return get_container().container.get(ISpecService)


def get_user_repository() -> IUserRepository:
    """Get the user repository."""
    return get_container().container.get(IUserRepository)


def get_test_case_repository() -> ITestCaseRepository:
    """Get the test case repository."""
    return get_container().container.get(ITestCaseRepository)


def get_activity_log_service():
    """Get the singleton activity / change-log service."""
    from src.services.activity_log_service import ActivityLogService
    return get_container().container.get(ActivityLogService)


# --------------------- Hybrid document parsing engine ---------------------

_PARSING_SINGLETONS: Dict[str, Any] = {}


def _parsing_singleton(name: str, factory: Callable[[], Any]) -> Any:
    if name not in _PARSING_SINGLETONS:
        _PARSING_SINGLETONS[name] = factory()
    return _PARSING_SINGLETONS[name]


def get_schema_service():
    """Return a lazily-built SchemaService bound to the local SQLite DB."""

    def _factory():
        from src.services.schema_service import SchemaService

        return SchemaService(get_local_database_service())

    return _parsing_singleton("schema_service", _factory)


def get_excel_deterministic_parser():
    """Lazily build the deterministic Excel parser."""
    from src.services.parsing.deterministic.excel_parser import ExcelDeterministicParser

    return _parsing_singleton("excel_parser", ExcelDeterministicParser)


def get_docx_deterministic_parser():
    """Lazily build the deterministic DOCX parser."""
    from src.services.parsing.deterministic.docx_parser import DocxDeterministicParser

    return _parsing_singleton("docx_parser", DocxDeterministicParser)


def get_visual_preprocessor():
    """Lazily build the visual preprocessor (LibreOffice snapshots)."""
    from src.services.parsing.visual.preprocessor import VisualPreprocessor

    return _parsing_singleton("visual_preprocessor", VisualPreprocessor)


def get_context_assembler():
    """Lazily build the hybrid context assembler."""
    from src.services.parsing.context_assembly import HybridContextAssembler

    return _parsing_singleton("context_assembler", HybridContextAssembler)


def get_vlm_registry():
    """Return the singleton VLM registry, configured from config_manager."""
    import src.implementations.llm  # noqa: F401 - auto-registers providers
    from src.interfaces.llm_provider import get_vlm_registry as _get_registry

    registry = _get_registry()
    registry.configure_from_config(get_config_manager())
    return registry


def get_strict_reconciler():
    """Lazily build the strict reconciler."""
    from src.services.parsing.reconciliation import StrictReconciler

    return _parsing_singleton("strict_reconciler", StrictReconciler)


def get_hybrid_document_parser():
    """Lazily build the full hybrid document parser orchestrator."""

    def _factory():
        from src.services.parsing.hybrid_parser import HybridDocumentParser

        return HybridDocumentParser(
            excel_parser=get_excel_deterministic_parser(),
            docx_parser=get_docx_deterministic_parser(),
            visual_preprocessor=get_visual_preprocessor(),
            assembler=get_context_assembler(),
            vlm_registry=get_vlm_registry(),
            reconciler=get_strict_reconciler(),
            config=get_config_manager(),
        )

    return _parsing_singleton("hybrid_document_parser", _factory)


def get_parsing_service():
    """Lazily build the parsing service used by the Flask controller."""

    def _factory():
        from src.services.parsing_service import ParsingService

        return ParsingService(get_hybrid_document_parser())

    return _parsing_singleton("parsing_service", _factory)


def get_vector_index_service():
    """Lazily build the RAG vector index service. Returns None if the
    feature is disabled via ``assistant.rag.enabled: false`` in config."""

    def _factory():
        from src.services.vector_index_service import VectorIndexService

        if not get_config_manager().get_config("assistant.rag.enabled", True):
            return None

        return VectorIndexService(
            requirement_service=get_requirement_service(),
            test_case_service=get_test_case_service(),
            design_ticket_service=get_design_ticket_service(),
            spec_service=get_spec_service(),
            local_database_service=get_local_database_service(),
            vlm_registry=get_vlm_registry(),
        )

    return _parsing_singleton("vector_index_service", _factory)


def get_live_indexer():
    """Return the singleton LiveIndexer thread (or None if RAG is disabled).

    The thread is created lazily and started by ``main.py`` after Flask boot.
    """

    def _factory():
        from src.services.vector_index_service import LiveIndexer

        vec = get_vector_index_service()
        if vec is None:
            return None
        cfg = get_config_manager()
        poll = float(cfg.get_config("assistant.rag.poll_interval_seconds", 15) or 15)
        delay = float(cfg.get_config("assistant.rag.startup_delay_seconds", 2) or 2)
        return LiveIndexer(vec, poll_interval_seconds=poll, startup_delay_seconds=delay)

    return _parsing_singleton("live_indexer", _factory)


def get_assistant_service():
    """Lazily build the NL chat assistant service used by /api/assistant/*."""

    def _factory():
        from src.services.assistant_service import AssistantService

        return AssistantService(
            requirement_service=get_requirement_service(),
            test_case_service=get_test_case_service(),
            design_ticket_service=get_design_ticket_service(),
            spec_service=get_spec_service(),
            vlm_registry=get_vlm_registry(),
            vector_index_service=get_vector_index_service(),
        )

    return _parsing_singleton("assistant_service", _factory)


# Ensure VLM adapters auto-register on import of this module.
try:  # noqa: SIM105 - best-effort registration on import
    import src.implementations.llm  # noqa: F401
except Exception as _exc:  # noqa: BLE001
    logger.warning(f"VLM adapter auto-registration failed: {_exc}")
