#!/usr/bin/env python3
"""
Database Sync Script

This script checks database paths and ensures the database is properly synced.
"""

import os
import sys
import shutil
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.infrastructure.configuration_manager import get_config_manager
from src.services.git_database_service import GitDatabaseService
from src.implementations.git_file_storage import GitFileStorage


def check_database_paths():
    """Check where databases are located"""
    print("🔍 Checking Database Paths...")
    
    config_manager = get_config_manager()
    
    # Get configuration paths
    db_name = config_manager.get_database_name()
    cache_dir = Path(config_manager.get_config("database.cache_directory", "data/cache"))
    data_dir = Path(config_manager.get_config("database.data_directory", "data"))
    
    print(f"📊 Database Name: {db_name}")
    print(f"📁 Cache Directory: {cache_dir}")
    print(f"📁 Data Directory: {data_dir}")
    
    # Check for database files
    cache_db = cache_dir / f"{db_name}.db"
    data_db = data_dir / f"{db_name}.db"
    
    print(f"\n🗄️ Database Files:")
    print(f"  Cache DB: {cache_db} - {'✅ Exists' if cache_db.exists() else '❌ Missing'}")
    print(f"  Data DB: {data_db} - {'✅ Exists' if data_db.exists() else '❌ Missing'}")
    
    # Check all .db files in both directories
    print(f"\n📋 All Database Files:")
    
    cache_files = list(cache_dir.glob("*.db")) if cache_dir.exists() else []
    data_files = list(data_dir.glob("*.db")) if data_dir.exists() else []
    
    print(f"  Cache Directory ({cache_dir}):")
    for db_file in cache_files:
        size = db_file.stat().st_size
        print(f"    - {db_file.name} ({size} bytes)")
    
    print(f"  Data Directory ({data_dir}):")
    for db_file in data_files:
        size = db_file.stat().st_size
        print(f"    - {db_file.name} ({size} bytes)")
    
    return cache_db, data_db, cache_files, data_files


def sync_databases():
    """Sync database files between directories"""
    print("\n🔄 Syncing Database Files...")
    
    cache_db, data_db, cache_files, data_files = check_database_paths()
    
    # Ensure directories exist
    cache_db.parent.mkdir(parents=True, exist_ok=True)
    data_db.parent.mkdir(parents=True, exist_ok=True)
    
    # If we have a database in cache but not in data, copy it
    if cache_db.exists() and not data_db.exists():
        print(f"📋 Copying {cache_db.name} from cache to data directory...")
        shutil.copy2(cache_db, data_db)
        print(f"✅ Copied to {data_db}")
    
    # If we have a database in data but not in cache, copy it
    elif data_db.exists() and not cache_db.exists():
        print(f"📋 Copying {data_db.name} from data to cache directory...")
        shutil.copy2(data_db, cache_db)
        print(f"✅ Copied to {cache_db}")
    
    # If both exist, check which is newer
    elif cache_db.exists() and data_db.exists():
        cache_time = cache_db.stat().st_mtime
        data_time = data_db.stat().st_mtime
        
        if cache_time > data_time:
            print(f"📋 Cache database is newer, copying to data directory...")
            shutil.copy2(cache_db, data_db)
            print(f"✅ Updated {data_db}")
        elif data_time > cache_time:
            print(f"📋 Data database is newer, copying to cache directory...")
            shutil.copy2(data_db, cache_db)
            print(f"✅ Updated {cache_db}")
        else:
            print(f"✅ Both databases are in sync")
    
    else:
        print(f"❌ No database files found in either location")
        return False
    
    return True


def test_database_connection():
    """Test database connection and show table contents"""
    print("\n🧪 Testing Database Connection...")
    
    config_manager = get_config_manager()
    db_name = config_manager.get_database_name()
    cache_dir = Path(config_manager.get_config("database.cache_directory", "data/cache"))
    cache_db = cache_dir / f"{db_name}.db"
    
    if not cache_db.exists():
        print(f"❌ Database file not found: {cache_db}")
        return False
    
    try:
        import sqlite3
        conn = sqlite3.connect(str(cache_db))
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"📋 Tables in database:")
        for table in tables:
            table_name = table[0]
            if table_name != 'sqlite_sequence':
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"  - {table_name}: {count} records")
        
        # Show sample data
        users_table = config_manager.get_table_name("users")
        cursor.execute(f"SELECT username, email, role FROM {users_table} LIMIT 3")
        users = cursor.fetchall()
        
        if users:
            print(f"\n👥 Sample Users:")
            for user in users:
                print(f"  - {user[0]} ({user[1]}) - {user[2]}")
        
        cursor.close()
        conn.close()
        
        print(f"✅ Database connection successful!")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def main():
    """Main function"""
    print("🔧 Sakura Database Sync Tool")
    print("=" * 40)
    
    try:
        # Check paths
        check_database_paths()
        
        # Sync databases
        if sync_databases():
            print("\n✅ Database sync completed!")
            
            # Test connection
            if test_database_connection():
                print("\n🎉 Database is ready for use!")
                print("🔗 Test the API endpoints:")
                print("  - http://localhost:5000/api/databases")
                print("  - http://localhost:5000/api/users/")
                print("  - http://localhost:5000/api/test-cases/")
            else:
                print("\n❌ Database connection test failed!")
                return 1
        else:
            print("\n❌ Database sync failed!")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
