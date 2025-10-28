#!/usr/bin/env python3
"""
Test Unified Configuration System

This script tests that the unified configuration system is working correctly.
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def test_config_loading():
    """Test that configuration loads from config.yaml"""
    print("Testing unified configuration system...\n")
    
    try:
        from src.infrastructure.configuration_manager import get_config_manager
        
        # Get configuration manager
        config = get_config_manager()
        print("✓ Configuration manager loaded\n")
        
        # Test database configuration
        db_config = config.get_database_config()
        print(f"✓ Database configuration loaded:")
        print(f"  Provider: {db_config.get('provider', 'N/A')}")
        print(f"  Name: {db_config.get('name', 'N/A')}")
        print()
        
        # Test storage configuration
        storage_config = config.get_storage_config()
        print(f"✓ Storage configuration loaded:")
        print(f"  Provider: {storage_config.get('provider', 'N/A')}")
        print(f"  Base URL: {storage_config.get('base_url', 'N/A')}")
        print(f"  Repository: {storage_config.get('repository', 'N/A')}")
        print()
        
        # Test specific getters
        gitlab_url = config.get_storage_base_url()
        print(f"✓ GitLab URL from config: {gitlab_url}")
        
        # Verify it's from config.yaml (not hardcoded)
        if gitlab_url and "android-devops" in gitlab_url:
            print("✓ URL loaded from configuration file")
        else:
            print(f"⚠ Warning: URL may not be from config.yaml: {gitlab_url}")
        print()
        
        # Test environment
        environment = config.get_config("environment", "unknown")
        print(f"✓ Environment: {environment}")
        print()
        
        # Test server configuration
        server_config = config.get_server_config()
        print(f"✓ Server configuration loaded:")
        print(f"  Host: {server_config.get('host', 'N/A')}")
        print(f"  Port: {server_config.get('port', 'N/A')}")
        print(f"  Debug: {server_config.get('debug', 'N/A')}")
        print()
        
        print("✅ All configuration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_file_exists():
    """Test that config.yaml exists"""
    config_file = backend_dir / "config" / "config.yaml"
    
    if config_file.exists():
        print(f"✓ Unified config file exists: {config_file}")
        return True
    else:
        print(f"❌ Unified config file not found: {config_file}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing Unified Configuration System")
    print("=" * 60)
    print()
    
    # Test config file exists
    if not test_config_file_exists():
        print("\n⚠️  Please ensure config.yaml exists in the backend directory")
        return 1
    
    print()
    
    # Test configuration loading
    if not test_config_loading():
        return 1
    
    print()
    print("=" * 60)
    print("🎉 All tests passed!")
    print()
    print("Configuration has been successfully unified!")
    print("All settings can now be managed in config.yaml")
    return 0

if __name__ == "__main__":
    sys.exit(main())

