"""
Test Configuration and Setup

This module provides test configuration, fixtures, and utilities for comprehensive testing.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import sqlite3
from typing import Dict, Any, List

# Add backend to Python path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Test configuration
TEST_CONFIG = {
    "environment": "test",
    "database": {
        "provider": "sqlite",
        "name": "test_db.db",
        "data_directory": "test_data",
        "cache_directory": "test_data/cache"
    },
    "storage": {
        "provider": "git",
        "base_url": "https://test-repo.com/test-db",
        "local_repo_path": "test_remote",
        "data_path": "test_data"
    },
    "logging": {
        "level": "DEBUG",
        "enable_console": False,
        "enable_file": False
    }
}

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
        
        # Create requirements table
        cursor.execute("""
            CREATE TABLE requirements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requirement_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT,
                status TEXT,
                created_by TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert sample data
        self._insert_sample_data(cursor)
        self.conn.commit()
    
    def _insert_sample_data(self, cursor):
        """Insert sample test data"""
        # Sample users
        users = [
            ('admin', 'admin@test.com', 'Admin', 'User', 'admin'),
            ('testuser1', 'test1@test.com', 'Test', 'User1', 'user'),
            ('testuser2', 'test2@test.com', 'Test', 'User2', 'user')
        ]
        
        for user in users:
            cursor.execute("""
                INSERT INTO users (username, email, first_name, last_name, role)
                VALUES (?, ?, ?, ?, ?)
            """, user)
        
        # Sample test cases
        test_cases = [
            ('TC001', 'REQ001', 'Login Test', 'Authentication', 'Functional', 
             'Test user login functionality', 'User has valid credentials', 
             '1. Navigate to login page\n2. Enter credentials\n3. Click login', 
             'User should be logged in successfully', 'Smoke', 'System', 
             'Test Environment', 'Valid user credentials', 'P1', 'Draft', 
             'Manual', 'Not Automated', 'High', 'Auth Suite', 'admin'),
            ('TC002', 'REQ002', 'Logout Test', 'Authentication', 'Functional',
             'Test user logout functionality', 'User is logged in',
             '1. Click logout button\n2. Confirm logout',
             'User should be logged out successfully', 'Smoke', 'System',
             'Test Environment', 'Logged in user', 'P2', 'Draft',
             'Manual', 'Not Automated', 'Medium', 'Auth Suite', 'admin')
        ]
        
        for tc in test_cases:
            cursor.execute("""
                INSERT INTO test_cases (test_case_id, requirement_id, test_name, feature, 
                test_type, description, preconditions, test_steps, expected_result, 
                test_category, test_level, test_environment, test_data, test_priority, 
                test_status, test_execution_type, test_automation_status, test_priority_level, 
                test_suite, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, tc)
        
        # Sample requirements
        requirements = [
            ('REQ001', 'User Authentication', 'Users should be able to login with valid credentials', 'P1', 'Active', 'admin'),
            ('REQ002', 'User Logout', 'Users should be able to logout from the system', 'P2', 'Active', 'admin')
        ]
        
        for req in requirements:
            cursor.execute("""
                INSERT INTO requirements (requirement_id, title, description, priority, status, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, req)

class MockGitFileStorage:
    """Mock implementation of GitFileStorage for testing"""
    
    def __init__(self, repo_url: str = "https://test-repo.com/test-db", 
                 local_repo_path: str = "test_remote", data_path: str = "test_data"):
        self.repo_url = repo_url
        self.local_repo_path = Path(local_repo_path)
        self.data_path = Path(data_path)
        self.git_path = self.local_repo_path / ".git"
        self._files = {}
    
    def clone_or_fetch_repo(self) -> bool:
        """Mock clone/fetch operation"""
        return True
    
    def file_exists(self, file_path: str) -> bool:
        """Mock file existence check"""
        return file_path in self._files
    
    def copy_file_to_data(self, source_file: str, dest_file: str) -> bool:
        """Mock file copy operation"""
        if source_file in self._files:
            self._files[dest_file] = self._files[source_file]
            return True
        return False
    
    def get_file(self, file_path: str) -> Path:
        """Mock get file operation"""
        if file_path in self._files:
            return Path(self._files[file_path])
        return None
    
    def list_files(self, pattern: str = "*") -> List[str]:
        """Mock list files operation"""
        return list(self._files.keys())
    
    def get_repo_status(self) -> Dict[str, Any]:
        """Mock repo status"""
        return {
            "status": "clean",
            "branch": "main",
            "last_commit": "abc123",
            "files_changed": 0
        }
    
    def add_file(self, file_path: str, content: str):
        """Add a file to the mock storage"""
        self._files[file_path] = content

@pytest.fixture
def test_config():
    """Provide test configuration"""
    return TEST_CONFIG.copy()

@pytest.fixture
def temp_dir():
    """Provide a temporary directory for tests"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)

@pytest.fixture
def test_db():
    """Provide a test database with sample data"""
    with TestDatabase() as db:
        db.create_test_tables()
        yield db

@pytest.fixture
def mock_git_storage():
    """Provide a mock GitFileStorage instance"""
    return MockGitFileStorage()

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
        "test_cases": "test_cases",
        "requirements": "requirements"
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

# Test utilities
def assert_dict_contains(actual: Dict[str, Any], expected: Dict[str, Any]):
    """Assert that actual dict contains all keys and values from expected"""
    for key, value in expected.items():
        assert key in actual, f"Key '{key}' not found in actual dict"
        assert actual[key] == value, f"Value for key '{key}' doesn't match. Expected: {value}, Actual: {actual[key]}"

def create_test_user_data():
    """Create test user data"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "role": "user"
    }

def create_test_case_data():
    """Create test case data"""
    return {
        "test_case_id": "TC_TEST_001",
        "requirement_id": "REQ_TEST_001",
        "test_name": "Test Case",
        "feature": "Test Feature",
        "test_type": "Functional",
        "description": "Test description",
        "preconditions": "Test preconditions",
        "test_steps": "1. Step one\n2. Step two",
        "expected_result": "Expected result",
        "test_category": "Smoke",
        "test_level": "System",
        "test_environment": "Test Environment",
        "test_data": "Test data",
        "test_priority": "P1",
        "test_status": "Draft",
        "test_execution_type": "Manual",
        "test_automation_status": "Not Automated",
        "test_priority_level": "High",
        "test_suite": "Test Suite",
        "created_by": "admin"
    }
