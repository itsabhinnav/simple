import sqlite3

conn = sqlite3.connect('data/local/dev/database/sakura_db.db')
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='requirements'")
result = cursor.fetchone()
if result:
    print(result[0])
else:
    print("No table found")









