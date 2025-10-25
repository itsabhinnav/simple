"""
Unit Tests for User Service and Repository

This module provides comprehensive unit tests for user-related services
to achieve 100% C0 and C1 coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Optional

from src.services.user_service import UserService, IUserService
from src.repositories.user_repository import UserRepository, IUserRepository
from tests import create_test_user_data


class TestUserRepository:
    """Test cases for UserRepository"""
    
    def test_init(self):
        """Test repository initialization"""
        mock_db_service = Mock()
        repository = UserRepository(mock_db_service)
        
        assert repository.database_service == mock_db_service
    
    def test_find_all_success(self):
        """Test successful retrieval of all users"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": True,
            "data": [
                {"id": 1, "username": "user1", "email": "user1@test.com"},
                {"id": 2, "username": "user2", "email": "user2@test.com"}
            ]
        }
        
        repository = UserRepository(mock_db_service)
        result = repository.find_all()
        
        assert len(result) == 2
        assert result[0]["username"] == "user1"
        assert result[1]["username"] == "user2"
        mock_db_service.execute_query.assert_called_once()
    
    def test_find_all_empty(self):
        """Test retrieval when no users exist"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": True,
            "data": []
        }
        
        repository = UserRepository(mock_db_service)
        result = repository.find_all()
        
        assert result == []
    
    def test_find_all_query_failure(self):
        """Test retrieval when query fails"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": False,
            "error": "Database error"
        }
        
        repository = UserRepository(mock_db_service)
        result = repository.find_all()
        
        assert result == []
    
    def test_find_by_id_success(self):
        """Test successful retrieval by ID"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": True,
            "data": [{"id": 1, "username": "user1", "email": "user1@test.com"}]
        }
        
        repository = UserRepository(mock_db_service)
        result = repository.find_by_id(1)
        
        assert result is not None
        assert result["username"] == "user1"
        mock_db_service.execute_query.assert_called_once()
    
    def test_find_by_id_not_found(self):
        """Test retrieval by ID when user doesn't exist"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": True,
            "data": []
        }
        
        repository = UserRepository(mock_db_service)
        result = repository.find_by_id(999)
        
        assert result is None
    
    def test_find_by_username_success(self):
        """Test successful retrieval by username"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": True,
            "data": [{"id": 1, "username": "user1", "email": "user1@test.com"}]
        }
        
        repository = UserRepository(mock_db_service)
        result = repository.find_by_username("user1")
        
        assert result is not None
        assert result["username"] == "user1"
        mock_db_service.execute_query.assert_called_once()
    
    def test_find_by_username_not_found(self):
        """Test retrieval by username when user doesn't exist"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": True,
            "data": []
        }
        
        repository = UserRepository(mock_db_service)
        result = repository.find_by_username("nonexistent")
        
        assert result is None
    
    def test_create_success(self):
        """Test successful user creation"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": True,
            "data": [],
            "row_count": 1
        }
        
        repository = UserRepository(mock_db_service)
        user_data = create_test_user_data()
        result = repository.create(user_data)
        
        assert result is not None
        assert result["username"] == user_data["username"]
        assert result["email"] == user_data["email"]
        mock_db_service.execute_query.assert_called_once()
    
    def test_create_failure(self):
        """Test user creation failure"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": False,
            "error": "Constraint violation"
        }
        
        repository = UserRepository(mock_db_service)
        user_data = create_test_user_data()
        result = repository.create(user_data)
        
        assert result is None
    
    def test_update_success(self):
        """Test successful user update"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": True,
            "data": [],
            "row_count": 1
        }
        
        repository = UserRepository(mock_db_service)
        update_data = {"email": "newemail@test.com"}
        result = repository.update(1, update_data)
        
        assert result is not None
        assert result["email"] == "newemail@test.com"
        mock_db_service.execute_query.assert_called_once()
    
    def test_update_not_found(self):
        """Test user update when user doesn't exist"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": True,
            "data": [],
            "row_count": 0
        }
        
        repository = UserRepository(mock_db_service)
        update_data = {"email": "newemail@test.com"}
        result = repository.update(999, update_data)
        
        assert result is None
    
    def test_delete_success(self):
        """Test successful user deletion"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": True,
            "data": [],
            "row_count": 1
        }
        
        repository = UserRepository(mock_db_service)
        result = repository.delete(1)
        
        assert result is True
        mock_db_service.execute_query.assert_called_once()
    
    def test_delete_not_found(self):
        """Test user deletion when user doesn't exist"""
        mock_db_service = Mock()
        mock_db_service.execute_query.return_value = {
            "success": True,
            "data": [],
            "row_count": 0
        }
        
        repository = UserRepository(mock_db_service)
        result = repository.delete(999)
        
        assert result is False


class TestUserService:
    """Test cases for UserService"""
    
    def test_init(self):
        """Test service initialization"""
        mock_repository = Mock()
        service = UserService(mock_repository)
        
        assert service.user_repository == mock_repository
    
    def test_get_all_users_success(self):
        """Test successful retrieval of all users"""
        mock_repository = Mock()
        mock_users = [
            {"id": 1, "username": "user1", "email": "user1@test.com", "role": "user"},
            {"id": 2, "username": "user2", "email": "user2@test.com", "role": "admin"}
        ]
        mock_repository.find_all.return_value = mock_users
        
        service = UserService(mock_repository)
        result = service.get_all_users()
        
        assert len(result) == 2
        assert result[0]["is_admin"] is False
        assert result[1]["is_admin"] is True
        assert result[0]["display_name"] == "user1"
        assert result[1]["display_name"] == "user2"
    
    def test_get_all_users_exception(self):
        """Test exception handling in get_all_users"""
        mock_repository = Mock()
        mock_repository.find_all.side_effect = Exception("Database error")
        
        service = UserService(mock_repository)
        
        with pytest.raises(Exception, match="Service error: Failed to get users"):
            service.get_all_users()
    
    def test_get_user_by_id_success(self):
        """Test successful retrieval by ID"""
        mock_repository = Mock()
        mock_user = {
            "id": 1,
            "username": "user1",
            "email": "user1@test.com",
            "role": "admin",
            "first_name": "John",
            "last_name": "Doe"
        }
        mock_repository.find_by_id.return_value = mock_user
        
        service = UserService(mock_repository)
        result = service.get_user_by_id(1)
        
        assert result is not None
        assert result["is_admin"] is True
        assert result["display_name"] == "John Doe"
    
    def test_get_user_by_id_not_found(self):
        """Test retrieval by ID when user doesn't exist"""
        mock_repository = Mock()
        mock_repository.find_by_id.return_value = None
        
        service = UserService(mock_repository)
        result = service.get_user_by_id(999)
        
        assert result is None
    
    def test_get_user_by_id_exception(self):
        """Test exception handling in get_user_by_id"""
        mock_repository = Mock()
        mock_repository.find_by_id.side_effect = Exception("Database error")
        
        service = UserService(mock_repository)
        
        with pytest.raises(Exception, match="Service error: Failed to get user"):
            service.get_user_by_id(1)
    
    def test_get_user_by_username_success(self):
        """Test successful retrieval by username"""
        mock_repository = Mock()
        mock_user = {
            "id": 1,
            "username": "user1",
            "email": "user1@test.com",
            "role": "user"
        }
        mock_repository.find_by_username.return_value = mock_user
        
        service = UserService(mock_repository)
        result = service.get_user_by_username("user1")
        
        assert result is not None
        assert result["is_admin"] is False
        assert result["display_name"] == "user1"
    
    def test_get_user_by_username_not_found(self):
        """Test retrieval by username when user doesn't exist"""
        mock_repository = Mock()
        mock_repository.find_by_username.return_value = None
        
        service = UserService(mock_repository)
        result = service.get_user_by_username("nonexistent")
        
        assert result is None
    
    def test_get_user_by_username_exception(self):
        """Test exception handling in get_user_by_username"""
        mock_repository = Mock()
        mock_repository.find_by_username.side_effect = Exception("Database error")
        
        service = UserService(mock_repository)
        
        with pytest.raises(Exception, match="Service error: Failed to get user by username"):
            service.get_user_by_username("user1")
    
    def test_create_user_success(self):
        """Test successful user creation"""
        mock_repository = Mock()
        mock_created_user = {
            "id": 1,
            "username": "newuser",
            "email": "newuser@test.com",
            "role": "user"
        }
        mock_repository.create.return_value = mock_created_user
        
        service = UserService(mock_repository)
        user_data = create_test_user_data()
        result = service.create_user(user_data)
        
        assert result is not None
        assert result["is_admin"] is False
        assert result["display_name"] == "newuser"
        mock_repository.create.assert_called_once()
    
    def test_create_user_exception(self):
        """Test exception handling in create_user"""
        mock_repository = Mock()
        mock_repository.create.side_effect = Exception("Database error")
        
        service = UserService(mock_repository)
        user_data = create_test_user_data()
        
        with pytest.raises(Exception, match="Service error: Failed to create user"):
            service.create_user(user_data)
    
    def test_update_user_success(self):
        """Test successful user update"""
        mock_repository = Mock()
        mock_updated_user = {
            "id": 1,
            "username": "user1",
            "email": "newemail@test.com",
            "role": "admin"
        }
        mock_repository.update.return_value = mock_updated_user
        
        service = UserService(mock_repository)
        update_data = {"email": "newemail@test.com", "role": "admin"}
        result = service.update_user(1, update_data)
        
        assert result is not None
        assert result["is_admin"] is True
        assert result["display_name"] == "user1"
        mock_repository.update.assert_called_once_with(1, update_data)
    
    def test_update_user_not_found(self):
        """Test user update when user doesn't exist"""
        mock_repository = Mock()
        mock_repository.update.return_value = None
        
        service = UserService(mock_repository)
        update_data = {"email": "newemail@test.com"}
        result = service.update_user(999, update_data)
        
        assert result is None
    
    def test_update_user_exception(self):
        """Test exception handling in update_user"""
        mock_repository = Mock()
        mock_repository.update.side_effect = Exception("Database error")
        
        service = UserService(mock_repository)
        update_data = {"email": "newemail@test.com"}
        
        with pytest.raises(Exception, match="Service error: Failed to update user"):
            service.update_user(1, update_data)
    
    def test_delete_user_success(self):
        """Test successful user deletion"""
        mock_repository = Mock()
        mock_repository.delete.return_value = True
        
        service = UserService(mock_repository)
        result = service.delete_user(1)
        
        assert result is True
        mock_repository.delete.assert_called_once_with(1)
    
    def test_delete_user_not_found(self):
        """Test user deletion when user doesn't exist"""
        mock_repository = Mock()
        mock_repository.delete.return_value = False
        
        service = UserService(mock_repository)
        result = service.delete_user(999)
        
        assert result is False
    
    def test_delete_user_exception(self):
        """Test exception handling in delete_user"""
        mock_repository = Mock()
        mock_repository.delete.side_effect = Exception("Database error")
        
        service = UserService(mock_repository)
        
        with pytest.raises(Exception, match="Service error: Failed to delete user"):
            service.delete_user(1)
    
    def test_display_name_with_names(self):
        """Test display name generation with first and last names"""
        mock_repository = Mock()
        mock_user = {
            "id": 1,
            "username": "user1",
            "first_name": "John",
            "last_name": "Doe",
            "role": "user"
        }
        mock_repository.find_by_id.return_value = mock_user
        
        service = UserService(mock_repository)
        result = service.get_user_by_id(1)
        
        assert result["display_name"] == "John Doe"
    
    def test_display_name_with_first_name_only(self):
        """Test display name generation with first name only"""
        mock_repository = Mock()
        mock_user = {
            "id": 1,
            "username": "user1",
            "first_name": "John",
            "last_name": None,
            "role": "user"
        }
        mock_repository.find_by_id.return_value = mock_user
        
        service = UserService(mock_repository)
        result = service.get_user_by_id(1)
        
        assert result["display_name"] == "John"
    
    def test_display_name_with_last_name_only(self):
        """Test display name generation with last name only"""
        mock_repository = Mock()
        mock_user = {
            "id": 1,
            "username": "user1",
            "first_name": None,
            "last_name": "Doe",
            "role": "user"
        }
        mock_repository.find_by_id.return_value = mock_user
        
        service = UserService(mock_repository)
        result = service.get_user_by_id(1)
        
        assert result["display_name"] == "Doe"
    
    def test_display_name_fallback_to_username(self):
        """Test display name fallback to username"""
        mock_repository = Mock()
        mock_user = {
            "id": 1,
            "username": "user1",
            "first_name": None,
            "last_name": None,
            "role": "user"
        }
        mock_repository.find_by_id.return_value = mock_user
        
        service = UserService(mock_repository)
        result = service.get_user_by_id(1)
        
        assert result["display_name"] == "user1"


class TestIUserService:
    """Test cases for IUserService interface"""
    
    def test_interface_methods_exist(self):
        """Test that interface defines all required methods"""
        assert hasattr(IUserService, 'get_all_users')
        assert hasattr(IUserService, 'get_user_by_id')
        assert hasattr(IUserService, 'get_user_by_username')
        assert hasattr(IUserService, 'create_user')
        assert hasattr(IUserService, 'update_user')
        assert hasattr(IUserService, 'delete_user')
    
    def test_interface_is_abstract(self):
        """Test that interface cannot be instantiated directly"""
        with pytest.raises(TypeError):
            IUserService()


class TestIUserRepository:
    """Test cases for IUserRepository interface"""
    
    def test_interface_methods_exist(self):
        """Test that interface defines all required methods"""
        assert hasattr(IUserRepository, 'find_all')
        assert hasattr(IUserRepository, 'find_by_id')
        assert hasattr(IUserRepository, 'find_by_username')
        assert hasattr(IUserRepository, 'create')
        assert hasattr(IUserRepository, 'update')
        assert hasattr(IUserRepository, 'delete')
    
    def test_interface_is_abstract(self):
        """Test that interface cannot be instantiated directly"""
        with pytest.raises(TypeError):
            IUserRepository()
