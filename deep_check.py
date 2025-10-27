import sqlite3
from pathlib import Path

db_path = Path("backend/data/local/dev/database/local.db")
print(f"Database: {db_path}")
print(f"Exists: {db_path.exists()}")
print(f"Size: {db_path.stat().st_size} bytes\n")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Get all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print(f"Tables: {', '.join(tables)}\n")

# Check each table for content
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"{table}: {count} rows")
    
    if count > 0 and table == 'users':
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        print(f"Columns: {', '.join(columns)}")
        print("First few rows:")
        for row in rows[:3]:
            print(f"  {dict(zip(columns, row))}")
        
conn.close()

