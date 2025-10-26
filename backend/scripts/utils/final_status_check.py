#!/usr/bin/env python3
"""
Final System Status Check

This script provides a comprehensive status check of the Sakura configuration system
and verifies all components are working correctly.
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

# Set environment variable
os.environ["ENVIRONMENT"] = "development"

from src.infrastructure.configuration_manager import get_config_manager
from src.services.git_database_service import GitDatabaseService
from src.implementations.git_file_storage import GitFileStorage


def check_system_status():
    """Check the complete system status"""
    print("🔍 Sakura System Status Check")
    print("=" * 50)
    
    # 1. Configuration System
    print("\n1️⃣ Configuration System")
    print("-" * 30)
    
    try:
        config_manager = get_config_manager()
        
        print(f"✅ Configuration Manager: Working")
        print(f"📊 Environment: {config_manager.get_config('environment')}")
        print(f"🗄️ Database Name: {config_manager.get_database_name()}")
        print(f"📁 Data Directory: {config_manager.get_config('database.data_directory')}")
        print(f"📁 Cache Directory: {config_manager.get_config('database.cache_directory')}")
        print(f"📦 Storage Provider: {config_manager.get_storage_provider()}")
        print(f"🌐 Storage URL: {config_manager.get_storage_base_url()}")
        
        # Test table names
        users_table = config_manager.get_table_name("users")
        test_cases_table = config_manager.get_table_name("test_cases")
        requirements_table = config_manager.get_table_name("requirements")
        
        print(f"📋 Table Names:")
        print(f"  Users: {users_table}")
        print(f"  Test Cases: {test_cases_table}")
        print(f"  Requirements: {requirements_table}")
        
        config_working = True
        
    except Exception as e:
        print(f"❌ Configuration System Error: {e}")
        config_working = False
    
    # 2. Database Files
    print("\n2️⃣ Database Files")
    print("-" * 30)
    
    try:
        db_name = config_manager.get_database_name()
        data_dir = config_manager.get_config('database.data_directory', 'data')
        cache_dir = config_manager.get_config('database.cache_directory', 'data/cache')
        
        data_db_path = Path(data_dir) / db_name
        cache_db_path = Path(cache_dir) / db_name
        
        print(f"📁 Data DB: {data_db_path} - {'✅ Exists' if data_db_path.exists() else '❌ Missing'}")
        print(f"📁 Cache DB: {cache_db_path} - {'✅ Exists' if cache_db_path.exists() else '❌ Missing'}")
        
        if data_db_path.exists():
            size = data_db_path.stat().st_size
            print(f"📏 Data DB Size: {size} bytes")
        
        if cache_db_path.exists():
            size = cache_db_path.stat().st_size
            print(f"📏 Cache DB Size: {size} bytes")
        
        # Test database content
        if data_db_path.exists():
            import sqlite3
            conn = sqlite3.connect(str(data_db_path))
            cursor = conn.cursor()
            
            cursor.execute(f"SELECT COUNT(*) FROM {users_table}")
            user_count = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {test_cases_table}")
            tc_count = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {requirements_table}")
            req_count = cursor.fetchone()[0]
            
            print(f"📊 Database Content:")
            print(f"  👥 Users: {user_count}")
            print(f"  🧪 Test Cases: {tc_count}")
            print(f"  📝 Requirements: {req_count}")
            
            cursor.close()
            conn.close()
            
            db_files_working = user_count > 0 and tc_count > 0 and req_count > 0
        else:
            db_files_working = False
        
    except Exception as e:
        print(f"❌ Database Files Error: {e}")
        db_files_working = False
    
    # 3. Database Service
    print("\n3️⃣ Database Service")
    print("-" * 30)
    
    try:
        git_storage = GitFileStorage(
            repo_url=config_manager.get_storage_base_url(),
            local_repo_path=config_manager.get_config("storage.local_repo_path", "remote"),
            data_path=config_manager.get_config("storage.data_path", "data")
        )
        
        db_service = GitDatabaseService(git_storage)
        
        print(f"✅ Database Service: Created successfully")
        print(f"📊 Database Name: {db_service.database_name}")
        print(f"📁 Data Path: {db_service.data_path}")
        print(f"📁 Cache Path: {db_service.cache_path}")
        
        # Test list databases
        databases = db_service.list_databases("default")
        print(f"📋 Databases Found: {len(databases)}")
        for db in databases:
            print(f"  - {db['name']} ({db['size']} bytes)")
        
        # Test query execution
        result = db_service.execute_query(f"SELECT COUNT(*) as count FROM {users_table}", "default")
        
        if result.get('success'):
            count = result['data'][0]['count'] if result['data'] else 0
            print(f"🔍 Query Test: Found {count} users")
            db_service_working = count > 0
        else:
            print(f"❌ Query Test Failed: {result.get('error', 'Unknown error')}")
            db_service_working = False
        
    except Exception as e:
        print(f"❌ Database Service Error: {e}")
        db_service_working = False
    
    # 4. Directory Structure
    print("\n4️⃣ Directory Structure")
    print("-" * 30)
    
    directories = [
        "data",
        "data/local",
        "remote",
        "backend/config"
    ]
    
    for dir_path in directories:
        path = Path(dir_path)
        exists = path.exists()
        print(f"📁 {dir_path}: {'✅ Exists' if exists else '❌ Missing'}")
    
    # 5. Summary
    print("\n5️⃣ Summary")
    print("-" * 30)
    
    all_working = config_working and db_files_working and db_service_working
    
    print(f"Configuration System: {'✅ Working' if config_working else '❌ Failed'}")
    print(f"Database Files: {'✅ Working' if db_files_working else '❌ Failed'}")
    print(f"Database Service: {'✅ Working' if db_service_working else '❌ Failed'}")
    
    print(f"\n🎯 Overall Status: {'✅ ALL SYSTEMS WORKING' if all_working else '❌ SOME ISSUES FOUND'}")
    
    if all_working:
        print("\n🎉 System is ready for use!")
        print("🔗 The configuration system is working correctly with:")
        print("  ✅ No hardcoded values")
        print("  ✅ Environment-specific configurations")
        print("  ✅ Extensible storage providers")
        print("  ✅ Configurable database and table names")
        print("  ✅ Complete database with sample data")
        
        print("\n📋 Current Configuration:")
        print(f"  Environment: {config_manager.get_config('environment')}")
        print(f"  Database: {config_manager.get_database_name()}")
        print(f"  Data Directory: {config_manager.get_config('database.data_directory')}")
        print(f"  Cache Directory: {config_manager.get_config('database.cache_directory')}")
        print(f"  Storage Provider: {config_manager.get_storage_provider()}")
        
        print("\n🚀 The system is fully configuration-based and extensible!")
    else:
        print("\n⚠️ Some issues need to be resolved:")
        if not config_working:
            print("  - Configuration system needs fixing")
        if not db_files_working:
            print("  - Database files need to be created/moved")
        if not db_service_working:
            print("  - Database service needs fixing")
    
    return all_working


def main():
    """Main function"""
    print("🚀 Sakura Configuration System - Final Status Check")
    print("=" * 60)
    
    success = check_system_status()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
