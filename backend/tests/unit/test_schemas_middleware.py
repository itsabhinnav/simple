"""
Unit Tests for Schemas and Middleware

This module provides comprehensive unit tests for schemas and middleware components
to achieve 100% C0 and C1 coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from flask import Flask, request, jsonify

from src.schemas.test_case_schema import TestCaseSchema, TestCaseCreateSchema
from src.schemas.user_schema import UserSchema, UserCreateSchema
from src.schemas.api_schema import DatabaseQuerySchema, DatabaseInfoSchema
from src.middleware.error_handlers import setup_error_handlers, setup_request_validation, setup_api_documentation
from tests import create_test_case_data, create_test_user_data


class TestTestCaseSchema:
    """Test cases for TestCaseSchema"""
    
    def test_test_case_schema_valid_data(self):
        """Test TestCaseSchema with valid data"""
        test_data = create_test_case_data()
        test_data.update({
            "id": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        })
        
        schema = TestCaseSchema(**test_data)
        
        assert schema.test_case_id == test_data["test_case_id"]
        assert schema.test_name == test_data["test_name"]
        assert schema.feature == test_data["feature"]
        assert schema.test_type == test_data["test_type"]
        assert schema.description == test_data["description"]
        assert schema.id == 1
        assert schema.created_at is not None
        assert schema.updated_at is not None
    
    def test_test_case_schema_minimal_data(self):
        """Test TestCaseSchema with minimal required data"""
        minimal_data = {
            "test_case_id": "TC001",
            "test_name": "Test Case"
        }
        
        schema = TestCaseSchema(**minimal_data)
        
        assert schema.test_case_id == "TC001"
        assert schema.test_name == "Test Case"
        assert schema.feature is None
        assert schema.test_type is None
        assert schema.description is None
        assert schema.id is None
        assert schema.created_at is None
        assert schema.updated_at is None
    
    def test_test_case_schema_validation(self):
        """Test TestCaseSchema validation"""
        # Test with invalid data
        with pytest.raises(ValueError):
            TestCaseSchema(test_case_id="", test_name="Test")  # Empty test_case_id
    
    def test_test_case_create_schema(self):
        """Test TestCaseCreateSchema"""
        test_data = create_test_case_data()
        
        schema = TestCaseCreateSchema(**test_data)
        
        assert schema.test_case_id == test_data["test_case_id"]
        assert schema.test_name == test_data["test_name"]
        assert schema.feature == test_data["feature"]
        assert schema.test_type == test_data["test_type"]
        assert schema.description == test_data["description"]
    
    def test_test_case_create_schema_validation(self):
        """Test TestCaseCreateSchema validation"""
        # Test with missing required field
        with pytest.raises(ValueError):
            TestCaseCreateSchema(test_case_id="TC001")  # Missing test_name


class TestUserSchema:
    """Test cases for UserSchema"""
    
    def test_user_schema_valid_data(self):
        """Test UserSchema with valid data"""
        user_data = create_test_user_data()
        user_data.update({
            "id": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        })
        
        schema = UserSchema(**user_data)
        
        assert schema.username == user_data["username"]
        assert schema.email == user_data["email"]
        assert schema.first_name == user_data["first_name"]
        assert schema.last_name == user_data["last_name"]
        assert schema.role == user_data["role"]
        assert schema.id == 1
        assert schema.created_at is not None
        assert schema.updated_at is not None
    
    def test_user_schema_minimal_data(self):
        """Test UserSchema with minimal required data"""
        minimal_data = {
            "username": "testuser",
            "email": "test@example.com"
        }
        
        schema = UserSchema(**minimal_data)
        
        assert schema.username == "testuser"
        assert schema.email == "test@example.com"
        assert schema.first_name is None
        assert schema.last_name is None
        assert schema.role == "user"  # default value
        assert schema.id is None
        assert schema.created_at is None
        assert schema.updated_at is None
    
    def test_user_create_schema(self):
        """Test UserCreateSchema"""
        user_data = create_test_user_data()
        
        schema = UserCreateSchema(**user_data)
        
        assert schema.username == user_data["username"]
        assert schema.email == user_data["email"]
        assert schema.first_name == user_data["first_name"]
        assert schema.last_name == user_data["last_name"]
        assert schema.role == user_data["role"]
    
    def test_user_create_schema_validation(self):
        """Test UserCreateSchema validation"""
        # Test with invalid email
        with pytest.raises(ValueError):
            UserCreateSchema(username="testuser", email="invalid-email")


class TestAPISchema:
    """Test cases for API schemas"""
    
    def test_database_query_schema(self):
        """Test DatabaseQuerySchema"""
        schema = DatabaseQuerySchema(query="SELECT * FROM users")
        
        assert schema.query == "SELECT * FROM users"
        assert schema.environment == "default"  # default value
    
    def test_database_query_schema_custom_environment(self):
        """Test DatabaseQuerySchema with custom environment"""
        schema = DatabaseQuerySchema(query="SELECT * FROM users", environment="test")
        
        assert schema.query == "SELECT * FROM users"
        assert schema.environment == "test"
    
    def test_database_query_schema_validation(self):
        """Test DatabaseQuerySchema validation"""
        # Test with empty query
        with pytest.raises(ValueError):
            DatabaseQuerySchema(query="")
        
        # Test with too long environment
        with pytest.raises(ValueError):
            DatabaseQuerySchema(query="SELECT * FROM users", environment="x" * 51)
    
    def test_database_info_schema(self):
        """Test DatabaseInfoSchema"""
        schema = DatabaseInfoSchema(
            database_name="test_db",
            file_path="/path/to/db",
            file_size=1024,
            last_modified=1234567890,
            tables=["users", "test_cases"],
            table_count=2
        )
        
        assert schema.database_name == "test_db"
        assert schema.file_path == "/path/to/db"
        assert schema.file_size == 1024
        assert schema.last_modified == 1234567890
        assert schema.tables == ["users", "test_cases"]
        assert schema.table_count == 2


class TestErrorHandlers:
    """Test cases for error handlers middleware"""
    
    def test_setup_error_handlers(self):
        """Test error handlers setup"""
        app = Flask(__name__)
        
        setup_error_handlers(app)
        
        # Test 404 handler
        with app.test_client() as client:
            response = client.get('/nonexistent')
            assert response.status_code == 404
            data = response.get_json()
            assert 'error' in data
    
    def test_setup_error_handlers_500(self):
        """Test 500 error handler"""
        app = Flask(__name__)
        
        @app.route('/error')
        def error_route():
            raise Exception("Test error")
        
        setup_error_handlers(app)
        
        with app.test_client() as client:
            response = client.get('/error')
            assert response.status_code == 500
            data = response.get_json()
            assert 'error' in data
    
    def test_setup_error_handlers_405(self):
        """Test 405 error handler"""
        app = Flask(__name__)
        
        @app.route('/test', methods=['GET'])
        def test_route():
            return "OK"
        
        setup_error_handlers(app)
        
        with app.test_client() as client:
            response = client.post('/test')  # POST not allowed
            assert response.status_code == 405
            data = response.get_json()
            assert 'error' in data
    
    def test_setup_request_validation(self):
        """Test request validation setup"""
        app = Flask(__name__)
        
        @app.route('/api/test', methods=['POST'])
        def test_route():
            return jsonify({"success": True})
        
        setup_request_validation(app)
        
        with app.test_client() as client:
            # Test with valid JSON
            response = client.post('/api/test', 
                                 json={"test": "data"},
                                 content_type='application/json')
            assert response.status_code == 200
            
            # Test with invalid JSON
            response = client.post('/api/test',
                                 data="invalid json",
                                 content_type='application/json')
            assert response.status_code == 400
            data = response.get_json()
            assert 'error' in data
    
    def test_setup_api_documentation(self):
        """Test API documentation setup"""
        app = Flask(__name__)
        
        @app.route('/api/test', methods=['GET'])
        def test_route():
            return jsonify({"success": True})
        
        setup_api_documentation(app)
        
        with app.test_client() as client:
            response = client.get('/api/docs')
            assert response.status_code == 200
            data = response.get_json()
            assert 'endpoints' in data
            assert 'version' in data
            assert 'title' in data


class TestMiddlewareIntegration:
    """Integration tests for middleware components"""
    
    def test_all_middleware_together(self):
        """Test all middleware components working together"""
        app = Flask(__name__)
        
        @app.route('/api/test', methods=['GET', 'POST'])
        def test_route():
            if request.method == 'POST':
                return jsonify({"success": True, "data": request.get_json()})
            return jsonify({"success": True})
        
        # Setup all middleware
        setup_error_handlers(app)
        setup_request_validation(app)
        setup_api_documentation(app)
        
        with app.test_client() as client:
            # Test GET request
            response = client.get('/api/test')
            assert response.status_code == 200
            
            # Test POST request with valid JSON
            response = client.post('/api/test',
                                 json={"test": "data"},
                                 content_type='application/json')
            assert response.status_code == 200
            
            # Test POST request with invalid JSON
            response = client.post('/api/test',
                                 data="invalid json",
                                 content_type='application/json')
            assert response.status_code == 400
            
            # Test 404
            response = client.get('/nonexistent')
            assert response.status_code == 404
            
            # Test API docs
            response = client.get('/api/docs')
            assert response.status_code == 200
    
    def test_cors_headers(self):
        """Test CORS headers are set correctly"""
        app = Flask(__name__)
        
        @app.route('/api/test', methods=['GET', 'OPTIONS'])
        def test_route():
            return jsonify({"success": True})
        
        setup_error_handlers(app)
        
        with app.test_client() as client:
            # Test OPTIONS request
            response = client.options('/api/test')
            assert response.status_code == 200
            assert 'Access-Control-Allow-Origin' in response.headers
            assert 'Access-Control-Allow-Methods' in response.headers
            assert 'Access-Control-Allow-Headers' in response.headers
            
            # Test GET request
            response = client.get('/api/test')
            assert response.status_code == 200
            assert 'Access-Control-Allow-Origin' in response.headers


class TestSchemaValidation:
    """Test cases for schema validation edge cases"""
    
    def test_test_case_schema_edge_cases(self):
        """Test TestCaseSchema with edge case values"""
        # Test with very long strings
        long_string = "x" * 1000
        schema = TestCaseSchema(
            test_case_id="TC001",
            test_name="Test",
            description=long_string
        )
        assert schema.description == long_string
        
        # Test with special characters
        special_chars = "Test with special chars: !@#$%^&*()"
        schema = TestCaseSchema(
            test_case_id="TC001",
            test_name=special_chars
        )
        assert schema.test_name == special_chars
    
    def test_user_schema_edge_cases(self):
        """Test UserSchema with edge case values"""
        # Test with very long email
        long_email = "a" * 100 + "@example.com"
        schema = UserSchema(
            username="testuser",
            email=long_email
        )
        assert schema.email == long_email
        
        # Test with unicode characters
        unicode_name = "测试用户"
        schema = UserSchema(
            username="testuser",
            email="test@example.com",
            first_name=unicode_name
        )
        assert schema.first_name == unicode_name
    
    def test_api_schema_edge_cases(self):
        """Test API schemas with edge case values"""
        # Test with very long query
        long_query = "SELECT * FROM " + ", ".join(f"table{i}" for i in range(100))
        schema = DatabaseQuerySchema(query=long_query)
        assert schema.query == long_query
        
        # Test with empty tables list
        schema = DatabaseInfoSchema(
            database_name="test_db",
            file_path="/path/to/db",
            file_size=0,
            last_modified=0,
            tables=[],
            table_count=0
        )
        assert schema.tables == []
        assert schema.table_count == 0
