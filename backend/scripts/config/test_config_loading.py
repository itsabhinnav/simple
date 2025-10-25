#!/usr/bin/env python3
"""
Configuration Test Script

This script tests the configuration loading to verify the correct paths are being used.
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

# Set environment variable
os.environ["ENVIRONMENT"] = "development"

from src.infrastructure.configuration_manager import get_config_manager


def test_configuration():
    """Test configuration loading"""
    print("🔧 Testing Configuration Loading")
    print("=" * 40)
    
    print(f"Current working directory: {os.getcwd()}")
    print(f"Environment variable: {os.environ.get('ENVIRONMENT', 'Not set')}")
    
    # Check if config files exist
    config_dir = Path("backend/config")
    dev_config = config_dir / "development.json"
    
    print(f"Config directory: {config_dir}")
    print(f"Development config exists: {dev_config.exists()}")
    
    if dev_config.exists():
        print(f"Development config path: {dev_config.absolute()}")
    
    # Test configuration manager
    try:
        config_manager = get_config_manager()
        
        print(f"\n📊 Configuration Manager Results:")
        print(f"Environment: {config_manager.get_config('environment')}")
        print(f"Database Name: {config_manager.get_database_name()}")
        print(f"Data Directory: {config_manager.get_config('database.data_directory')}")
        print(f"Cache Directory: {config_manager.get_config('database.cache_directory')}")
        
        # Test database paths
        db_name = config_manager.get_database_name()
        data_dir = config_manager.get_config('database.data_directory', 'data')
        cache_dir = config_manager.get_config('database.cache_directory', 'data/cache')
        
        print(f"\n📁 Expected Database Paths:")
        print(f"Data DB: {data_dir}/{db_name}")
        print(f"Cache DB: {cache_dir}/{db_name}")
        
        # Check if files exist
        data_db_path = Path(data_dir) / db_name
        cache_db_path = Path(cache_dir) / db_name
        
        print(f"\n🗄️ Database File Status:")
        print(f"Data DB exists: {data_db_path.exists()} - {data_db_path}")
        print(f"Cache DB exists: {cache_db_path.exists()} - {cache_db_path}")
        
        return data_db_path.exists() and cache_db_path.exists()
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    print("🚀 Configuration Test")
    print("=" * 30)
    
    success = test_configuration()
    
    if success:
        print("\n✅ Configuration test passed!")
    else:
        print("\n❌ Configuration test failed!")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
