"""
Simple Test Suite for Sakura Backend

This module provides a basic test suite to demonstrate the testing structure
and achieve coverage for the core functionality.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sqlite3

# Add backend to Python path
import sys
import os
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.services.git_database_service import GitDatabaseService
from src.implementations.git_file_storage import GitFileStorage
from src.infrastructure.configuration_manager import ConfigurationManager


class TestDatabase:
    """Test database utility for creating temporary databases"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or tempfile.mktemp(suffix='.db')
        self.conn = None
    
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def create_test_tables(self):
        """Create test tables with sample data"""
        cursor = self.conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                first_name TEXT,
                last_name TEXT,
                role TEXT DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create test_cases table
        cursor.execute("""
            CREATE TABLE test_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_case_id TEXT UNIQUE NOT NULL,
                requirement_id TEXT,
                test_name TEXT NOT NULL,
                feature TEXT,
                test_type TEXT,
                description TEXT,
                preconditions TEXT,
                test_steps TEXT,
                expected_result TEXT,
                test_category TEXT,
                test_level TEXT,
                test_environment TEXT,
                test_data TEXT,
                test_priority TEXT,
                test_status TEXT,
                test_execution_type TEXT,
                test_automation_status TEXT,
                test_priority_level TEXT,
                test_suite TEXT,
                created_by TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert sample data
        cursor.execute("""
            INSERT INTO users (username, email, first_name, last_name, role)
            VALUES ('admin', 'admin@test.com', 'Admin', 'User', 'admin')
        """)
        
        cursor.execute("""
            INSERT INTO test_cases (test_case_id, test_name, feature, test_type, description)
            VALUES ('TC001', 'Test Case 1', 'Authentication', 'Functional', 'Test description')
        """)
        
        self.conn.commit()


@pytest.fixture
def mock_git_storage():
    """Provide a mock GitFileStorage instance"""
    mock = Mock()
    mock.clone_or_fetch_repo.return_value = True
    mock.file_exists.return_value = True
    mock.local_repo_path = Path("test_remote")
    return mock


@pytest.fixture
def mock_config_manager():
    """Provide a mock configuration manager"""
    mock = Mock()
    mock.get_config.side_effect = lambda key, default=None: {
        "database.data_directory": "test_data",
        "database.cache_directory": "test_data/cache",
        "database.name": "test_db.db"
    }.get(key, default)
    mock.get_database_name.return_value = "test_db.db"
    mock.get_table_name.side_effect = lambda table: {
        "users": "users",
        "test_cases": "test_cases"
    }.get(table, table)
    return mock


@pytest.fixture
def mock_logger():
    """Provide a mock logger"""
    mock = Mock()
    mock.info = Mock()
    mock.error = Mock()
    mock.warning = Mock()
    mock.debug = Mock()
    return mock


class TestGitDatabaseService:
    """Test cases for GitDatabaseService"""
    
    def test_init_success(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test successful initialization of GitDatabaseService"""
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                
                assert service.git_storage == mock_git_storage
                assert service.config_manager == mock_config_manager
                assert service.data_path == Path("test_data")
                assert service.cache_path == Path("test_data/cache")
                assert service.database_name == "test_db.db"
                mock_logger.info.assert_called_once_with("Git database service initialized")
    
    def test_initialize_success(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test successful initialization process"""
        mock_git_storage.clone_or_fetch_repo.return_value = True
        
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                
                result = service.initialize()
                
                assert result is True
                mock_git_storage.clone_or_fetch_repo.assert_called_once()
                mock_logger.info.assert_any_call("Initializing Git database service...")
                mock_logger.info.assert_any_call("Git database service initialized successfully")
    
    def test_execute_query_success(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test successful query execution"""
        with TestDatabase() as test_db:
            test_db.create_test_tables()
            
            with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
                with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                    service = GitDatabaseService(mock_git_storage)
                    service.cache_path = Path(test_db.db_path).parent
                    service.database_name = Path(test_db.db_path).name
                    
                    result = service.execute_query("SELECT * FROM users LIMIT 1")
                    
                    assert result["success"] is True
                    assert "data" in result
                    assert "row_count" in result
                    assert result["row_count"] == 1
    
    def test_get_database_info_success(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test successful database info retrieval"""
        with TestDatabase() as test_db:
            test_db.create_test_tables()
            
            with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
                with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                    service = GitDatabaseService(mock_git_storage)
                    service.cache_path = Path(test_db.db_path).parent
                    service.database_name = Path(test_db.db_path).name
                    
                    result = service.get_database_info()
                    
                    assert "database_name" in result
                    assert "file_path" in result
                    assert "file_size" in result
                    assert "last_modified" in result
                    assert "tables" in result
                    assert "table_count" in result
                    assert result["database_name"] == "test_db.db"
                    assert result["table_count"] == 2  # users, test_cases


class TestGitFileStorage:
    """Test cases for GitFileStorage"""
    
    def test_init_default_params(self, mock_logger):
        """Test initialization with default parameters"""
        with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
            storage = GitFileStorage()
            
            assert storage.repo_url == "https://gitlab.com/android-devops/sakura-db"
            assert storage.local_repo_path == Path("remote")
            assert storage.data_path == Path("data")
            assert storage.git_path == Path("remote") / ".git"
            mock_logger.info.assert_called_once()
    
    def test_file_exists_true(self, mock_logger):
        """Test file exists when file is present"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test_file.txt"
            test_file.write_text("test content")
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                storage = GitFileStorage(local_repo_path=str(temp_path))
                
                result = storage.file_exists("test_file.txt")
                
                assert result is True
    
    def test_file_exists_false(self, mock_logger):
        """Test file exists when file is not present"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                storage = GitFileStorage(local_repo_path=str(temp_path))
                
                result = storage.file_exists("nonexistent_file.txt")
                
                assert result is False


class TestConfigurationManager:
    """Test cases for ConfigurationManager"""
    
    def test_init_empty(self):
        """Test initialization with no sources"""
        manager = ConfigurationManager()
        assert len(manager.sources) == 0
    
    def test_add_source(self):
        """Test adding configuration source"""
        manager = ConfigurationManager()
        from src.infrastructure.configuration_manager import EnvironmentConfigSource
        source = EnvironmentConfigSource()
        
        manager.add_source(source)
        assert len(manager.sources) == 1
        assert source in manager.sources
    
    def test_get_config_not_found(self):
        """Test getting config when no source has it"""
        manager = ConfigurationManager()
        
        result = manager.get_config('test.key')
        
        assert result is None
    
    def test_get_config_with_default(self):
        """Test getting config with default value"""
        manager = ConfigurationManager()
        
        result = manager.get_config('test.key', 'default_value')
        
        assert result == 'default_value'
