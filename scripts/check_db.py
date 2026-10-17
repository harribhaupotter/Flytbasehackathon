import sqlite3

conn = sqlite3.connect('storage/local.db')
cur = conn.cursor()
for table in ['areas', 'teams', 'users', 'wells', 'inspections', 'maintenance', 'documents', 'context_notes', 'regulatory_events']:
    try:
        cur.execute(f"SELECT count(*) FROM {table}")
        print(f"{table}: {cur.fetchone()[0]}")
    except Exception as e:
        print(f"{table}: error: {e}")

cur.execute("SELECT name FROM sqlite_master WHERE type='view'")
print("Views:", [r[0] for r in cur.fetchall()])
