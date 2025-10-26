#!/usr/bin/env python3
"""
Clear Database Script

This script deletes all data from all tables in both databases.
"""

import sqlite3
from pathlib import Path

# Resolve paths relative to backend directory
backend_dir = Path(__file__).parent.parent
local_db = backend_dir / "data" / "local" / "local.db"
remote_db = backend_dir / "remote" / "dev" / "database" / "sakura_db.db"

def clear_database(db_path, db_name):
    """Clear all data from all tables"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        
        # Filter out system tables
        tables = [t for t in tables if t != 'sqlite_sequence']
        
        print(f"🗄️  Database: {db_name}")
        print("=" * 50)
        print(f"\n📋 Tables to clear: {tables}")
        
        # Show current row counts
        print("\n📊 Current data:")
        total_rows = 0
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            total_rows += count
            print(f"  - {table}: {count} rows")
        print(f"\n  Total: {total_rows} rows")
        
        # Confirm deletion
        if total_rows == 0:
            print("\n✅ Database is already empty!")
            return
        
        print("\n⚠️  WARNING: This will delete ALL data from the database!")
        confirm = input("\nType 'DELETE' to confirm: ")
        
        if confirm != 'DELETE':
            print("\n❌ Operation cancelled.")
            return
        
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
        else:
            print(f"⚠️  Warning: {remaining} rows still remain in database")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("🗑️  Database Clearing Tool")
    print("=" * 60)
    
    # Clear local database
    if local_db.exists():
        print(f"\n1️⃣  Clearing LOCAL database: {local_db.name}")
        clear_database(local_db, local_db.name)
    else:
        print(f"\n⚠️  Local database not found at {local_db}")
    
    # Clear remote database
    if remote_db.exists():
        print(f"\n2️⃣  Clearing REMOTE database: {remote_db.name}")
        clear_database(remote_db, remote_db.name)
    else:
        print(f"\n⚠️  Remote database not found at {remote_db}")
    
    print("\n" + "=" * 60)
    print("✅ Done!")

