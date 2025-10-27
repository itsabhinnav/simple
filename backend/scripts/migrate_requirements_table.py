#!/usr/bin/env python3
"""
Migrate Requirements Table

This script adds missing columns to the requirements table.
"""

import sqlite3
from pathlib import Path

# Database path
db_path = Path("data/local/dev/database/sakura_db.db")

if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("Migrating requirements table...")

try:
    # Get current columns
    cursor.execute("PRAGMA table_info(requirements)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    # Columns to add
    new_columns = {
        'given': 'TEXT',
        'when_action': 'TEXT',
        'then_result': 'TEXT',
        'assignee': 'TEXT',
        'tags': 'TEXT'
    }
    
    # Add missing columns
    for col_name, col_type in new_columns.items():
        if col_name not in existing_columns:
            print(f"  Adding column: {col_name}")
            cursor.execute(f'ALTER TABLE requirements ADD COLUMN {col_name} {col_type}')
        else:
            print(f"  Column {col_name} already exists, skipping")
    
    # Commit changes
    conn.commit()
    print("\nMigration completed successfully!")
    
    # Show updated schema
    cursor.execute("PRAGMA table_info(requirements)")
    cols = cursor.fetchall()
    print("\nUpdated requirements table schema:")
    for col in cols:
        print(f"  {col[1]} ({col[2]})")
    
except Exception as e:
    print(f"\nError during migration: {e}")
    conn.rollback()
    exit(1)
    
finally:
    conn.close()

