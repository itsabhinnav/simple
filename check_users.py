import sqlite3
from pathlib import Path

# Connect to database
db_path = Path("backend/data/local/dev/database/local.db")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Query all users
cursor.execute("SELECT id, username, email, role, created_at FROM users")
rows = cursor.fetchall()

print("=" * 100)
print("USERS IN DATABASE")
print("=" * 100)
print(f"{'ID':<5} {'Username':<20} {'Email':<30} {'Role':<10} {'Created At'}")
print("-" * 100)

for row in rows:
    user_id, username, email, role, created_at = row
    print(f"{user_id:<5} {username:<20} {email:<30} {role:<10} {created_at or 'N/A'}")

print("=" * 100)
print(f"Total users: {len(rows)}")
print("=" * 100)

conn.close()

