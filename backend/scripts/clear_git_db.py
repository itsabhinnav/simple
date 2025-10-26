#!/usr/bin/env python3
"""
Clear Git Database Script

This script deletes all data from the remote database and prepares it for commit.
"""

import sqlite3
from pathlib import Path

# Path to the git-tracked database
db_path = Path("backend/remote/dev/database/sakura_db.db")

if not db_path.exists():
    print(f"❌ Database not found at {db_path}!")
    exit(1)

def clear_database():
    """Clear all data from all tables"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        
        # Filter out system tables
        tables = [t for t in tables if t != 'sqlite_sequence']
        
        print("🗄️  Database: sakura_db.db")
        print("=" * 50)
        print(f"\n📋 Tables: {tables}")
        
        # Show current row counts
        print("\n📊 Current data:")
        total_rows = 0
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            total_rows += count
            print(f"  - {table}: {count} rows")
        print(f"\n  Total: {total_rows} rows")
        
        if total_rows == 0:
            print("\n✅ Database is already empty!")
            return True
        
        # Delete all data from each table
        print("\n🗑️  Deleting data...")
        deleted_count = 0
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            deleted_count += cursor.rowcount
            print(f"  ✓ Cleared {table}")
        
        conn.commit()
        
        # Verify deletion
        remaining = 0
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            remaining += count
        
        print("\n" + "=" * 50)
        if remaining == 0:
            print(f"✅ Successfully deleted all data from {len(tables)} tables!")
            print(f"   Total rows deleted: {deleted_count}")
            return True
        else:
            print(f"⚠️  Warning: {remaining} rows still remain")
            return False
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = clear_database()
    exit(0 if success else 1)

