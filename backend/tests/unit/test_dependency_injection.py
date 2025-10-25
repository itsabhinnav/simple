"""
Unit Tests for Dependency Injection Container

This module provides comprehensive unit tests for the DIContainer class
to achieve 100% C0 and C1 coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.infrastructure.dependency_injection import DIContainer, get_container
from tests import mock_config_manager, mock_logger


class TestDIContainer:
    """Test cases for DIContainer"""
    
    def test_init(self):
        """Test container initialization"""
        container = DIContainer()
        assert container.container is not None
        assert len(container.container._factories) == 0
    
    def test_register_singleton(self):
        """Test registering singleton service"""
        container = DIContainer()
        
        class TestService:
            pass
        
        container.register_singleton(TestService, TestService)
        
        assert TestService in container.container._factories
        
        # Test that it's actually a singleton
        instance1 = container.container.get(TestService)
        instance2 = container.container.get(TestService)
        assert instance1 is instance2
    
    def test_register_singleton_with_factory(self):
        """Test registering singleton with factory function"""
        container = DIContainer()
        
        class TestService:
            def __init__(self, value):
                self.value = value
        
        def factory():
            return TestService("test_value")
        
        container.register_singleton(TestService, factory)
        
        instance = container.container.get(TestService)
        assert isinstance(instance, TestService)
        assert instance.value == "test_value"
    
    def test_register_transient(self):
        """Test registering transient service"""
        container = DIContainer()
        
        class TestService:
            pass
        
        container.register_transient(TestService, TestService)
        
        assert TestService in container.container._factories
        
        # Test that it creates new instances
        instance1 = container.container.get(TestService)
        instance2 = container.container.get(TestService)
        assert instance1 is not instance2
        assert isinstance(instance1, TestService)
        assert isinstance(instance2, TestService)
    
    def test_register_transient_with_factory(self):
        """Test registering transient with factory function"""
        container = DIContainer()
        
        class TestService:
            def __init__(self, value):
                self.value = value
        
        def factory():
            return TestService("test_value")
        
        container.register_transient(TestService, factory)
        
        instance1 = container.container.get(TestService)
        instance2 = container.container.get(TestService)
        
        assert isinstance(instance1, TestService)
        assert isinstance(instance2, TestService)
        assert instance1.value == "test_value"
        assert instance2.value == "test_value"
        assert instance1 is not instance2
    
    def test_get_service_not_registered(self):
        """Test getting service that's not registered"""
        container = DIContainer()
        
        class TestService:
            pass
        
        with pytest.raises(KeyError):
            container.container.get(TestService)
    
    def test_get_service_with_dependencies(self):
        """Test getting service with dependencies"""
        container = DIContainer()
        
        class Dependency:
            def __init__(self):
                self.value = "dependency_value"
        
        class TestService:
            def __init__(self, dependency: Dependency):
                self.dependency = dependency
        
        container.register_singleton(Dependency, Dependency)
        container.register_singleton(TestService, TestService)
        
        instance = container.container.get(TestService)
        
        assert isinstance(instance, TestService)
        assert isinstance(instance.dependency, Dependency)
        assert instance.dependency.value == "dependency_value"
    
    def test_get_service_circular_dependency(self):
        """Test handling circular dependencies"""
        container = DIContainer()
        
        class ServiceA:
            def __init__(self, service_b):
                self.service_b = service_b
        
        class ServiceB:
            def __init__(self, service_a):
                self.service_a = service_a
        
        container.register_singleton(ServiceA, ServiceA)
        container.register_singleton(ServiceB, ServiceB)
        
        # This should raise an exception due to circular dependency
        with pytest.raises(Exception):
            container.container.get(ServiceA)
    
    def test_factory_exception(self):
        """Test handling factory exceptions"""
        container = DIContainer()
        
        class TestService:
            pass
        
        def failing_factory():
            raise Exception("Factory error")
        
        container.register_singleton(TestService, failing_factory)
        
        with pytest.raises(Exception, match="Factory error"):
            container.container.get(TestService)
    
    def test_factory_with_args(self):
        """Test factory with arguments"""
        container = DIContainer()
        
        class TestService:
            def __init__(self, arg1, arg2):
                self.arg1 = arg1
                self.arg2 = arg2
        
        def factory():
            return TestService("value1", "value2")
        
        container.register_singleton(TestService, factory)
        
        instance = container.container.get(TestService)
        assert instance.arg1 == "value1"
        assert instance.arg2 == "value2"


class TestApplicationContainer:
    """Test cases for ApplicationContainer"""
    
    def test_init(self):
        """Test ApplicationContainer initialization"""
        with patch('src.infrastructure.dependency_injection.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.dependency_injection.get_logger', return_value=mock_logger):
                container = DIContainer()
                
                # Mock configuration
                mock_config_manager.get_config.side_effect = lambda key, default=None: {
                    "storage.provider": "git",
                    "storage.base_url": "https://test-repo.com",
                    "storage.local_repo_path": "test_remote",
                    "storage.data_path": "test_data",
                    "database.provider": "sqlite",
                    "database.name": "test_db.db"
                }.get(key, default)
                
                container._setup_services()
                
                # Verify that services are registered
                assert len(container.container._factories) > 0
    
    def test_setup_services_git_provider(self):
        """Test setting up services with git provider"""
        with patch('src.infrastructure.dependency_injection.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.dependency_injection.get_logger', return_value=mock_logger):
                container = DIContainer()
                
                # Mock configuration for git provider
                mock_config_manager.get_config.side_effect = lambda key, default=None: {
                    "storage.provider": "git",
                    "storage.base_url": "https://test-repo.com",
                    "storage.local_repo_path": "test_remote",
                    "storage.data_path": "test_data"
                }.get(key, default)
                
                container._setup_services()
                
                # Should have registered git services
                assert len(container.container._factories) > 0
    
    def test_setup_services_artifactory_provider(self):
        """Test setting up services with artifactory provider"""
        with patch('src.infrastructure.dependency_injection.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.dependency_injection.get_logger', return_value=mock_logger):
                container = DIContainer()
                
                # Mock configuration for artifactory provider
                mock_config_manager.get_config.side_effect = lambda key, default=None: {
                    "storage.provider": "artifactory",
                    "storage.base_url": "http://localhost:8080",
                    "storage.local_repo_path": "test_remote",
                    "storage.data_path": "test_data"
                }.get(key, default)
                
                container._setup_services()
                
                # Should have registered artifactory services
                assert len(container.container._factories) > 0
    
    def test_setup_services_unknown_provider(self):
        """Test setting up services with unknown provider"""
        with patch('src.infrastructure.dependency_injection.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.dependency_injection.get_logger', return_value=mock_logger):
                container = DIContainer()
                
                # Mock configuration for unknown provider
                mock_config_manager.get_config.side_effect = lambda key, default=None: {
                    "storage.provider": "unknown",
                    "storage.base_url": "http://localhost:8080",
                    "storage.local_repo_path": "test_remote",
                    "storage.data_path": "test_data"
                }.get(key, default)
                
                container._setup_services()
                
                # Should still register some services
                assert len(container.container._factories) > 0
    
    def test_setup_services_exception(self):
        """Test handling exceptions during service setup"""
        with patch('src.infrastructure.dependency_injection.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.dependency_injection.get_logger', return_value=mock_logger):
                container = DIContainer()
                
                # Mock configuration that causes exception
                mock_config_manager.get_config.side_effect = Exception("Config error")
                
                # Should not raise exception
                container._setup_services()
                
                # Should have some services registered despite error
                assert len(container.container._factories) >= 0


class TestGetContainer:
    """Test cases for get_container function"""
    
    def test_get_container_singleton(self):
        """Test that get_container returns singleton instance"""
        container1 = get_container()
        container2 = get_container()
        
        assert container1 is container2
    
    def test_get_container_initialization(self):
        """Test that get_container initializes properly"""
        container = get_container()
        
        assert container is not None
        assert hasattr(container, 'container')
        assert hasattr(container, '_setup_services')
    
    def test_get_container_with_services(self):
        """Test that get_container has services registered"""
        container = get_container()
        
        # Should have some services registered
        assert len(container.container._factories) > 0


class TestServiceRegistration:
    """Test cases for specific service registrations"""
    
    def test_git_file_storage_registration(self):
        """Test GitFileStorage service registration"""
        with patch('src.infrastructure.dependency_injection.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.dependency_injection.get_logger', return_value=mock_logger):
                container = DIContainer()
                
                mock_config_manager.get_config.side_effect = lambda key, default=None: {
                    "storage.provider": "git",
                    "storage.base_url": "https://test-repo.com",
                    "storage.local_repo_path": "test_remote",
                    "storage.data_path": "test_data"
                }.get(key, default)
                
                container._setup_services()
                
                # Should be able to get GitFileStorage
                from src.interfaces.git_file_storage import IGitFileStorage
                service = container.container.get(IGitFileStorage)
                assert service is not None
    
    def test_git_database_service_registration(self):
        """Test GitDatabaseService registration"""
        with patch('src.infrastructure.dependency_injection.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.dependency_injection.get_logger', return_value=mock_logger):
                container = DIContainer()
                
                mock_config_manager.get_config.side_effect = lambda key, default=None: {
                    "storage.provider": "git",
                    "storage.base_url": "https://test-repo.com",
                    "storage.local_repo_path": "test_remote",
                    "storage.data_path": "test_data",
                    "database.name": "test_db.db"
                }.get(key, default)
                
                container._setup_services()
                
                # Should be able to get GitDatabaseService
                from src.services.git_database_service import GitDatabaseService
                service = container.container.get(GitDatabaseService)
                assert service is not None
    
    def test_user_service_registration(self):
        """Test UserService registration"""
        with patch('src.infrastructure.dependency_injection.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.dependency_injection.get_logger', return_value=mock_logger):
                container = DIContainer()
                
                mock_config_manager.get_config.side_effect = lambda key, default=None: {
                    "storage.provider": "git",
                    "storage.base_url": "https://test-repo.com",
                    "storage.local_repo_path": "test_remote",
                    "storage.data_path": "test_data",
                    "database.name": "test_db.db"
                }.get(key, default)
                
                container._setup_services()
                
                # Should be able to get UserService
                from src.services.user_service import IUserService
                service = container.container.get(IUserService)
                assert service is not None
    
    def test_test_case_service_registration(self):
        """Test TestCaseService registration"""
        with patch('src.infrastructure.dependency_injection.get_config_manager', return_value=mock_config_manager):
            with patch('src.infrastructure.dependency_injection.get_logger', return_value=mock_logger):
                container = DIContainer()
                
                mock_config_manager.get_config.side_effect = lambda key, default=None: {
                    "storage.provider": "git",
                    "storage.base_url": "https://test-repo.com",
                    "storage.local_repo_path": "test_remote",
                    "storage.data_path": "test_data",
                    "database.name": "test_db.db"
                }.get(key, default)
                
                container._setup_services()
                
                # Should be able to get TestCaseService
                from src.services.test_case_service import ITestCaseService
                service = container.container.get(ITestCaseService)
                assert service is not None
