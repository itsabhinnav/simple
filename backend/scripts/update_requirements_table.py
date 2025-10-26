import sqlite3
from pathlib import Path

# Resolve path relative to backend directory
backend_dir = Path(__file__).parent.parent
db_path = backend_dir / "data" / "local" / "local.db"

if not db_path.exists():
    print(f"Database not found at {db_path}!")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

try:
    # Add new columns to requirements table if they don't exist
    columns_to_add = [
        ('given', 'TEXT'),
        ('when_action', 'TEXT'),
        ('then_result', 'TEXT'),
        ('assignee', 'TEXT'),
        ('tags', 'TEXT'),
        ('created_by', 'TEXT')
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f'ALTER TABLE requirements ADD COLUMN {col_name} {col_type}')
            print(f"✓ Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print(f"  Column {col_name} already exists")
            else:
                print(f"✗ Error adding column {col_name}: {e}")
    
    conn.commit()
    print("\n✓ Requirements table updated successfully!")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()

