import sqlite3
from pathlib import Path

local_db = Path("backend/data/local/dev/database/sakura_db.db")

conn = sqlite3.connect(str(local_db))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== Checking for User2 ===")
cursor.execute("SELECT id, username, email, created_at FROM users WHERE username = 'User2'")
result = cursor.fetchall()

if result:
    print(f"Found {len(result)} user(s)")
    for row in result:
        print(f"  ID: {row['id']}, Username: {row['username']}, Email: {row['email']}, Created: {row['created_at']}")
else:
    print("User2 not found")

print("\n=== All users ===")
cursor.execute("SELECT id, username, email FROM users")
all_users = cursor.fetchall()
print(f"Total: {len(all_users)}")
for u in all_users:
    print(f"  - {u['id']}: {u['username']} ({u['email']})")

print("\n=== Database version ===")
cursor.execute("SELECT metadata_value FROM database_metadata WHERE metadata_key = 'version'")
version = cursor.fetchone()
print(f"Version: {version['metadata_value'] if version else 'N/A'}")

conn.close()

