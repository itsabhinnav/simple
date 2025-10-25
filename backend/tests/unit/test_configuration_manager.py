"""
Unit Tests for Configuration Manager

This module provides comprehensive unit tests for the ConfigurationManager class
to achieve 100% C0 and C1 coverage.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.infrastructure.configuration_manager import (
    ConfigurationManager, 
    EnvironmentConfigSource, 
    FileConfigSource,
    get_config_manager
)
from tests import TEST_CONFIG


class TestEnvironmentConfigSource:
    """Test cases for EnvironmentConfigSource"""
    
    def test_get_config_existing(self):
        """Test getting existing environment variable"""
        with patch.dict(os.environ, {'TEST_VAR': 'test_value'}):
            source = EnvironmentConfigSource()
            result = source.get_config('TEST_VAR')
            assert result == 'test_value'
    
    def test_get_config_missing(self):
        """Test getting missing environment variable"""
        source = EnvironmentConfigSource()
        result = source.get_config('NONEXISTENT_VAR')
        assert result is None
    
    def test_get_config_with_default(self):
        """Test getting config with default value"""
        source = EnvironmentConfigSource()
        result = source.get_config('NONEXISTENT_VAR', 'default_value')
        assert result == 'default_value'
    
    def test_has_config_true(self):
        """Test has_config when variable exists"""
        with patch.dict(os.environ, {'TEST_VAR': 'test_value'}):
            source = EnvironmentConfigSource()
            assert source.has_config('TEST_VAR') is True
    
    def test_has_config_false(self):
        """Test has_config when variable doesn't exist"""
        source = EnvironmentConfigSource()
        assert source.has_config('NONEXISTENT_VAR') is False


class TestFileConfigSource:
    """Test cases for FileConfigSource"""
    
    def test_init_with_path(self):
        """Test initialization with file path"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(TEST_CONFIG, f)
            file_path = f.name
        
        try:
            source = FileConfigSource(file_path)
            assert source.file_path == Path(file_path)
        finally:
            os.unlink(file_path)
    
    def test_get_config_existing(self):
        """Test getting existing config from file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(TEST_CONFIG, f)
            file_path = f.name
        
        try:
            source = FileConfigSource(file_path)
            result = source.get_config('environment')
            assert result == 'test'
        finally:
            os.unlink(file_path)
    
    def test_get_config_nested(self):
        """Test getting nested config from file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(TEST_CONFIG, f)
            file_path = f.name
        
        try:
            source = FileConfigSource(file_path)
            result = source.get_config('database.provider')
            assert result == 'sqlite'
        finally:
            os.unlink(file_path)
    
    def test_get_config_missing(self):
        """Test getting missing config from file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(TEST_CONFIG, f)
            file_path = f.name
        
        try:
            source = FileConfigSource(file_path)
            result = source.get_config('nonexistent.key')
            assert result is None
        finally:
            os.unlink(file_path)
    
    def test_get_config_with_default(self):
        """Test getting config with default value"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(TEST_CONFIG, f)
            file_path = f.name
        
        try:
            source = FileConfigSource(file_path)
            result = source.get_config('nonexistent.key', 'default_value')
            assert result == 'default_value'
        finally:
            os.unlink(file_path)
    
    def test_has_config_true(self):
        """Test has_config when config exists"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(TEST_CONFIG, f)
            file_path = f.name
        
        try:
            source = FileConfigSource(file_path)
            assert source.has_config('environment') is True
        finally:
            os.unlink(file_path)
    
    def test_has_config_false(self):
        """Test has_config when config doesn't exist"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(TEST_CONFIG, f)
            file_path = f.name
        
        try:
            source = FileConfigSource(file_path)
            assert source.has_config('nonexistent.key') is False
        finally:
            os.unlink(file_path)
    
    def test_file_not_exists(self):
        """Test behavior when file doesn't exist"""
        source = FileConfigSource('/nonexistent/file.json')
        result = source.get_config('any.key')
        assert result is None
        assert source.has_config('any.key') is False
    
    def test_invalid_json(self):
        """Test behavior with invalid JSON file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('invalid json content')
            file_path = f.name
        
        try:
            source = FileConfigSource(file_path)
            result = source.get_config('any.key')
            assert result is None
        finally:
            os.unlink(file_path)
    
    def test_file_exists_method(self):
        """Test file_exists method"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(TEST_CONFIG, f)
            file_path = f.name
        
        try:
            source = FileConfigSource(file_path)
            assert source.file_exists() is True
            
            source = FileConfigSource('/nonexistent/file.json')
            assert source.file_exists() is False
        finally:
            os.unlink(file_path)


class TestConfigurationManager:
    """Test cases for ConfigurationManager"""
    
    def test_init_empty(self):
        """Test initialization with no sources"""
        manager = ConfigurationManager()
        assert len(manager.sources) == 0
    
    def test_add_source(self):
        """Test adding configuration source"""
        manager = ConfigurationManager()
        source = EnvironmentConfigSource()
        
        manager.add_source(source)
        assert len(manager.sources) == 1
        assert source in manager.sources
    
    def test_get_config_from_first_source(self):
        """Test getting config from first available source"""
        manager = ConfigurationManager()
        
        # Mock sources
        source1 = Mock()
        source1.has_config.return_value = True
        source1.get_config.return_value = 'value1'
        
        source2 = Mock()
        source2.has_config.return_value = True
        source2.get_config.return_value = 'value2'
        
        manager.add_source(source1)
        manager.add_source(source2)
        
        result = manager.get_config('test.key')
        
        assert result == 'value1'
        source1.has_config.assert_called_once_with('test.key')
        source1.get_config.assert_called_once_with('test.key')
        source2.has_config.assert_not_called()
    
    def test_get_config_from_second_source(self):
        """Test getting config from second source when first doesn't have it"""
        manager = ConfigurationManager()
        
        # Mock sources
        source1 = Mock()
        source1.has_config.return_value = False
        
        source2 = Mock()
        source2.has_config.return_value = True
        source2.get_config.return_value = 'value2'
        
        manager.add_source(source1)
        manager.add_source(source2)
        
        result = manager.get_config('test.key')
        
        assert result == 'value2'
        source1.has_config.assert_called_once_with('test.key')
        source2.has_config.assert_called_once_with('test.key')
        source2.get_config.assert_called_once_with('test.key')
    
    def test_get_config_not_found(self):
        """Test getting config when no source has it"""
        manager = ConfigurationManager()
        
        source = Mock()
        source.has_config.return_value = False
        
        manager.add_source(source)
        
        result = manager.get_config('test.key')
        
        assert result is None
        source.has_config.assert_called_once_with('test.key')
        source.get_config.assert_not_called()
    
    def test_get_config_with_default(self):
        """Test getting config with default value"""
        manager = ConfigurationManager()
        
        source = Mock()
        source.has_config.return_value = False
        
        manager.add_source(source)
        
        result = manager.get_config('test.key', 'default_value')
        
        assert result == 'default_value'
        source.has_config.assert_called_once_with('test.key')
        source.get_config.assert_not_called()
    
    def test_get_config_exception_in_source(self):
        """Test handling exception in source"""
        manager = ConfigurationManager()
        
        source = Mock()
        source.has_config.side_effect = Exception("Source error")
        
        manager.add_source(source)
        
        result = manager.get_config('test.key')
        
        assert result is None
    
    def test_get_database_name(self):
        """Test getting database name"""
        manager = ConfigurationManager()
        
        source = Mock()
        source.has_config.return_value = True
        source.get_config.return_value = 'test_db.db'
        
        manager.add_source(source)
        
        result = manager.get_database_name()
        
        assert result == 'test_db.db'
        source.has_config.assert_called_once_with('database.name')
        source.get_config.assert_called_once_with('database.name')
    
    def test_get_database_name_not_found(self):
        """Test getting database name when not configured"""
        manager = ConfigurationManager()
        
        source = Mock()
        source.has_config.return_value = False
        
        manager.add_source(source)
        
        result = manager.get_database_name()
        
        assert result == 'sakura.db'  # default value
    
    def test_get_table_name(self):
        """Test getting table name"""
        manager = ConfigurationManager()
        
        source = Mock()
        source.has_config.return_value = True
        source.get_config.return_value = 'custom_users'
        
        manager.add_source(source)
        
        result = manager.get_table_name('users')
        
        assert result == 'custom_users'
        source.has_config.assert_called_once_with('database.table_names.users')
        source.get_config.assert_called_once_with('database.table_names.users')
    
    def test_get_table_name_not_found(self):
        """Test getting table name when not configured"""
        manager = ConfigurationManager()
        
        source = Mock()
        source.has_config.return_value = False
        
        manager.add_source(source)
        
        result = manager.get_table_name('users')
        
        assert result == 'users'  # default value
    
    def test_get_table_name_custom_default(self):
        """Test getting table name with custom default"""
        manager = ConfigurationManager()
        
        source = Mock()
        source.has_config.return_value = False
        
        manager.add_source(source)
        
        result = manager.get_table_name('users', 'custom_default')
        
        assert result == 'custom_default'


class TestGetConfigManager:
    """Test cases for get_config_manager function"""
    
    def test_get_config_manager_singleton(self):
        """Test that get_config_manager returns singleton instance"""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        
        assert manager1 is manager2
    
    def test_get_config_manager_initialization(self):
        """Test that get_config_manager initializes with default sources"""
        manager = get_config_manager()
        
        assert len(manager.sources) >= 1
        assert any(isinstance(source, EnvironmentConfigSource) for source in manager.sources)
    
    def test_get_config_manager_with_file_source(self):
        """Test get_config_manager with file source"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(TEST_CONFIG, f)
            file_path = f.name
        
        try:
            with patch.dict(os.environ, {'CONFIG_FILE': file_path}):
                manager = get_config_manager()
                
                # Should have both environment and file sources
                assert len(manager.sources) >= 2
                assert any(isinstance(source, EnvironmentConfigSource) for source in manager.sources)
                assert any(isinstance(source, FileConfigSource) for source in manager.sources)
        finally:
            os.unlink(file_path)
    
    def test_get_config_manager_file_not_exists(self):
        """Test get_config_manager when config file doesn't exist"""
        with patch.dict(os.environ, {'CONFIG_FILE': '/nonexistent/file.json'}):
            manager = get_config_manager()
            
            # Should still initialize with environment source
            assert len(manager.sources) >= 1
            assert any(isinstance(source, EnvironmentConfigSource) for source in manager.sources)
    
    def test_get_config_manager_invalid_file(self):
        """Test get_config_manager with invalid config file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('invalid json')
            file_path = f.name
        
        try:
            with patch.dict(os.environ, {'CONFIG_FILE': file_path}):
                manager = get_config_manager()
                
                # Should still initialize with environment source
                assert len(manager.sources) >= 1
                assert any(isinstance(source, EnvironmentConfigSource) for source in manager.sources)
        finally:
            os.unlink(file_path)
