import sqlite3
from pathlib import Path

# Check multiple possible database locations
db_paths = [
    Path("backend/data/local/dev/database/local.db"),
    Path("data/local/dev/database/local.db"),
    Path("backend/data/local/local.db"),
    Path("data/local/local.db"),
]

for db_path in db_paths:
    if db_path.exists():
        print(f"\n{'='*100}")
        print(f"Database found: {db_path}")
        print(f"Size: {db_path.stat().st_size} bytes")
        print(f"{'='*100}")
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"Tables: {', '.join([t[0] for t in tables])}\n")
            
            # Check users table
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"Total users: {user_count}")
            
            if user_count > 0:
                cursor.execute("SELECT id, username, email, role, created_at FROM users")
                users = cursor.fetchall()
                print(f"\n{'ID':<5} {'Username':<20} {'Email':<30} {'Role':<10} {'Created At'}")
                print("-" * 100)
                for user in users:
                    print(f"{user[0]:<5} {user[1]:<20} {user[2]:<30} {user[3]:<10} {user[4] or 'N/A'}")
            
            conn.close()
        except Exception as e:
            print(f"Error reading database: {e}")

