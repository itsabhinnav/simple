#!/usr/bin/env python3
"""
Fix design_tickets table schema to use linked_requirement_id
"""
import os
import sys
import sqlite3
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from src.infrastructure.configuration_manager import get_config_manager

def fix_design_tickets_table():
    """Fix the design_tickets table to use linked_requirement_id"""
    config_manager = get_config_manager()
    local_db_path = config_manager.get_config("database.local_db_path", "data/local/dev/database/sakura_db.db")
    
    # Resolve path
    backend_dir = Path(__file__).parent.parent
    db_path = backend_dir / local_db_path
    
    print(f"Connecting to database: {db_path}")
    
    if not db_path.exists():
        alt_path = backend_dir / "data" / "local" / "dev" / "database" / "sakura_db.db"
        if alt_path.exists():
            db_path = alt_path
        else:
            print(f"Error: Database not found at {db_path}")
            return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='design_tickets'
        """)
        
        if cursor.fetchone():
            # Table exists, check column
            cursor.execute("PRAGMA table_info(design_tickets)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'requirement_id' in columns and 'linked_requirement_id' not in columns:
                # Rename column
                print("Renaming requirement_id to linked_requirement_id...")
                cursor.execute("""
                    ALTER TABLE design_tickets 
                    RENAME COLUMN requirement_id TO linked_requirement_id
                """)
                conn.commit()
                print("✓ Successfully renamed column")
            elif 'linked_requirement_id' in columns:
                print("✓ Column already renamed to linked_requirement_id")
            else:
                print("✗ Neither requirement_id nor linked_requirement_id found")
        else:
            print("✗ design_tickets table does not exist")
            return False
            
        print("\n✓ Migration completed successfully")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = fix_design_tickets_table()
    sys.exit(0 if success else 1)

