import sqlite3
import re

conn = sqlite3.connect('storage/local.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== Q8 Ground Truth: Recalled Pumps in the Ground ===")
# 1. Search maintenance reports for RP-175 and lot numbers
# LOT-2409-A, LOT-2409-C, LOT-2410-B
recalled_lots = ["LOT-2409-A", "LOT-2409-C", "LOT-2410-B"]

cur.execute("""
    SELECT doc_id, asset_id, content
    FROM documents
    WHERE category = 'maintenance_report'
      AND (
          content LIKE '%LOT-2409-A%' OR 
          content LIKE '%LOT-2409-C%' OR 
          content LIKE '%LOT-2410-B%'
      )
    ORDER BY asset_id, doc_id;
""")
reports = cur.fetchall()
print(f"Reports mentioning recalled lots: {len(reports)}")

# Group by asset_id and check the latest pump installation date vs latest repair/replacement
wells_with_recalled = {}
for r in reports:
    aid = r["asset_id"]
    content = r["content"]
    doc_id = r["doc_id"]
    
    # check which lot
    lot = None
    for l in recalled_lots:
        if l in content:
            lot = l
            break
    
    # check date of this maintenance job
    cur.execute("SELECT started_at, completed_at, cost_total FROM maintenance WHERE maintenance_id = ?", (doc_id,))
    m_row = cur.fetchone()
    install_date = m_row["started_at"] if m_row else "unknown"
    cost = m_row["cost_total"] if m_row else None
    
    # Check if there is a later maintenance job that replaced/pulled the downhole pump
    cur.execute("""
        SELECT maintenance_id, started_at, equipment_kind, action_taken, issue
        FROM maintenance
        WHERE asset_id = ? 
          AND started_at > ?
          AND (equipment_kind IN ('downhole_pump', 'rod_pump') OR LOWER(issue) LIKE '%pump%' OR LOWER(action_taken) LIKE '%replace%')
        ORDER BY started_at DESC LIMIT 1;
    """, (aid, install_date))
    later_job = cur.fetchone()
    
    # Check area
    cur.execute("SELECT area_id FROM wells WHERE asset_id = ?", (aid,))
    w_row = cur.fetchone()
    area = w_row["area_id"] if w_row else "unknown"
    
    wells_with_recalled[aid] = {
        "well": aid,
        "area": area,
        "doc_id": doc_id,
        "installed_at": install_date,
        "lot": lot,
        "cost_usd": cost,
        "later_replacement": dict(later_job) if later_job else None,
        "still_in_ground": later_job is None
    }

for aid, info in sorted(wells_with_recalled.items()):
    status = "STILL IN GROUND" if info["still_in_ground"] else f"REPLACED on {info['later_replacement']['started_at']} ({info['later_replacement']['maintenance_id']})"
    print(f"{aid} ({info['area']}) | Lot: {info['lot']} installed on {info['installed_at']} ({info['doc_id']}) | Cost: ${info['cost_usd']} | Status: {status}")
