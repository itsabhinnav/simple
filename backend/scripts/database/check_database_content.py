#!/usr/bin/env python3
"""
Database Content Checker

This script checks the content of the database files to verify they have the correct tables and data.
"""

import sqlite3
from pathlib import Path


def check_database_content(db_path):
    """Check the content of a database file"""
    print(f"🔍 Checking database: {db_path}")
    
    if not Path(db_path).exists():
        print(f"❌ Database file not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        table_names = [t[0] for t in tables]
        
        print(f"📋 Tables found: {table_names}")
        
        # Check each table for data
        for table in table_names:
            if table != 'sqlite_sequence':  # Skip system table
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  - {table}: {count} records")
        
        # Show sample data from users table
        if 'users' in table_names:
            cursor.execute("SELECT username, email, role FROM users LIMIT 3")
            users = cursor.fetchall()
            print(f"\n👥 Sample users:")
            for user in users:
                print(f"  - {user[0]} ({user[1]}) - {user[2]}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return False


def main():
    """Main function"""
    print("🗄️ Database Content Checker")
    print("=" * 40)
    
    # Check both database locations
    databases = [
        "backend/data/sakura_db.db",
        "backend/data/cache/sakura_db.db",
        "backend/remote/git/database/sakura_db.db"
    ]
    
    for db_path in databases:
        print(f"\n{'='*50}")
        check_database_content(db_path)
    
    print(f"\n{'='*50}")
    print("✅ Database content check complete!")


if __name__ == "__main__":
    main()
