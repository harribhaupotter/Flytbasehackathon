import sqlite3
import re

conn = sqlite3.connect('storage/local.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== Q10 Ground Truth: Waiting On Breakdown ===")
# Search context notes or documents for waiting on
cur.execute("""
    SELECT n.asset_id, w.area_id, n.created_at, n.text
    FROM context_notes n
    JOIN wells w ON n.asset_id = w.asset_id
    WHERE LOWER(n.text) LIKE '%waiting on%' 
       OR LOWER(n.text) LIKE '%waiting for%'
       OR LOWER(n.text) LIKE '%delayed%'
    ORDER BY n.created_at
    LIMIT 20;
""")
notes = cur.fetchall()
print(f"Context notes matching delay: {len(notes)}")
for r in notes[:5]:
    print(f"{r['asset_id']} ({r['area_id']}) | {r['created_at']} | {r['text']}")

# Also search documents
cur.execute("""
    SELECT doc_id, asset_id, section, snippet(documents_fts, 5, '<b>', '</b>', '...', 20) as snip
    FROM documents_fts
    WHERE documents_fts MATCH 'waiting'
    LIMIT 10;
""")
docs = cur.fetchall()
print(f"\nDocuments matching waiting: {len(docs)}")
for d in docs[:5]:
    print(f"{d['doc_id']} ({d['asset_id']}) | {d['section']} | {d['snip']}")
