"""
Integration Tests for API Endpoints

This module provides comprehensive integration tests for the Flask API endpoints
to achieve 100% C0 and C1 coverage.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from flask import Flask
import tempfile
import os

from app_api import create_app, register_api_routes, register_legacy_routes
from tests import TestDatabase, mock_config_manager, mock_logger


class TestAPIEndpoints:
    """Test cases for API endpoints"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app"""
        with patch('app_api.get_config_manager', return_value=mock_config_manager):
            with patch('app_api.get_logger', return_value=mock_logger):
                app = create_app()
                app.config['TESTING'] = True
                return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
    
    def test_api_docs_endpoint(self, client):
        """Test API documentation endpoint"""
        response = client.get('/api/docs')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'endpoints' in data
    
    def test_databases_list_endpoint(self, client):
        """Test databases list endpoint"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.list_databases.return_value = [
                {
                    "name": "test_db",
                    "file_path": "/path/to/test.db",
                    "size": 1024,
                    "last_modified": 1234567890,
                    "status": "available"
                }
            ]
            mock_service.return_value = mock_db_service
            
            response = client.get('/api/databases?environment=default')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'databases' in data
            assert len(data['databases']) == 1
    
    def test_databases_list_endpoint_exception(self, client):
        """Test databases list endpoint with exception"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.list_databases.side_effect = Exception("Database error")
            mock_service.return_value = mock_db_service
            
            response = client.get('/api/databases?environment=default')
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_database_info_endpoint(self, client):
        """Test database info endpoint"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.get_database_info.return_value = {
                "database_name": "test_db.db",
                "file_path": "/path/to/test.db",
                "file_size": 1024,
                "last_modified": 1234567890,
                "tables": ["users", "test_cases"],
                "table_count": 2
            }
            mock_service.return_value = mock_db_service
            
            response = client.get('/api/databases/test_db/info?environment=default')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'database_name' in data
            assert data['table_count'] == 2
    
    def test_database_info_endpoint_exception(self, client):
        """Test database info endpoint with exception"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.get_database_info.side_effect = Exception("Database error")
            mock_service.return_value = mock_db_service
            
            response = client.get('/api/databases/test_db/info?environment=default')
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_database_query_endpoint_success(self, client):
        """Test database query endpoint success"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.execute_query.return_value = {
                "success": True,
                "data": [
                    {"id": 1, "name": "test"},
                    {"id": 2, "name": "test2"}
                ],
                "row_count": 2
            }
            mock_service.return_value = mock_db_service
            
            response = client.post('/api/databases/test_db/query?environment=default',
                                 json={"query": "SELECT * FROM users LIMIT 10", "fetch_all": True})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'data' in data
            assert 'columns' in data['data']
            assert 'data' in data['data']
            assert 'row_count' in data['data']
    
    def test_database_query_endpoint_missing_query(self, client):
        """Test database query endpoint with missing query"""
        response = client.post('/api/databases/test_db/query?environment=default',
                             json={"fetch_all": True})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Query parameter is required' in data['error']
    
    def test_database_query_endpoint_exception(self, client):
        """Test database query endpoint with exception"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.execute_query.side_effect = Exception("Database error")
            mock_service.return_value = mock_db_service
            
            response = client.post('/api/databases/test_db/query?environment=default',
                                 json={"query": "SELECT * FROM users", "fetch_all": True})
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_database_sync_endpoint_success(self, client):
        """Test database sync endpoint success"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.sync_database.return_value = True
            mock_service.return_value = mock_db_service
            
            response = client.post('/api/databases/test_db/sync?environment=default')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'message' in data
    
    def test_database_sync_endpoint_failure(self, client):
        """Test database sync endpoint failure"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.sync_database.return_value = False
            mock_service.return_value = mock_db_service
            
            response = client.post('/api/databases/test_db/sync?environment=default')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is False
    
    def test_database_sync_endpoint_exception(self, client):
        """Test database sync endpoint with exception"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.sync_database.side_effect = Exception("Sync error")
            mock_service.return_value = mock_db_service
            
            response = client.post('/api/databases/test_db/sync?environment=default')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_git_status_endpoint(self, client):
        """Test git status endpoint"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.get_repo_status.return_value = {
                "status": "clean",
                "branch": "main",
                "last_commit": "abc123",
                "files_changed": 0
            }
            mock_service.return_value = mock_db_service
            
            response = client.get('/api/git/status')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'data' in data
            assert data['data']['status'] == 'clean'
    
    def test_git_status_endpoint_exception(self, client):
        """Test git status endpoint with exception"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.get_repo_status.side_effect = Exception("Git error")
            mock_service.return_value = mock_db_service
            
            response = client.get('/api/git/status')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_git_pull_endpoint_success(self, client):
        """Test git pull endpoint success"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.pull_latest_changes.return_value = True
            mock_service.return_value = mock_db_service
            
            response = client.post('/api/git/pull')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'message' in data
    
    def test_git_pull_endpoint_failure(self, client):
        """Test git pull endpoint failure"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.pull_latest_changes.return_value = False
            mock_service.return_value = mock_db_service
            
            response = client.post('/api/git/pull')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is False
    
    def test_git_pull_endpoint_exception(self, client):
        """Test git pull endpoint with exception"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_db_service = Mock()
            mock_db_service.pull_latest_changes.side_effect = Exception("Pull error")
            mock_service.return_value = mock_db_service
            
            response = client.post('/api/git/pull')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_cors_headers(self, client):
        """Test CORS headers are set correctly"""
        response = client.options('/api/databases')
        assert response.status_code == 200
        assert 'Access-Control-Allow-Origin' in response.headers
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'Access-Control-Allow-Headers' in response.headers
    
    def test_error_handling_404(self, client):
        """Test 404 error handling"""
        response = client.get('/nonexistent-endpoint')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_error_handling_405(self, client):
        """Test 405 error handling"""
        response = client.delete('/health')  # DELETE not allowed on health endpoint
        assert response.status_code == 405
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_error_handling_500(self, client):
        """Test 500 error handling"""
        with patch('app_api.get_git_database_service') as mock_service:
            mock_service.side_effect = Exception("Service error")
            
            response = client.get('/api/databases')
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data


class TestAppCreation:
    """Test cases for app creation and configuration"""
    
    def test_create_app_success(self):
        """Test successful app creation"""
        with patch('app_api.get_config_manager', return_value=mock_config_manager):
            with patch('app_api.get_logger', return_value=mock_logger):
                app = create_app()
                
                assert isinstance(app, Flask)
                assert app.config['TESTING'] is False
    
    def test_create_app_with_testing_config(self):
        """Test app creation with testing configuration"""
        with patch('app_api.get_config_manager', return_value=mock_config_manager):
            with patch('app_api.get_logger', return_value=mock_logger):
                app = create_app(testing=True)
                
                assert isinstance(app, Flask)
                assert app.config['TESTING'] is True
    
    def test_register_api_routes(self):
        """Test API routes registration"""
        app = Flask(__name__)
        
        with patch('backend.app_api.get_git_database_service'):
            register_api_routes(app)
            
            # Check that routes are registered
            rules = [rule.rule for rule in app.url_map.iter_rules()]
            assert '/health' in rules
            assert '/api/docs' in rules
            assert '/api/databases' in rules
    
    def test_register_legacy_routes(self):
        """Test legacy routes registration"""
        app = Flask(__name__)
        
        with patch('backend.app_api.get_git_database_service'):
            register_legacy_routes(app)
            
            # Check that legacy routes are registered
            rules = [rule.rule for rule in app.url_map.iter_rules()]
            assert '/api/databases/<database_name>/query' in rules
            assert '/api/databases/<database_name>/info' in rules
            assert '/api/databases/<database_name>/sync' in rules
            assert '/api/git/status' in rules
            assert '/api/git/pull' in rules


class TestDatabaseIntegration:
    """Integration tests with actual database"""
    
    def test_database_query_integration(self):
        """Test actual database query integration"""
        with TestDatabase() as test_db:
            test_db.create_test_tables()
            
            with patch('app_api.get_git_database_service') as mock_service:
                from src.services.git_database_service import GitDatabaseService
                from src.implementations.git_file_storage import GitFileStorage
                
                mock_git_storage = Mock()
                service = GitDatabaseService(mock_git_storage)
                service.cache_path = Path(test_db.db_path).parent
                service.database_name = Path(test_db.db_path).name
                
                mock_service.return_value = service
                
                with patch('backend.app_api.get_config_manager', return_value=mock_config_manager):
                    with patch('backend.app_api.get_logger', return_value=mock_logger):
                        app = create_app(testing=True)
                        client = app.test_client()
                        
                        response = client.post('/api/databases/test_db/query?environment=default',
                                             json={"query": "SELECT * FROM users LIMIT 1", "fetch_all": True})
                        
                        assert response.status_code == 200
                        data = json.loads(response.data)
                        assert data['success'] is True
                        assert len(data['data']['data']) == 1
                        assert 'username' in data['data']['columns']
    
    def test_database_info_integration(self):
        """Test actual database info integration"""
        with TestDatabase() as test_db:
            test_db.create_test_tables()
            
            with patch('app_api.get_git_database_service') as mock_service:
                from src.services.git_database_service import GitDatabaseService
                from src.implementations.git_file_storage import GitFileStorage
                
                mock_git_storage = Mock()
                service = GitDatabaseService(mock_git_storage)
                service.cache_path = Path(test_db.db_path).parent
                service.database_name = Path(test_db.db_path).name
                
                mock_service.return_value = service
                
                with patch('backend.app_api.get_config_manager', return_value=mock_config_manager):
                    with patch('backend.app_api.get_logger', return_value=mock_logger):
                        app = create_app(testing=True)
                        client = app.test_client()
                        
                        response = client.get('/api/databases/test_db/info?environment=default')
                        
                        assert response.status_code == 200
                        data = json.loads(response.data)
                        assert 'database_name' in data
                        assert 'tables' in data
                        assert 'users' in data['tables']
                        assert 'test_cases' in data['tables']
                        assert 'requirements' in data['tables']
