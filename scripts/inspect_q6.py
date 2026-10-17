import sqlite3

conn = sqlite3.connect('storage/local.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== Q6 Ground Truth: Status Disagreements ===")
# OPS-3: A well's current status comes from the most recent of:
# - latest inspection reading (producing or not producing by well-type delta threshold, after data_correction)
# - latest operator note saying the well was shut in or restarted.
# If shut-in note more recent than inspection -> not producing (shut in)
# If restart note more recent than inspection -> producing (unconfirmed)
# Disagreements: where inspection and operator note disagree!

cur.execute("SELECT asset_id, name, well_type, area_id FROM wells ORDER BY asset_id")
wells = cur.fetchall()

disagreements = []
for w in wells:
    aid = w["asset_id"]
    # Latest inspection
    cur.execute("""
        SELECT inspection_id, inspected_at, is_producing_dynamically, dynamic_status, delta_temp_c
        FROM v_inspections_effective
        WHERE asset_id = ?
        ORDER BY inspected_at DESC LIMIT 1;
    """, (aid,))
    insp = cur.fetchone()
    if not insp:
        continue
    
    # Latest operator note saying shut in or restarted
    cur.execute("""
        SELECT note_id, created_at, text
        FROM context_notes
        WHERE asset_id = ?
          AND note_type = 'operator_note'
          AND (
              LOWER(text) LIKE '%shut in%' OR 
              LOWER(text) LIKE '%shut-in%' OR 
              LOWER(text) LIKE '%shut down%' OR
              LOWER(text) LIKE '%stopped%' OR
              LOWER(text) LIKE '%restart%' OR
              LOWER(text) LIKE '%started up%' OR
              LOWER(text) LIKE '%back online%' OR
              LOWER(text) LIKE '%brought back%'
          )
        ORDER BY created_at DESC LIMIT 1;
    """, (aid,))
    note = cur.fetchone()
    if not note:
        continue
    
    insp_producing = (insp["is_producing_dynamically"] == 1)
    note_text = note["text"].lower()
    
    # Classify note
    note_shut_in = any(k in note_text for k in ['shut in', 'shut-in', 'shut down', 'stopped'])
    note_restarted = any(k in note_text for k in ['restart', 'started up', 'back online', 'brought back'])
    
    if note_shut_in and insp_producing and note["created_at"] > insp["inspected_at"]:
        disagreements.append({
            "well": aid,
            "area": w["area_id"],
            "insp": dict(insp),
            "note": dict(note),
            "status_now": "Not producing oil (shut in)",
            "reason": "Shut-in note is more recent than latest producing inspection (OPS-3)"
        })
    elif note_restarted and not insp_producing and note["created_at"] > insp["inspected_at"]:
        disagreements.append({
            "well": aid,
            "area": w["area_id"],
            "insp": dict(insp),
            "note": dict(note),
            "status_now": "Producing oil (unconfirmed)",
            "reason": "Restart note is more recent than latest non-producing inspection (OPS-3)"
        })

print(f"Total disagreements found: {len(disagreements)}")
for d in disagreements:
    print(f"Well: {d['well']} ({d['area']}) | Status: {d['status_now']}")
    print(f"  Insp: {d['insp']['inspection_id']} on {d['insp']['inspected_at']} -> {'Producing' if d['insp']['is_producing_dynamically'] else 'Non-producing'} (ΔT={d['insp']['delta_temp_c']}°C)")
    print(f"  Note: on {d['note']['created_at']} -> \"{d['note']['text']}\"")
