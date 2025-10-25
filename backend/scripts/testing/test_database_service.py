#!/usr/bin/env python3
"""
Database Test Script

This script tests the database service directly to verify it can find and access the database.
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.infrastructure.configuration_manager import get_config_manager
from src.services.git_database_service import GitDatabaseService
from src.implementations.git_file_storage import GitFileStorage


def test_database_service():
    """Test the database service directly"""
    print("🧪 Testing Database Service...")
    
    # Get configuration
    config_manager = get_config_manager()
    
    # Create Git file storage
    git_storage = GitFileStorage(
        repo_url=config_manager.get_storage_base_url(),
        local_repo_path=config_manager.get_config("storage.local_repo_path", "remote"),
        data_path=config_manager.get_config("storage.data_path", "data")
    )
    
    # Create database service
    db_service = GitDatabaseService(git_storage)
    
    print(f"📊 Database Service Configuration:")
    print(f"  Database Name: {db_service.database_name}")
    print(f"  Data Path: {db_service.data_path}")
    print(f"  Cache Path: {db_service.cache_path}")
    
    # Test list databases
    print(f"\n📋 Testing list_databases()...")
    databases = db_service.list_databases("default")
    print(f"  Found {len(databases)} databases:")
    for db in databases:
        print(f"    - {db}")
    
    # Test database info
    print(f"\n📊 Testing get_database_info()...")
    db_info = db_service.get_database_info()
    print(f"  Database Info: {db_info}")
    
    # Test execute query
    print(f"\n🔍 Testing execute_query()...")
    try:
        users_table = config_manager.get_table_name("users")
        result = db_service.execute_query(f"SELECT COUNT(*) as count FROM {users_table}", "default")
        print(f"  Query Result: {result}")
        
        if result.get('success') and result.get('data'):
            count = result['data'][0]['count'] if result['data'] else 0
            print(f"  👥 Users in database: {count}")
        else:
            print(f"  ❌ Query failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"  ❌ Query error: {e}")
    
    return len(databases) > 0


def main():
    """Main function"""
    print("🔧 Database Service Test")
    print("=" * 30)
    
    try:
        success = test_database_service()
        
        if success:
            print("\n✅ Database service test completed!")
        else:
            print("\n❌ Database service test failed!")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
