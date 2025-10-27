import sqlite3

conn = sqlite3.connect('data/local/dev/database/sakura_db.db')
cursor = conn.cursor()

# Check current state
cursor.execute("SELECT id, requirement_id, requirement_type FROM requirements WHERE requirement_type IS NULL")
null_types = cursor.fetchall()
print(f"Found {len(null_types)} requirements with null requirement_type")

# Update requirements with random types
import random
types = ["Functional", "HMI", "Safety", "Performance", "Usability"]

for req in null_types:
    req_id = req[0]
    req_type = random.choice(types)
    cursor.execute("UPDATE requirements SET requirement_type = ? WHERE id = ?", (req_type, req_id))
    print(f"Updated requirement {req_id} with type {req_type}")

conn.commit()

# Verify
cursor.execute("SELECT id, requirement_id, requirement_type FROM requirements")
all_reqs = cursor.fetchall()
print(f"\nTotal requirements: {len(all_reqs)}")
for req in all_reqs[:5]:
    print(f"  ID: {req[0]}, ReqID: {req[1]}, Type: {req[2]}")

conn.close()

