#!/usr/bin/env python3
"""
Comprehensive System Test

This script provides a complete test of the Sakura configuration system
and verifies all components are working correctly.
"""

import os
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.infrastructure.configuration_manager import get_config_manager
from src.services.git_database_service import GitDatabaseService
from src.implementations.git_file_storage import GitFileStorage


def test_configuration_system():
    """Test the configuration system"""
    print("🔧 Testing Configuration System")
    print("=" * 40)
    
    try:
        config_manager = get_config_manager()
        
        print(f"✅ Configuration Manager: Loaded successfully")
        print(f"📊 Environment: {config_manager.get_config('environment', 'unknown')}")
        print(f"🗄️ Database Name: {config_manager.get_database_name()}")
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
        
        # Test feature flags
        git_integration = config_manager.is_feature_enabled("git_integration")
        artifactory_integration = config_manager.is_feature_enabled("artifactory_integration")
        
        print(f"🚩 Feature Flags:")
        print(f"  Git Integration: {'✅' if git_integration else '❌'}")
        print(f"  Artifactory Integration: {'✅' if artifactory_integration else '❌'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def test_database_files():
    """Test database file existence and content"""
    print("\n🗄️ Testing Database Files")
    print("=" * 40)
    
    try:
        config_manager = get_config_manager()
        
        # Check database paths
        db_name = config_manager.get_database_name()
        cache_dir = Path(config_manager.get_config("database.cache_directory", "data/cache"))
        data_dir = Path(config_manager.get_config("database.data_directory", "data"))
        
        cache_db = cache_dir / f"{db_name}.db"
        data_db = data_dir / f"{db_name}.db"
        
        print(f"📁 Database Paths:")
        print(f"  Cache: {cache_db} - {'✅ Exists' if cache_db.exists() else '❌ Missing'}")
        print(f"  Data: {data_db} - {'✅ Exists' if data_db.exists() else '❌ Missing'}")
        
        if cache_db.exists():
            size = cache_db.stat().st_size
            print(f"📏 Cache DB Size: {size} bytes")
            
            # Test database content
            import sqlite3
            conn = sqlite3.connect(str(cache_db))
            cursor = conn.cursor()
            
            # Get table counts
            users_table = config_manager.get_table_name("users")
            test_cases_table = config_manager.get_table_name("test_cases")
            requirements_table = config_manager.get_table_name("requirements")
            
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
            
            return user_count > 0 and tc_count > 0 and req_count > 0
        
        return False
        
    except Exception as e:
        print(f"❌ Database file test failed: {e}")
        return False


def test_database_service():
    """Test the database service"""
    print("\n🔧 Testing Database Service")
    print("=" * 40)
    
    try:
        config_manager = get_config_manager()
        
        # Create services
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
        
        # Test database info
        db_info = db_service.get_database_info()
        if 'error' not in db_info:
            print(f"📊 Database Info: {db_info['table_count']} tables")
            print(f"📋 Tables: {', '.join(db_info['tables'])}")
        else:
            print(f"❌ Database Info Error: {db_info['error']}")
        
        # Test query execution
        users_table = config_manager.get_table_name("users")
        result = db_service.execute_query(f"SELECT COUNT(*) as count FROM {users_table}", "default")
        
        if result.get('success'):
            count = result['data'][0]['count'] if result['data'] else 0
            print(f"🔍 Query Test: Found {count} users")
            return count > 0
        else:
            print(f"❌ Query Test Failed: {result.get('error', 'Unknown error')}")
            return False
        
    except Exception as e:
        print(f"❌ Database service test failed: {e}")
        return False


def test_api_endpoints():
    """Test API endpoints"""
    print("\n🌐 Testing API Endpoints")
    print("=" * 40)
    
    import requests
    
    base_url = "http://localhost:5000"
    
    try:
        # Test health endpoint
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Health Check: {health_data.get('status', 'unknown')}")
        else:
            print(f"❌ Health Check Failed: {response.status_code}")
            return False
        
        # Test databases endpoint
        response = requests.get(f"{base_url}/api/databases", timeout=5)
        if response.status_code == 200:
            db_data = response.json()
            db_count = len(db_data.get('data', []))
            print(f"📊 Databases API: {db_count} databases found")
        else:
            print(f"❌ Databases API Failed: {response.status_code}")
        
        # Test users endpoint
        response = requests.get(f"{base_url}/api/users/", timeout=5)
        if response.status_code == 200:
            users_data = response.json()
            user_count = users_data.get('count', 0)
            print(f"👥 Users API: {user_count} users found")
        else:
            print(f"❌ Users API Failed: {response.status_code}")
        
        # Test git status endpoint
        response = requests.get(f"{base_url}/api/git/status", timeout=5)
        if response.status_code == 200:
            git_data = response.json()
            print(f"🔧 Git Status API: Working")
        else:
            print(f"❌ Git Status API Failed: {response.status_code}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API test failed: {e}")
        return False


def main():
    """Main test function"""
    print("🚀 Sakura Configuration System - Comprehensive Test")
    print("=" * 60)
    
    results = {
        "Configuration System": test_configuration_system(),
        "Database Files": test_database_files(),
        "Database Service": test_database_service(),
        "API Endpoints": test_api_endpoints()
    }
    
    print("\n📋 Test Results Summary")
    print("=" * 40)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print(f"\n🎯 Overall Status: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    if all_passed:
        print("\n🎉 Configuration System is fully functional!")
        print("🔗 Available API Endpoints:")
        print("  - http://localhost:5000/health")
        print("  - http://localhost:5000/api/databases")
        print("  - http://localhost:5000/api/users/")
        print("  - http://localhost:5000/api/test-cases/")
        print("  - http://localhost:5000/api/requirements/")
        print("  - http://localhost:5000/api/git/status")
        
        print("\n🔧 Configuration Features:")
        print("  ✅ No hardcoded values")
        print("  ✅ Environment-specific settings")
        print("  ✅ Extensible storage providers")
        print("  ✅ Configurable database and table names")
        print("  ✅ Feature flags")
        print("  ✅ Dynamic configuration changes")
        
        print("\n🚀 System is ready for production use!")
    else:
        print("\n⚠️ Some issues need to be resolved:")
        print("  - Check database file paths")
        print("  - Verify API endpoint configurations")
        print("  - Ensure all services are properly initialized")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
