"""
Configuration Manager

This module provides a centralized configuration management system
that supports multiple configuration sources and environments.
"""

import os
import sys
import json
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from abc import ABC, abstractmethod

# Optional YAML import
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

from config.environments import ApplicationConfig, get_config
from src.interfaces.providers import IConfigurationProvider
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class ConfigurationSource(ABC):
    """Abstract base class for configuration sources"""
    
    @abstractmethod
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from source"""
        pass
    
    @abstractmethod
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to source"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if configuration source is available"""
        pass


class EnvironmentConfigSource(ConfigurationSource):
    """Configuration source from environment variables"""
    
    def __init__(self, prefix: str = ""):
        self.prefix = prefix
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        config = {}
        for key, value in os.environ.items():
            if self.prefix and not key.startswith(self.prefix):
                continue
            
            # Remove prefix if present
            config_key = key[len(self.prefix):] if self.prefix else key
            
            # Convert string values to appropriate types
            config[config_key] = self._convert_value(value)
        
        return config
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Environment variables cannot be saved"""
        logger.warning("Cannot save configuration to environment variables")
        return False
    
    def is_available(self) -> bool:
        """Environment variables are always available"""
        return True
    
    def _convert_value(self, value: str) -> Union[str, int, float, bool, List[str]]:
        """Convert string value to appropriate type"""
        # Boolean conversion
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Numeric conversion
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # List conversion (comma-separated)
        if ',' in value:
            return [item.strip() for item in value.split(',')]
        
        return value


class FileConfigSource(ConfigurationSource):
    """Configuration source from files (JSON, YAML)"""
    
    def __init__(self, file_path: str, file_format: str = "auto"):
        self.file_path = Path(file_path)
        self.file_format = file_format
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if not self.file_path.exists():
            logger.warning(f"Configuration file not found: {self.file_path}")
            return {}
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                if self.file_format == "json" or (self.file_format == "auto" and self.file_path.suffix == '.json'):
                    return json.load(f)
                elif self.file_format == "yaml" or (self.file_format == "auto" and self.file_path.suffix in ['.yaml', '.yml']):
                    if YAML_AVAILABLE:
                        return yaml.safe_load(f)
                    else:
                        logger.error(f"YAML support not available. Install PyYAML to use YAML configuration files.")
                        return {}
                else:
                    logger.error(f"Unsupported file format: {self.file_format}")
                    return {}
        except Exception as e:
            logger.error(f"Failed to load configuration from {self.file_path}: {e}")
            return {}
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file"""
        try:
            # Ensure directory exists
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                if self.file_format == "json" or (self.file_format == "auto" and self.file_path.suffix == '.json'):
                    json.dump(config, f, indent=2, default=str)
                elif self.file_format == "yaml" or (self.file_format == "auto" and self.file_path.suffix in ['.yaml', '.yml']):
                    if YAML_AVAILABLE:
                        yaml.dump(config, f, default_flow_style=False)
                    else:
                        logger.error(f"YAML support not available. Install PyYAML to save YAML configuration files.")
                        return False
                else:
                    logger.error(f"Unsupported file format: {self.file_format}")
                    return False
            
            logger.info(f"Configuration saved to {self.file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration to {self.file_path}: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if file is available"""
        return self.file_path.exists()


class DatabaseConfigSource(ConfigurationSource):
    """Configuration source from database"""
    
    def __init__(self, database_provider, table_name: str = "configurations"):
        self.database_provider = database_provider
        self.table_name = table_name
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from database"""
        try:
            query = f"SELECT config_key, config_value FROM {self.table_name}"
            result = self.database_provider.execute_query(query)
            
            config = {}
            for row in result.get('data', []):
                config[row['config_key']] = self._convert_value(row['config_value'])
            
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration from database: {e}")
            return {}
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to database"""
        try:
            queries = []
            for key, value in config.items():
                # Convert value to string for storage
                str_value = str(value)
                query = f"""
                    INSERT OR REPLACE INTO {self.table_name} (config_key, config_value, updated_at)
                    VALUES ('{key}', '{str_value}', CURRENT_TIMESTAMP)
                """
                queries.append(query)
            
            return self.database_provider.execute_transaction(queries)
        except Exception as e:
            logger.error(f"Failed to save configuration to database: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if database is available"""
        try:
            return self.database_provider.connect()
        except Exception:
            return False
    
    def _convert_value(self, value: str) -> Union[str, int, float, bool, List[str]]:
        """Convert string value to appropriate type"""
        # Boolean conversion
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Numeric conversion
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # List conversion (comma-separated)
        if ',' in value:
            return [item.strip() for item in value.split(',')]
        
        return value


class ConfigurationManager(IConfigurationProvider):
    """Centralized configuration manager"""
    
    def __init__(self, environment: str = None):
        self.environment = environment or os.getenv("ENVIRONMENT", "development")
        self.sources: List[ConfigurationSource] = []
        self._config_cache: Dict[str, Any] = {}
        self._base_config: Optional[ApplicationConfig] = None
        
        # Initialize with default sources
        self._initialize_default_sources()
    
    def _initialize_default_sources(self):
        """Initialize default configuration sources"""
        # Environment variables (highest priority)
        self.add_source(EnvironmentConfigSource())

        # File-based configuration - ONLY use config.yaml (unified configuration)
        config_candidates = [
            "backend/config/config.yaml",  # Unified configuration file (primary)
            "config/config.yaml",  # Fallback location
            "backend/config.yaml",  # Legacy location
            "config.yaml",  # Fallback location
        ]

        # When running as a PyInstaller-frozen exe the working directory is
        # the user's app dir (writable) but config.yaml lives in the bundled
        # _MEIPASS extraction tree. Probe there first so the bundled config
        # wins over a stale on-disk copy.
        search_roots = [Path.cwd()]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            search_roots.insert(0, Path(meipass))

        config_loaded = False
        for root in search_roots:
            for rel in config_candidates:
                candidate = (root / rel) if not Path(rel).is_absolute() else Path(rel)
                if candidate.exists():
                    self.add_source(FileConfigSource(str(candidate)))
                    logger.info(f"Configuration loaded from: {candidate}")
                    config_loaded = True
                    break
            if config_loaded:
                break

        if not config_loaded:
            logger.warning("No config.yaml found. Using default configuration from code.")
    
    def add_source(self, source: ConfigurationSource):
        """Add a configuration source"""
        if source.is_available():
            self.sources.append(source)
            logger.info(f"Added configuration source: {type(source).__name__}")
        else:
            logger.warning(f"Configuration source not available: {type(source).__name__}")
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value with fallback chain"""
        # Check cache first
        if key in self._config_cache:
            return self._config_cache[key]
        
        # Try sources in reverse order (last added has highest priority)
        for source in reversed(self.sources):
            try:
                config = source.load_config()
                value = self._get_nested_value(config, key)
                if value is not None:
                    self._config_cache[key] = value
                    return value
            except Exception as e:
                logger.warning(f"Failed to load config from {type(source).__name__}: {e}")
        
        # Try base configuration
        if self._base_config:
            value = self._get_nested_value(self._base_config.to_dict(), key)
            if value is not None:
                self._config_cache[key] = value
                return value
        
        return default
    
    def set_config(self, key: str, value: Any) -> bool:
        """Set configuration value"""
        # Update cache
        self._config_cache[key] = value
        
        # Try to save to first available writable source
        for source in self.sources:
            try:
                if hasattr(source, 'save_config'):
                    config = source.load_config()
                    config[key] = value
                    if source.save_config(config):
                        logger.info(f"Configuration {key} saved to {type(source).__name__}")
                        return True
            except Exception as e:
                logger.warning(f"Failed to save config to {type(source).__name__}: {e}")
        
        logger.warning(f"Failed to save configuration {key} to any source")
        return False
    
    def get_all_configs(self) -> Dict[str, Any]:
        """Get all configuration values"""
        all_configs = {}
        
        # Start with base configuration
        if self._base_config:
            all_configs.update(self._base_config.to_dict())
        
        # Override with source configurations
        for source in reversed(self.sources):
            try:
                config = source.load_config()
                all_configs.update(config)
            except Exception as e:
                logger.warning(f"Failed to load config from {type(source).__name__}: {e}")
        
        # Add cached values
        all_configs.update(self._config_cache)
        
        return all_configs
    
    def reload_config(self) -> bool:
        """Reload configuration from all sources"""
        try:
            self._config_cache.clear()
            
            # Reload base configuration
            self._base_config = get_config(self.environment)
            
            # Reload from sources
            for source in self.sources:
                try:
                    config = source.load_config()
                    self._config_cache.update(config)
                except Exception as e:
                    logger.warning(f"Failed to reload config from {type(source).__name__}: {e}")
            
            logger.info("Configuration reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            return False
    
    def validate_config(self) -> bool:
        """Validate configuration"""
        try:
            # Validate base configuration
            if self._base_config:
                # Check required fields
                required_fields = [
                    "database.name",
                    "authentication.default_admin_username",
                ]
                
                for field in required_fields:
                    if not self._get_nested_value(self._base_config.to_dict(), field):
                        logger.error(f"Required configuration field missing: {field}")
                        return False
            
            # Validate database connection
            db_config = self.get_config("database")
            if db_config and isinstance(db_config, dict):
                # Add database validation logic here
                pass
            
            # Validate storage configuration
            storage_config = self.get_config("storage")
            if storage_config and isinstance(storage_config, dict):
                # Add storage validation logic here
                pass
            
            logger.info("Configuration validation passed")
            return True
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def _get_nested_value(self, config: Dict[str, Any], key: str) -> Any:
        """Get nested value from configuration dictionary"""
        keys = key.split('.')
        value = config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return self.get_config("database", {})
    
    def get_storage_config(self) -> Dict[str, Any]:
        """Get storage configuration"""
        return self.get_config("storage", {})
    
    def get_authentication_config(self) -> Dict[str, Any]:
        """Get authentication configuration"""
        return self.get_config("authentication", {})
    
    def get_server_config(self) -> Dict[str, Any]:
        """Get server configuration"""
        return self.get_config("server", {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self.get_config("logging", {})
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled"""
        features = self.get_config("features", {})
        return features.get(feature_name, False)
    
    def get_table_name(self, table_type: str) -> str:
        """Get table name for a specific type"""
        table_names = self.get_config("database.table_names", {})
        return table_names.get(table_type, table_type)
    
    def get_database_name(self) -> str:
        """Get database name"""
        return self.get_config("database.name", "sakura_db")
    
    def get_storage_provider(self) -> str:
        """Get storage provider type"""
        return self.get_config("storage.provider", "git")
    
    def get_storage_repository(self) -> str:
        """Get storage repository (empty by default - remote sync disabled)."""
        return self.get_config("storage.repository", "")
    
    def get_test_case_dropdowns(self) -> Dict[str, Any]:
        """Return the configurable test-case dropdown options block.

        Shape::

            {
              "multi_value_fields": [<field>, ...],
              "feature":           [<option>, ...],
              "test_type":         [<option>, ...],
              "region":            [<option>, ...],
              "brand":             [<option>, ...],
              "vehicle_variant":   [<option>, ...],
              "vehicle_mode":      [<option>, ...],
              "env_dependency":    [<option>, ...],
              "regulation":        [<option>, ...],
              "priority":          [<option>, ...],
              "testsuite_type":    [<option>, ...],
            }

        Returns an empty dict (with empty lists) if config is missing so
        callers can rely on `.get(field, [])` without KeyError handling.
        """
        defaults: Dict[str, Any] = {
            "multi_value_fields": [
                "reference_document", "associated_requirement_id", "screen_id",
                "feature", "region", "brand", "vehicle_variant", "vehicle_mode",
                "env_dependency", "testsuite_type",
            ],
            "feature": [],
            "test_type": ["Positive", "Negative", "Abnormal", "Boundary"],
            "region": [],
            "brand": [],
            "vehicle_variant": [],
            "vehicle_mode": ["Common", "EV", "HEV", "ICE", "PHEV"],
            "env_dependency": [],
            "regulation": ["Yes", "No"],
            "priority": ["P1", "P2", "P3", "P4"],
            "testsuite_type": [],
        }
        loaded = self.get_config("test_case_dropdowns", {}) or {}
        if not isinstance(loaded, dict):
            return defaults
        merged = {**defaults, **loaded}
        # Coerce each value list to a list of strings to keep the API stable
        # (YAML may decode "Yes"/"No" as booleans, etc.).
        for key, value in list(merged.items()):
            if key == "multi_value_fields":
                merged[key] = [str(v) for v in (value or [])]
            elif isinstance(value, list):
                merged[key] = [str(v) for v in value]
        return merged

    def get_storage_base_url(self) -> str:
        """Get storage base URL.

        Remote/git DB sync is permanently disabled, so callers should not rely
        on this for live network operations. Returns an empty string when no
        URL is configured instead of falling back to a hardcoded remote.
        """
        url = self.get_config("storage.base_url")
        if not url:
            logger.debug("storage.base_url not configured (remote sync disabled)")
            return ""
        return url


# Global configuration manager instance
config_manager = ConfigurationManager()


def get_config_manager() -> ConfigurationManager:
    """Get the global configuration manager"""
    return config_manager


def get_config_value(key: str, default: Any = None) -> Any:
    """Convenience function to get configuration value"""
    return config_manager.get_config(key, default)


def set_config_value(key: str, value: Any) -> bool:
    """Convenience function to set configuration value"""
    return config_manager.set_config(key, value)
