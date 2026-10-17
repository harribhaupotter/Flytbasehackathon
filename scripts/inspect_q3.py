import sqlite3
import json
import re

conn = sqlite3.connect('storage/local.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== Q3 Ground Truth: Gas Reports Since 1 Nov 2026 ===")
# Find operator notes mentioning gas, smell, rotten-egg, odor, h2s since 1 Nov 2026
cur.execute("""
    SELECT n.note_id, n.asset_id, w.area_id, a.name as area_name, n.created_at, n.text
    FROM context_notes n
    JOIN wells w ON n.asset_id = w.asset_id
    JOIN areas a ON w.area_id = a.area_id
    WHERE n.created_at >= '2026-11-01'
      AND (
          LOWER(n.text) LIKE '%gas%' OR 
          LOWER(n.text) LIKE '%odor%' OR 
          LOWER(n.text) LIKE '%smell%' OR 
          LOWER(n.text) LIKE '%rotten-egg%' OR 
          LOWER(n.text) LIKE '%h2s%'
      )
    ORDER BY n.created_at;
""")
gas_notes = cur.fetchall()
print(f"Found {len(gas_notes)} gas notes.")
for r in gas_notes:
    # Check field response: maintenance job or manual inspection
    asset_id = r["asset_id"]
    created_at = r["created_at"]
    deadline_hours = 12 if created_at >= '2027-01-01' else 24
    
    # check maintenance started_at > created_at
    cur.execute("""
        SELECT maintenance_id, started_at
        FROM maintenance
        WHERE asset_id = ? AND started_at > ?
        ORDER BY started_at ASC LIMIT 1;
    """, (asset_id, created_at))
    m_row = cur.fetchone()
    
    # check manual inspection inspected_at > created_at
    cur.execute("""
        SELECT inspection_id, inspected_at
        FROM inspections
        WHERE asset_id = ? AND inspected_at > ? AND method = 'manual'
        ORDER BY inspected_at ASC LIMIT 1;
    """, (asset_id, created_at))
    i_row = cur.fetchone()
    
    print(f"Well: {asset_id} ({r['area_name']}) | Noted: {created_at} | Text: {r['text'][:60]}")
    print(f"  Next MNT: {dict(m_row) if m_row else 'None'} | Next Manual INS: {dict(i_row) if i_row else 'None'}")
