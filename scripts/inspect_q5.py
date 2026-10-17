import sqlite3
import re

conn = sqlite3.connect('storage/local.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== Q5 Ground Truth: Regulator Letter Spills ===")
# Letter from 20 Nov 2026 covers:
# "For every reportable spill (5 bbl or more) in Northeast Block 7 or Northeast Block 8 since 1 Jun 2026"
# Compliant only if clean-up report contains the exact sentence: "Soil samples sent to the lab."
# (spills later confirmed not crude oil do not need samples)

cur.execute("""
    SELECT s.inspection_id, s.asset_id, s.well_name, s.area_id, s.area_name, s.inspected_at,
           s.spill_est_volume_bbl, s.maintenance_id, s.report_file
    FROM v_spill_incidents s
    WHERE s.area_id IN ('NE-07', 'NE-08')
      AND s.inspected_at >= '2026-06-01'
      AND s.spill_est_volume_bbl >= 5.0
    ORDER BY s.inspected_at;
""")
spills = cur.fetchall()
print(f"Total covered spills: {len(spills)}")
for s in spills:
    mnt_id = s["maintenance_id"]
    content = ""
    if mnt_id:
        cur.execute("SELECT content FROM documents WHERE doc_id = ?", (mnt_id,))
        doc_row = cur.fetchone()
        if doc_row:
            content = doc_row["content"]
    
    # Check if confirmed not crude oil
    not_crude = "not crude" in content.lower() or "rainwater" in content.lower()
    
    # Check for exact sentence: "Soil samples sent to the lab."
    has_lab_samples = "Soil samples sent to the lab." in content
    
    status = "Yes" if has_lab_samples else "No"
    reason = "Exact sentence 'Soil samples sent to the lab.' present in clean-up report" if has_lab_samples else "Missing laboratory soil sample submission"
    if not_crude:
        reason = "Confirmed not crude oil (exempt from sampling)"
        status = "Yes (exempt)"
    
    print(f"Well: {s['asset_id']} | Area: {s['area_id']} | Insp: {s['inspection_id']} ({s['inspected_at']}) | Vol: {s['spill_est_volume_bbl']} bbl | Job: {mnt_id} | Compliant: {status} ({reason})")
