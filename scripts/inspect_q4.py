import sqlite3

conn = sqlite3.connect('storage/local.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== Q4 Ground Truth: Temporary Flowline Bypasses ===")
cur.execute("""
    SELECT n.note_id, n.asset_id, w.area_id, a.name as area_name, n.created_at, n.text
    FROM context_notes n
    JOIN wells w ON n.asset_id = w.asset_id
    JOIN areas a ON w.area_id = a.area_id
    WHERE LOWER(n.text) LIKE '%bypass%'
    ORDER BY n.asset_id, n.created_at;
""")
rows = cur.fetchall()
print(f"Total bypass notes: {len(rows)}")
for r in rows:
    print(f"{r['asset_id']} ({r['area_id']}) | {r['created_at']} | {r['text']}")
