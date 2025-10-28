#!/usr/bin/env python3
"""
Database Migration Script: Add Design Tickets
This script creates the design_tickets table and adds design_ticket_id to requirements table
"""

import os
import sys
from pathlib import Path
import sqlite3

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from src.infrastructure.configuration_manager import get_config_manager

def create_design_tickets_table(cursor):
    """Create the design_tickets table"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS design_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            design_ticket_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            design_type TEXT,
            diagram_type TEXT,
            image_url TEXT,
            priority TEXT,
            status TEXT,
            linked_requirement_id TEXT,
            assignee TEXT,
            tags TEXT,
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✓ Created design_tickets table")

def add_design_ticket_id_to_requirements(cursor):
    """Add design_ticket_id column to requirements table"""
    try:
        # Try to add the column (will fail if it already exists)
        cursor.execute("""
            ALTER TABLE requirements 
            ADD COLUMN design_ticket_id TEXT
        """)
        print("✓ Added design_ticket_id column to requirements table")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            print("✓ design_ticket_id column already exists in requirements table")
        else:
            raise

def migrate():
    """Run the migration"""
    config_manager = get_config_manager()
    local_db_path = config_manager.get_config("database.local_db_path", "data/local/dev/database/sakura_db.db")
    
    # Resolve path
    backend_dir = Path(__file__).parent.parent
    db_path = backend_dir / local_db_path
    
    print(f"Connecting to database: {db_path}")
    
    if not db_path.exists():
        # Try alternative path
        alt_path = backend_dir / "data" / "local" / "dev" / "database" / "sakura_db.db"
        if alt_path.exists():
            db_path = alt_path
        else:
            print(f"Error: Database not found at {db_path}")
            print(f"Looking for database in: {alt_path}")
            return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        create_design_tickets_table(cursor)
        add_design_ticket_id_to_requirements(cursor)
        
        conn.commit()
        print("\n✓ Migration completed successfully")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)

