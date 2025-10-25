"""
Unit Tests for Git Database Service

This module provides comprehensive unit tests for the GitDatabaseService class
to achieve 100% C0 and C1 coverage.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sqlite3

from src.services.git_database_service import GitDatabaseService
from tests import TestDatabase, MockGitFileStorage, mock_config_manager, mock_logger


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
    
    def test_init_creates_directories(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test that initialization creates required directories"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            mock_config_manager.get_config.side_effect = lambda key, default=None: {
                "database.data_directory": str(temp_path / "data"),
                "database.cache_directory": str(temp_path / "data" / "cache"),
                "database.name": "test_db.db"
            }.get(key, default)
            
            with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
                with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                    service = GitDatabaseService(mock_git_storage)
                    
                    assert (temp_path / "data").exists()
                    assert (temp_path / "data" / "cache").exists()
    
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
    
    def test_initialize_clone_failure(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test initialization failure when clone/fetch fails"""
        mock_git_storage.clone_or_fetch_repo.return_value = False
        
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                
                result = service.initialize()
                
                assert result is False
                mock_logger.error.assert_called_with("Failed to clone/fetch repository")
    
    def test_initialize_exception(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test initialization with exception"""
        mock_git_storage.clone_or_fetch_repo.side_effect = Exception("Git error")
        
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                
                result = service.initialize()
                
                assert result is False
                mock_logger.error.assert_called()
    
    def test_sync_databases_from_git_success(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test successful database sync from git"""
        mock_git_storage.file_exists.return_value = True
        mock_git_storage.local_repo_path = Path("test_remote")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            mock_config_manager.get_config.side_effect = lambda key, default=None: {
                "database.data_directory": str(temp_path / "data"),
                "database.cache_directory": str(temp_path / "data" / "cache"),
                "database.name": "test_db.db"
            }.get(key, default)
            
            # Create source database file
            source_db = temp_path / "test_remote" / "database" / "test_db.db"
            source_db.parent.mkdir(parents=True)
            with TestDatabase(str(source_db)) as db:
                db.create_test_tables()
            
            with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
                with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                    service = GitDatabaseService(mock_git_storage)
                    service._sync_databases_from_git()
                    
                    # Check that file was copied
                    dest_db = temp_path / "data" / "cache" / "test_db.db"
                    assert dest_db.exists()
                    mock_logger.info.assert_called_with("Synced database file: test_db.db")
    
    def test_sync_databases_from_git_file_not_found(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test database sync when file doesn't exist in git"""
        mock_git_storage.file_exists.return_value = False
        
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                service._sync_databases_from_git()
                
                mock_logger.warning.assert_called_with("Database file not found in git repo: database/test_db.db")
    
    def test_sync_databases_from_git_exception(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test database sync with exception"""
        mock_git_storage.file_exists.side_effect = Exception("File system error")
        
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                service._sync_databases_from_git()
                
                mock_logger.error.assert_called()
    
    def test_execute_query_select_success(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test successful SELECT query execution"""
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
    
    def test_execute_query_insert_success(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test successful INSERT query execution"""
        with TestDatabase() as test_db:
            test_db.create_test_tables()
            
            with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
                with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                    service = GitDatabaseService(mock_git_storage)
                    service.cache_path = Path(test_db.db_path).parent
                    service.database_name = Path(test_db.db_path).name
                    
                    result = service.execute_query("INSERT INTO users (username, email) VALUES ('newuser', 'new@test.com')")
                    
                    assert result["success"] is True
                    assert result["row_count"] == 1
    
    def test_execute_query_database_not_found(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test query execution when database file doesn't exist"""
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                service.cache_path = Path("/nonexistent")
                service.database_name = "nonexistent.db"
                
                result = service.execute_query("SELECT * FROM users")
                
                assert "error" in result
                assert "Database file not found" in result["error"]
                mock_logger.error.assert_called()
    
    def test_execute_query_sql_error(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test query execution with SQL error"""
        with TestDatabase() as test_db:
            test_db.create_test_tables()
            
            with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
                with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                    service = GitDatabaseService(mock_git_storage)
                    service.cache_path = Path(test_db.db_path).parent
                    service.database_name = Path(test_db.db_path).name
                    
                    result = service.execute_query("SELECT * FROM nonexistent_table")
                    
                    assert result["success"] is False
                    assert "error" in result
                    mock_logger.error.assert_called()
    
    def test_execute_query_pragma_query(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test PRAGMA query execution"""
        with TestDatabase() as test_db:
            test_db.create_test_tables()
            
            with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
                with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                    service = GitDatabaseService(mock_git_storage)
                    service.cache_path = Path(test_db.db_path).parent
                    service.database_name = Path(test_db.db_path).name
                    
                    result = service.execute_query("PRAGMA table_info(users)")
                    
                    assert result["success"] is True
                    assert "data" in result
    
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
                    assert result["table_count"] == 3  # users, test_cases, requirements
    
    def test_get_database_info_not_found(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test database info when database doesn't exist"""
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                service.cache_path = Path("/nonexistent")
                service.database_name = "nonexistent.db"
                
                result = service.get_database_info()
                
                assert "error" in result
                assert result["error"] == "Database file not found"
    
    def test_get_database_info_exception(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test database info with exception"""
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                
                # Mock Path.exists to raise exception
                with patch.object(Path, 'exists', side_effect=Exception("File system error")):
                    result = service.get_database_info()
                    
                    assert "error" in result
                    mock_logger.error.assert_called()
    
    def test_list_databases_success(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test successful database listing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test database files
            db1 = temp_path / "test1.db"
            db2 = temp_path / "test2.db"
            
            with TestDatabase(str(db1)) as db:
                db.create_test_tables()
            
            with TestDatabase(str(db2)) as db:
                db.create_test_tables()
            
            with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
                with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                    service = GitDatabaseService(mock_git_storage)
                    service.cache_path = temp_path
                    
                    result = service.list_databases()
                    
                    assert len(result) == 2
                    assert all("name" in db for db in result)
                    assert all("file_path" in db for db in result)
                    assert all("size" in db for db in result)
                    assert all("last_modified" in db for db in result)
                    assert all("status" in db for db in result)
    
    def test_list_databases_empty_directory(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test database listing with empty directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
                with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                    service = GitDatabaseService(mock_git_storage)
                    service.cache_path = temp_path
                    
                    result = service.list_databases()
                    
                    assert result == []
    
    def test_list_databases_exception(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test database listing with exception"""
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                
                # Mock glob to raise exception
                with patch.object(Path, 'glob', side_effect=Exception("File system error")):
                    result = service.list_databases()
                    
                    assert result == []
                    mock_logger.error.assert_called()
    
    def test_get_repo_status_success(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test successful repo status retrieval"""
        mock_git_storage.get_repo_status.return_value = {"status": "clean", "branch": "main"}
        
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                
                result = service.get_repo_status()
                
                assert result == {"status": "clean", "branch": "main"}
                mock_git_storage.get_repo_status.assert_called_once()
    
    def test_get_repo_status_exception(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test repo status with exception"""
        mock_git_storage.get_repo_status.side_effect = Exception("Git error")
        
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                
                result = service.get_repo_status()
                
                assert "error" in result
                mock_logger.error.assert_called()
    
    def test_create_sample_data_success(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test successful sample data creation"""
        with TestDatabase() as test_db:
            test_db.create_test_tables()
            
            with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
                with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                    service = GitDatabaseService(mock_git_storage)
                    service.cache_path = Path(test_db.db_path).parent
                    service.database_name = Path(test_db.db_path).name
                    
                    result = service.create_sample_data()
                    
                    assert result is True
                    mock_logger.info.assert_any_call("Creating sample data...")
                    mock_logger.info.assert_any_call("Sample data created successfully")
    
    def test_create_sample_data_exception(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test sample data creation with exception"""
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                
                # Mock execute_query to raise exception
                with patch.object(service, 'execute_query', side_effect=Exception("Database error")):
                    result = service.create_sample_data()
                    
                    assert result is False
                    mock_logger.error.assert_called()
    
    def test_database_name_with_extension(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test database name handling when it already has .db extension"""
        mock_config_manager.get_database_name.return_value = "test.db"
        
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                
                assert service.database_name == "test.db"
    
    def test_database_name_without_extension(self, mock_git_storage, mock_config_manager, mock_logger):
        """Test database name handling when it doesn't have .db extension"""
        mock_config_manager.get_database_name.return_value = "test"
        
        with patch('src.services.git_database_service.get_config_manager', return_value=mock_config_manager):
            with patch('src.services.git_database_service.get_logger', return_value=mock_logger):
                service = GitDatabaseService(mock_git_storage)
                
                assert service.database_name == "test"
