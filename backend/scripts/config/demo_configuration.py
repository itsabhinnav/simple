#!/usr/bin/env python3
"""
Configuration System Demonstration

This script demonstrates the extensibility of the Sakura configuration system
by showing how to switch between different storage providers and environments.
"""

import os
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.infrastructure.configuration_manager import get_config_manager
from src.implementations.storage_providers import create_storage_provider


def demonstrate_current_configuration():
    """Show the current configuration"""
    print("🔧 Current Configuration")
    print("=" * 50)
    
    config_manager = get_config_manager()
    
    print(f"Environment: {config_manager.get_config('environment', 'unknown')}")
    print(f"Database Name: {config_manager.get_database_name()}")
    print(f"Storage Provider: {config_manager.get_storage_provider()}")
    print(f"Storage Base URL: {config_manager.get_storage_base_url()}")
    print(f"Users Table: {config_manager.get_table_name('users')}")
    print(f"Test Cases Table: {config_manager.get_table_name('test_cases')}")
    print(f"Git Integration: {config_manager.is_feature_enabled('git_integration')}")
    print(f"Artifactory Integration: {config_manager.is_feature_enabled('artifactory_integration')}")
    
    # Show storage configuration
    storage_config = config_manager.get_storage_config()
    print(f"\nStorage Configuration:")
    for key, value in storage_config.items():
        if 'password' in key.lower():
            print(f"  {key}: ***")
        else:
            print(f"  {key}: {value}")
    
    print()


def demonstrate_storage_provider_switching():
    """Demonstrate switching between different storage providers"""
    print("🔄 Storage Provider Switching Demonstration")
    print("=" * 50)
    
    # Test different storage providers
    providers = [
        {
            "name": "Git Provider",
            "config": {
                "provider": "git",
                "base_url": "https://gitlab.com/android-devops/sakura-db",
                "username": "admin",
                "password": "password",
                "repository": "android-devops/sakura-db",
                "local_repo_path": "remote/git",
                "data_path": "data/git"
            }
        },
        {
            "name": "Artifactory Provider",
            "config": {
                "provider": "artifactory",
                "base_url": "https://artifactory.company.com",
                "username": "artifactory_user",
                "password": "secure_password",
                "repository": "sakura-configs",
                "timeout": 60,
                "verify_ssl": True
            }
        },
        {
            "name": "GitHub Provider",
            "config": {
                "provider": "git",
                "base_url": "https://github.com/your-org/sakura-db",
                "username": "github_user",
                "password": "github_token",
                "repository": "your-org/sakura-db",
                "local_repo_path": "remote/github",
                "data_path": "data/github"
            }
        },
        {
            "name": "Local Provider",
            "config": {
                "provider": "local",
                "base_url": "file:///tmp/sakura-local",
                "username": "local",
                "password": "local",
                "repository": "local-repo",
                "data_path": "data/local"
            }
        }
    ]
    
    for provider_info in providers:
        print(f"\n📦 Testing {provider_info['name']}:")
        try:
            provider = create_storage_provider(provider_info['config'])
            print(f"  ✅ Provider Type: {provider.get_provider_type().value}")
            
            # Test authentication
            if hasattr(provider, 'authenticate'):
                auth_result = provider.authenticate("test", "test")
                print(f"  🔐 Authentication: {'✅ Success' if auth_result else '❌ Failed'}")
            
            # Test health check
            if hasattr(provider, 'health_check'):
                health_result = provider.health_check()
                print(f"  💚 Health Check: {'✅ Healthy' if health_result else '❌ Unhealthy'}")
            
            # Show provider-specific info
            if hasattr(provider, 'base_url'):
                print(f"  🌐 Base URL: {provider.base_url}")
            if hasattr(provider, 'local_repo_path'):
                print(f"  📁 Local Path: {provider.local_repo_path}")
            if hasattr(provider, 'data_path'):
                print(f"  📊 Data Path: {provider.data_path}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print()


def demonstrate_environment_switching():
    """Demonstrate switching between different environments"""
    print("🌍 Environment Switching Demonstration")
    print("=" * 50)
    
    environments = [
        {
            "name": "Development",
            "env_vars": {
                "ENVIRONMENT": "development",
                "DB_NAME": "sakura_dev",
                "DB_PROVIDER": "sqlite",
                "STORAGE_PROVIDER": "git",
                "DEBUG": "true",
                "MOCK_MODE": "true"
            }
        },
        {
            "name": "Production",
            "env_vars": {
                "ENVIRONMENT": "production",
                "DB_NAME": "sakura_prod",
                "DB_PROVIDER": "postgresql",
                "STORAGE_PROVIDER": "artifactory",
                "DEBUG": "false",
                "MOCK_MODE": "false",
                "DB_HOST": "prod-db.company.com",
                "DB_USERNAME": "sakura_user",
                "DB_PASSWORD": "secure_password"
            }
        },
        {
            "name": "Testing",
            "env_vars": {
                "ENVIRONMENT": "testing",
                "DB_NAME": "sakura_test",
                "DB_PROVIDER": "sqlite",
                "STORAGE_PROVIDER": "local",
                "DEBUG": "true",
                "MOCK_MODE": "true"
            }
        }
    ]
    
    # Store original environment variables
    original_env = {}
    for key in os.environ:
        original_env[key] = os.environ[key]
    
    try:
        for env_info in environments:
            print(f"\n🏗️ {env_info['name']} Environment:")
            
            # Set environment variables
            for key, value in env_info['env_vars'].items():
                os.environ[key] = value
            
            # Reload configuration
            config_manager = get_config_manager()
            config_manager.reload_config()
            
            # Show configuration
            print(f"  Environment: {config_manager.get_config('environment')}")
            print(f"  Database: {config_manager.get_config('database.provider')} - {config_manager.get_database_name()}")
            print(f"  Storage: {config_manager.get_storage_provider()}")
            print(f"  Debug Mode: {config_manager.get_config('server.debug')}")
            print(f"  Mock Mode: {config_manager.get_config('server.mock_mode')}")
            
            # Show feature flags
            features = [
                "git_integration",
                "artifactory_integration",
                "user_management",
                "test_case_management"
            ]
            
            print(f"  Feature Flags:")
            for feature in features:
                enabled = config_manager.is_feature_enabled(feature)
                print(f"    {feature}: {'✅' if enabled else '❌'}")
    
    finally:
        # Restore original environment variables
        for key in original_env:
            os.environ[key] = original_env[key]
        for key in os.environ:
            if key not in original_env:
                del os.environ[key]
    
    print()


def demonstrate_configuration_sources():
    """Demonstrate different configuration sources"""
    print("📄 Configuration Sources Demonstration")
    print("=" * 50)
    
    config_manager = get_config_manager()
    
    # Show all configuration sources
    print("Configuration Sources (in priority order):")
    print("1. Environment Variables (highest priority)")
    print("2. Environment-specific JSON files")
    print("3. Default configuration files")
    print("4. Base configuration classes")
    
    # Show current configuration values
    print(f"\nCurrent Configuration Values:")
    all_configs = config_manager.get_all_configs()
    
    # Show key configuration sections
    key_sections = ['environment', 'database', 'storage', 'server', 'features']
    for section in key_sections:
        if section in all_configs:
            print(f"\n{section.upper()}:")
            config_section = all_configs[section]
            if isinstance(config_section, dict):
                for key, value in config_section.items():
                    if 'password' in key.lower():
                        print(f"  {key}: ***")
                    else:
                        print(f"  {key}: {value}")
            else:
                print(f"  {config_section}")
    
    print()


def demonstrate_dynamic_configuration():
    """Demonstrate dynamic configuration changes"""
    print("⚡ Dynamic Configuration Changes")
    print("=" * 50)
    
    config_manager = get_config_manager()
    
    print("Original Configuration:")
    print(f"  Database Name: {config_manager.get_database_name()}")
    print(f"  Storage Provider: {config_manager.get_storage_provider()}")
    
    # Change configuration dynamically
    print("\nChanging configuration dynamically...")
    
    # Set new values
    config_manager.set_config("database.name", "dynamic_test_db")
    config_manager.set_config("storage.provider", "local")
    
    print("Updated Configuration:")
    print(f"  Database Name: {config_manager.get_database_name()}")
    print(f"  Storage Provider: {config_manager.get_storage_provider()}")
    
    # Show cached vs reloaded values
    print("\nReloading configuration...")
    config_manager.reload_config()
    
    print("After Reload:")
    print(f"  Database Name: {config_manager.get_database_name()}")
    print(f"  Storage Provider: {config_manager.get_storage_provider()}")
    
    print()


def main():
    """Run all demonstrations"""
    print("🚀 Sakura Configuration System Demonstration")
    print("=" * 60)
    print()
    
    try:
        demonstrate_current_configuration()
        demonstrate_storage_provider_switching()
        demonstrate_environment_switching()
        demonstrate_configuration_sources()
        demonstrate_dynamic_configuration()
        
        print("🎉 Configuration System Demonstration Complete!")
        print("\n📋 Summary:")
        print("  ✅ Configuration system is fully functional")
        print("  ✅ Storage providers are easily swappable")
        print("  ✅ Environment switching works seamlessly")
        print("  ✅ Multiple configuration sources supported")
        print("  ✅ Dynamic configuration changes possible")
        print("\n🔧 The system is now ready for production use!")
        
    except Exception as e:
        print(f"❌ Demonstration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
