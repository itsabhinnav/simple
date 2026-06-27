"""
Integration Tests for Authentication Endpoints

This module provides comprehensive integration tests for user authentication
including signup and login functionality.
"""

import pytest
import json
import tempfile
import os
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

# Add backend to Python path
import sys
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from tests import TestDatabase, mock_config_manager, mock_logger
from werkzeug.security import generate_password_hash
import base64

# Create a simple app factory function
def create_test_app():
    """Create a test Flask app"""
    from src.controllers.user_controller import create_user_blueprint
    from src.controllers.auth_controller import create_auth_blueprint
    from src.services.user_service import UserService
    from src.repositories.user_repository import UserRepository
    
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    # Mock database service for testing
    mock_db_service = Mock()
    mock_db_service.execute_query.return_value = {
        "success": True,
        "data": [],
        "lastrowid": 1
    }
    
    # Create user repository and service
    user_repository = UserRepository(mock_db_service)
    user_service = UserService(user_repository)
    
    # Register blueprints
    auth_bp = create_auth_blueprint(user_service)
    user_bp = create_user_blueprint(user_service)
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    
    return app


class TestAuthEndpoints:
    """Test cases for authentication endpoints"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app with real database"""
        # Create temporary database directory
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test.db"
        
        # Create database with proper schema
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Create users table with all required fields including git_token_encrypted
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                secret_key_hash TEXT,
                git_token_encrypted TEXT,
                first_name TEXT,
                last_name TEXT,
                role TEXT DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create test user
        password_hash = generate_password_hash("testpass123")
        secret_key_hash = generate_password_hash("secret123")
        git_token = base64.b64encode("test_git_token_12345".encode('utf-8')).decode('utf-8')
        
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, secret_key_hash, git_token_encrypted, role, first_name, last_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ("existinguser", "existing@test.com", password_hash, secret_key_hash, git_token, "user", "Existing", "User"))
        
        conn.commit()
        conn.close()
        
        # Create test app with real database
        from src.services.local_database_service import LocalDatabaseService
        from src.repositories.user_repository import UserRepository
        from src.services.user_service import UserService
        from src.controllers.user_controller import create_user_blueprint
        from src.controllers.auth_controller import create_auth_blueprint
        
        app = Flask(__name__)
        app.config['TESTING'] = True
        
        # Create real database service and override the db path
        db_service = LocalDatabaseService()
        # Override the database path to use our test database
        db_service.local_db_path = Path(db_path)
        
        # Override in DI container so controllers using get_hybrid_database_service point to this test db
        from src.infrastructure.dependency_injection import get_container
        from src.services.hybrid_database_service import HybridDatabaseService
        container = get_container().container
        container.register_instance(LocalDatabaseService, db_service)
        
        # Also ensure HybridDatabaseService uses the overridden LocalDatabaseService
        if container.is_registered(HybridDatabaseService):
            hybrid_service = container.get(HybridDatabaseService)
            hybrid_service.local_db = db_service
            
        # Create user repository and service
        user_repository = UserRepository(db_service)
        user_service = UserService(user_repository)
        
        # Register blueprints
        auth_bp = create_auth_blueprint(user_service)
        user_bp = create_user_blueprint(user_service)
        
        app.register_blueprint(auth_bp)
        app.register_blueprint(user_bp)
        
        yield app
        
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except:
                pass
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_signup_success(self, client):
        """Test successful user signup"""
        signup_data = {
            "username": "newuser",
            "email": "newuser@test.com",
            "password": "password123456",
            "secret_key": "secret1234567",
            "git_token": "git_token_for_newuser_123456789",
            "first_name": "New",
            "last_name": "User",
            "role": "user"
        }
        
        response = client.post('/api/auth/signup', json=signup_data, content_type='application/json')
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'token' in data['data']
        assert 'user' in data['data']
        assert data['data']['user']['username'] == "newuser"
        assert data['data']['user']['email'] == "newuser@test.com"
        # Password hash should not be exposed
        assert 'password_hash' not in data['data']['user']
        assert 'password' not in data['data']['user']

    def test_signup_success_without_git_token(self, client):
        """Test successful user signup without providing a Git token"""
        signup_data = {
            "username": "newuser_notoken",
            "email": "newuser_notoken@test.com",
            "password": "password123456",
            "secret_key": "secret1234567",
            "first_name": "NoToken",
            "last_name": "User",
            "role": "user"
        }
        
        response = client.post('/api/auth/signup', json=signup_data, content_type='application/json')
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'token' in data['data']
        assert 'user' in data['data']
        assert data['data']['user']['username'] == "newuser_notoken"
        assert data['data']['user']['email'] == "newuser_notoken@test.com"
        assert 'git_token' not in data['data']['user']
        assert 'git_token_encrypted' not in data['data']['user']
    
    def test_signup_duplicate_username(self, client):
        """Test signup with duplicate username"""
        signup_data = {
            "username": "existinguser",
            "email": "duplicate@test.com",
            "password": "password123",
            "secret_key": "secret123",
            "git_token": "git_token_for_duplicate_user_123456789",
            "first_name": "Duplicate",
            "last_name": "User"
        }
        
        response = client.post('/api/auth/signup', json=signup_data, content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert "already taken" in data['message'].lower()
    
    def test_signup_invalid_data(self, client):
        """Test signup with invalid data"""
        # Missing required fields
        signup_data = {
            "username": "invaliduser",
            "email": "invalid@test.com"
            # Missing password, secret_key
        }
        
        response = client.post('/api/auth/signup', json=signup_data, content_type='application/json')
        
        assert response.status_code in [400, 422]  # Pydantic validation error
    
    def test_login_success(self, client):
        """Test successful user login"""
        login_data = {
            "username": "existinguser",
            "password": "testpass123"
        }
        
        response = client.post('/api/auth/login', json=login_data, content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'token' in data['data']
        assert 'user' in data['data']
        assert data['data']['user']['username'] == "existinguser"
    
    def test_login_invalid_username(self, client):
        """Test login with invalid username"""
        login_data = {
            "username": "nonexistent",
            "password": "password123"
        }
        
        response = client.post('/api/auth/login', json=login_data, content_type='application/json')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False
        # Check for one of the expected error messages
        assert "incorrect" in data['message'].lower() or "invalid credentials" in data['message'].lower()
    
    def test_login_invalid_password(self, client):
        """Test login with invalid password"""
        login_data = {
            "username": "existinguser",
            "password": "wrongpassword"
        }
        
        response = client.post('/api/auth/login', json=login_data, content_type='application/json')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False
        # Check for one of the expected error messages
        assert "incorrect" in data['message'].lower() or "invalid credentials" in data['message'].lower()
    
    def test_login_and_signup_flow(self, client):
        """Test complete flow: signup then login"""
        # First, signup a new user
        signup_data = {
            "username": "flowuser",
            "email": "flowuser@test.com",
            "password": "flowpass123456",
            "secret_key": "secret1234567",
            "git_token": "git_token_for_flowuser_123456789",
            "first_name": "Flow",
            "last_name": "User"
        }
        
        response = client.post('/api/auth/signup', json=signup_data, content_type='application/json')
        assert response.status_code == 201
        signup_data = json.loads(response.data)
        assert signup_data['success'] is True
        signup_token = signup_data['data']['token']
        
        # Now login with the same credentials
        login_data = {
            "username": "flowuser",
            "password": "flowpass123456"
        }
        
        response = client.post('/api/auth/login', json=login_data, content_type='application/json')
        assert response.status_code == 200
        login_data = json.loads(response.data)
        assert login_data['success'] is True
        login_token = login_data['data']['token']
        
        # Both tokens should be present
        assert signup_token is not None
        assert login_token is not None
    
    def test_signup_sql_injection_attempt(self, client):
        """Test signup with SQL injection attempt in username"""
        signup_data = {
            "username": "admin'; DROP TABLE users; --",
            "email": "sql@test.com",
            "password": "password123",
            "secret_key": "secret123",
            "git_token": "git_token_for_sql_user_123456789"
        }
        
        # This should either fail validation or the quotes should be escaped
        response = client.post('/api/auth/signup', json=signup_data, content_type='application/json')
        
        # Should either succeed with escaped data or fail safely
        # The system should not execute the SQL injection
        assert response.status_code in [201, 400, 500]
        
        # If it succeeds, verify the data is stored correctly (not executed as SQL)
        if response.status_code == 201:
            data = json.loads(response.data)
            user = data['data']['user']
            assert "'" in user['username']  # The SQL injection string should be stored as-is, not executed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

