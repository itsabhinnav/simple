"""
Unit Tests for Git File Storage

This module provides comprehensive unit tests for the GitFileStorage class
to achieve 100% C0 and C1 coverage.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import subprocess

from src.implementations.git_file_storage import GitFileStorage
from tests import MockGitFileStorage, mock_logger


class TestGitFileStorage:
    """Test cases for GitFileStorage"""
    
    def test_init_default_params(self, mock_logger):
        """Default init now leaves repo_url empty - remote/git sync is permanently disabled."""
        with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
            storage = GitFileStorage()

            assert storage.repo_url == ""
            assert storage.local_repo_path == Path("remote")
            assert storage.data_path == Path("data")
            assert storage.git_path == Path("remote") / ".git"
            mock_logger.info.assert_called_once()
    
    def test_init_custom_params(self, mock_logger):
        """Test initialization with custom parameters"""
        with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
            storage = GitFileStorage(
                repo_url="https://custom-repo.com/test",
                local_repo_path="custom_remote",
                data_path="custom_data"
            )
            
            assert storage.repo_url == "https://custom-repo.com/test"
            assert storage.local_repo_path == Path("custom_remote")
            assert storage.data_path == Path("custom_data")
            assert storage.git_path == Path("custom_remote") / ".git"
    
    def test_init_creates_data_directory(self, mock_logger):
        """Test that initialization creates data directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                storage = GitFileStorage(data_path=str(temp_path / "test_data"))
                
                assert (temp_path / "test_data").exists()
    
    def test_clone_or_fetch_repo_new_repo(self, mock_logger):
        """Test cloning a new repository"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value.returncode = 0
                    storage = GitFileStorage(local_repo_path=str(temp_path / "remote"))
                    
                    result = storage.clone_or_fetch_repo()
                    
                    assert result is True
                    mock_run.assert_called_once()
                    mock_logger.info.assert_any_call("Cloning repository...")
                    mock_logger.info.assert_any_call("Repository cloned successfully")
    
    def test_clone_or_fetch_repo_existing_repo(self, mock_logger):
        """Test fetching updates for existing repository"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            git_path = temp_path / "remote" / ".git"
            git_path.mkdir(parents=True)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                with patch('subprocess.run') as mock_run:
                    # Mock successful git operations
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = "origin/main"
                    
                    storage = GitFileStorage(local_repo_path=str(temp_path / "remote"))
                    
                    result = storage.clone_or_fetch_repo()
                    
                    assert result is True
                    assert mock_run.call_count >= 2  # fetch + reset
                    mock_logger.info.assert_any_call("Repository exists, fetching latest changes...")
    
    def test_clone_or_fetch_repo_clone_failure(self, mock_logger):
        """Test clone failure"""
        with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(1, "git")
                
                storage = GitFileStorage()
                
                result = storage.clone_or_fetch_repo()
                
                assert result is False
                mock_logger.error.assert_called()
    
    def test_clone_or_fetch_repo_fetch_failure(self, mock_logger):
        """Test fetch failure for existing repo"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            git_path = temp_path / "remote" / ".git"
            git_path.mkdir(parents=True)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                with patch('subprocess.run') as mock_run:
                    # First call (fetch) succeeds, second call (reset) fails
                    mock_run.side_effect = [
                        Mock(returncode=0),  # fetch
                        subprocess.CalledProcessError(1, "git")  # reset
                    ]
                    
                    storage = GitFileStorage(local_repo_path=str(temp_path / "remote"))
                    
                    result = storage.clone_or_fetch_repo()
                    
                    assert result is False
                    mock_logger.error.assert_called()
    
    def test_clone_or_fetch_repo_unexpected_error(self, mock_logger):
        """Test unexpected error during clone/fetch"""
        with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
            with patch('subprocess.run', side_effect=Exception("Unexpected error")):
                storage = GitFileStorage()
                
                result = storage.clone_or_fetch_repo()
                
                assert result is False
                mock_logger.error.assert_called()
    
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
    
    def test_copy_file_to_data_success(self, mock_logger):
        """Test successful file copy to data directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_file = temp_path / "remote" / "database" / "test.db"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("database content")
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                storage = GitFileStorage(
                    local_repo_path=str(temp_path / "remote"),
                    data_path=str(temp_path / "data")
                )
                
                result = storage.copy_file_to_data("database/test.db", "cache/test.db")
                
                assert result is True
                dest_file = temp_path / "data" / "cache" / "test.db"
                assert dest_file.exists()
                assert dest_file.read_text() == "database content"
                mock_logger.info.assert_called()
    
    def test_copy_file_to_data_source_not_found(self, mock_logger):
        """Test file copy when source file doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                storage = GitFileStorage(
                    local_repo_path=str(temp_path / "remote"),
                    data_path=str(temp_path / "data")
                )
                
                result = storage.copy_file_to_data("nonexistent/file.txt", "cache/file.txt")
                
                assert result is False
                mock_logger.error.assert_called()
    
    def test_copy_file_to_data_exception(self, mock_logger):
        """Test file copy with exception"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_file = temp_path / "remote" / "test.txt"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("content")
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                with patch('shutil.copy2', side_effect=Exception("Copy error")):
                    storage = GitFileStorage(
                        local_repo_path=str(temp_path / "remote"),
                        data_path=str(temp_path / "data")
                    )
                    
                    result = storage.copy_file_to_data("test.txt", "cache/test.txt")
                    
                    assert result is False
                    mock_logger.error.assert_called()
    
    def test_copy_file_from_data_success(self, mock_logger):
        """Test successful file copy from data directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_file = temp_path / "data" / "cache" / "test.db"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("database content")
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                storage = GitFileStorage(
                    local_repo_path=str(temp_path / "remote"),
                    data_path=str(temp_path / "data")
                )
                
                result = storage.copy_file_from_data("cache/test.db", "database/test.db")
                
                assert result is True
                dest_file = temp_path / "remote" / "database" / "test.db"
                assert dest_file.exists()
                assert dest_file.read_text() == "database content"
                mock_logger.info.assert_called()
    
    def test_copy_file_from_data_source_not_found(self, mock_logger):
        """Test file copy from data when source file doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                storage = GitFileStorage(
                    local_repo_path=str(temp_path / "remote"),
                    data_path=str(temp_path / "data")
                )
                
                result = storage.copy_file_from_data("nonexistent/file.txt", "database/file.txt")
                
                assert result is False
                mock_logger.error.assert_called()
    
    def test_copy_file_from_data_exception(self, mock_logger):
        """Test file copy from data with exception"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_file = temp_path / "data" / "test.txt"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("content")
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                with patch('shutil.copy2', side_effect=Exception("Copy error")):
                    storage = GitFileStorage(
                        local_repo_path=str(temp_path / "remote"),
                        data_path=str(temp_path / "data")
                    )
                    
                    result = storage.copy_file_from_data("test.txt", "remote/test.txt")
                    
                    assert result is False
                    mock_logger.error.assert_called()
    
    def test_list_files_default_pattern(self, mock_logger):
        """Test listing files with default pattern"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            (temp_path / "file1.txt").write_text("content1")
            (temp_path / "file2.db").write_text("content2")
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "file3.txt").write_text("content3")
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                storage = GitFileStorage(local_repo_path=str(temp_path))
                
                files = storage.list_files()
                
                assert len(files) >= 2
                assert "file1.txt" in files
                assert "file2.db" in files
    
    def test_list_files_custom_pattern(self, mock_logger):
        """Test listing files with custom pattern"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            (temp_path / "file1.txt").write_text("content1")
            (temp_path / "file2.db").write_text("content2")
            (temp_path / "file3.py").write_text("content3")
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                storage = GitFileStorage(local_repo_path=str(temp_path))
                
                files = storage.list_files("*.db")
                
                assert len(files) == 1
                assert "file2.db" in files
    
    def test_list_files_exception(self, mock_logger):
        """Test listing files with exception"""
        with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
            storage = GitFileStorage()
            
            with patch.object(Path, 'glob', side_effect=Exception("File system error")):
                files = storage.list_files()
                
                assert files == []
    
    def test_get_repo_status_success(self, mock_logger):
        """Test successful repo status retrieval"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            git_path = temp_path / "remote" / ".git"
            git_path.mkdir(parents=True)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = "main\n"
                    
                    storage = GitFileStorage(local_repo_path=str(temp_path / "remote"))
                    
                    result = storage.get_repo_status()
                    
                    assert "branch" in result
                    assert "status" in result
                    assert "last_commit" in result
                    assert "files_changed" in result
    
    def test_get_repo_status_exception(self, mock_logger):
        """Test repo status with exception"""
        with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
            storage = GitFileStorage()
            
            with patch('subprocess.run', side_effect=Exception("Git error")):
                result = storage.get_repo_status()
                
                assert "error" in result
                mock_logger.error.assert_called()
    
    def test_pull_latest_changes_success(self, mock_logger):
        """Test successful pull of latest changes"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            git_path = temp_path / "remote" / ".git"
            git_path.mkdir(parents=True)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value.returncode = 0
                    
                    storage = GitFileStorage(local_repo_path=str(temp_path / "remote"))
                    
                    result = storage.pull_latest_changes()
                    
                    assert result is True
                    mock_logger.info.assert_called()
    
    def test_pull_latest_changes_failure(self, mock_logger):
        """Test pull failure"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            git_path = temp_path / "remote" / ".git"
            git_path.mkdir(parents=True)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                with patch('subprocess.run') as mock_run:
                    mock_run.side_effect = subprocess.CalledProcessError(1, "git")
                    
                    storage = GitFileStorage(local_repo_path=str(temp_path / "remote"))
                    
                    result = storage.pull_latest_changes()
                    
                    assert result is False
                    mock_logger.error.assert_called()
    
    def test_pull_latest_changes_exception(self, mock_logger):
        """Test pull with unexpected exception"""
        with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
            storage = GitFileStorage()
            
            with patch('subprocess.run', side_effect=Exception("Unexpected error")):
                result = storage.pull_latest_changes()
                
                assert result is False
                mock_logger.error.assert_called()
    
    def test_push_changes_success(self, mock_logger):
        """Test successful push of changes"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            git_path = temp_path / "remote" / ".git"
            git_path.mkdir(parents=True)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value.returncode = 0
                    
                    storage = GitFileStorage(local_repo_path=str(temp_path / "remote"))
                    
                    result = storage.push_changes("Test commit")
                    
                    assert result is True
                    mock_logger.info.assert_called()
    
    def test_push_changes_failure(self, mock_logger):
        """Test push failure"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            git_path = temp_path / "remote" / ".git"
            git_path.mkdir(parents=True)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                with patch('subprocess.run') as mock_run:
                    mock_run.side_effect = subprocess.CalledProcessError(1, "git")
                    
                    storage = GitFileStorage(local_repo_path=str(temp_path / "remote"))
                    
                    result = storage.push_changes("Test commit")
                    
                    assert result is False
                    mock_logger.error.assert_called()
    
    def test_push_changes_exception(self, mock_logger):
        """Test push with unexpected exception"""
        with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
            storage = GitFileStorage()
            
            with patch('subprocess.run', side_effect=Exception("Unexpected error")):
                result = storage.push_changes("Test commit")
                
                assert result is False
                mock_logger.error.assert_called()
    
    def test_get_file_exists(self, mock_logger):
        """Test get file when file exists"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test_file.txt"
            test_file.write_text("test content")
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                storage = GitFileStorage(local_repo_path=str(temp_path))
                
                result = storage.get_file("test_file.txt")
                
                assert result == test_file
    
    def test_get_file_not_exists(self, mock_logger):
        """Test get file when file doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            with patch('src.implementations.git_file_storage.get_logger', return_value=mock_logger):
                storage = GitFileStorage(local_repo_path=str(temp_path))
                
                result = storage.get_file("nonexistent_file.txt")
                
                assert result is None
