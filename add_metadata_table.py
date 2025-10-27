import sqlite3
from pathlib import Path

def add_metadata_table(db_path):
    """Add database_metadata table to existing database"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='database_metadata'")
    exists = cursor.fetchone()
    
    if not exists:
        print(f"Adding database_metadata table to {db_path}")
        # Create table
        cursor.execute("""
            CREATE TABLE database_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metadata_key TEXT UNIQUE NOT NULL,
                metadata_value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Initialize version
        cursor.execute("""
            INSERT INTO database_metadata (metadata_key, metadata_value)
            VALUES ('version', '1')
        """)
        
        conn.commit()
        print(f"✓ Added database_metadata table with version=1")
    else:
        print(f"database_metadata table already exists in {db_path}")
    
    conn.close()

# Add to both databases
local_db = Path("backend/data/local/dev/database/sakura_db.db")
remote_db = Path("backend/data/remote/dev/database/sakura_db.db")

if local_db.exists():
    add_metadata_table(local_db)

if remote_db.exists():
    add_metadata_table(remote_db)

