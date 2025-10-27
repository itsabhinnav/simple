import sqlite3
from pathlib import Path

local_db = Path("backend/data/local/dev/database/sakura_db.db")
remote_db = Path("backend/data/remote/dev/database/sakura_db.db")

print("=== LOCAL DATABASE ===")
if local_db.exists():
    conn = sqlite3.connect(str(local_db))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get version
    cursor.execute("SELECT metadata_value FROM database_metadata WHERE metadata_key = 'version'")
    version = cursor.fetchone()
    print(f"Version: {version[0] if version else 'N/A'}")
    
    # Get users
    cursor.execute("SELECT id, username, email, created_at FROM users")
    users = cursor.fetchall()
    print(f"Users: {len(users)}")
    for u in users:
        print(f"  - {u['id']}: {u['username']} ({u['email']}) - {u['created_at']}")
    
    conn.close()
else:
    print("Local DB not found")

print("\n=== REMOTE DATABASE ===")
if remote_db.exists():
    conn = sqlite3.connect(str(remote_db))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get version
    cursor.execute("SELECT metadata_value FROM database_metadata WHERE metadata_key = 'version'")
    version = cursor.fetchone()
    print(f"Version: {version[0] if version else 'N/A'}")
    
    # Get users
    cursor.execute("SELECT id, username, email, created_at FROM users")
    users = cursor.fetchall()
    print(f"Users: {len(users)}")
    for u in users:
        print(f"  - {u['id']}: {u['username']} ({u['email']}) - {u['created_at']}")
    
    conn.close()
else:
    print("Remote DB not found")

