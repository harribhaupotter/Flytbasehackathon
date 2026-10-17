#!/usr/bin/env python3
"""
scripts/ingest_test_dataset.py

High-performance data ingestion pipeline for the test dataset (600 wells, today = 15 Jan 2027).
Populates SQLite (`storage/local.db`) with full relational telemetry, views, and FTS5 documents.
"""

import os
import glob
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "flytbase" / "flytbase-ahc-swe-asset-intelligence-dataset" / "test-data" / "dataset"
SQLITE_DB_PATH = BASE_DIR / "storage" / "local.db"

SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def setup_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.executescript("""
    PRAGMA journal_mode = WAL;
    PRAGMA synchronous = NORMAL;

    DROP TABLE IF EXISTS areas;
    CREATE TABLE areas (
        area_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        team_id TEXT NOT NULL,
        lat REAL,
        lon REAL
    );

    DROP TABLE IF EXISTS teams;
    CREATE TABLE teams (
        team_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        lead_user_id TEXT
    );

    DROP TABLE IF EXISTS users;
    CREATE TABLE users (
        user_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        team_id TEXT
    );

    DROP TABLE IF EXISTS wells;
    CREATE TABLE wells (
        asset_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        asset_category TEXT NOT NULL,
        well_type TEXT NOT NULL,
        area_id TEXT NOT NULL,
        team_id TEXT NOT NULL,
        in_charge_user_id TEXT,
        lat REAL,
        lon REAL,
        installed_on TEXT,
        recorded_status TEXT,
        status TEXT,
        decommissioned_on TEXT,
        last_inspection_id TEXT,
        last_inspection_time TEXT,
        last_inspection_inspector TEXT
    );

    DROP TABLE IF EXISTS inspections;
    CREATE TABLE inspections (
        inspection_id TEXT PRIMARY KEY,
        asset_id TEXT NOT NULL,
        inspected_at TEXT NOT NULL,
        inspector_user_id TEXT,
        method TEXT,
        ambient_temp_c REAL,
        wellhead_temp_c REAL,
        spill_detected INTEGER,
        spill_area_pct REAL,
        spill_est_volume_bbl REAL,
        recorded_at TEXT,
        notes TEXT
    );

    DROP TABLE IF EXISTS maintenance;
    CREATE TABLE maintenance (
        maintenance_id TEXT PRIMARY KEY,
        asset_id TEXT NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        maintenance_type TEXT NOT NULL,
        equipment_kind TEXT,
        issue TEXT,
        action_taken TEXT,
        technician_user_id TEXT,
        contractor TEXT,
        downtime_hours REAL,
        cost_labor REAL,
        cost_parts REAL,
        cost_total REAL,
        cost_revision TEXT,
        recorded_at TEXT,
        triggered_by_inspection_id TEXT,
        report_file TEXT,
        containment_hours REAL,
        sr02_met INTEGER
    );

    DROP TABLE IF EXISTS regulatory_events;
    CREATE TABLE regulatory_events (
        event_id TEXT PRIMARY KEY,
        asset_id TEXT NOT NULL,
        date TEXT NOT NULL,
        agency TEXT,
        event_type TEXT NOT NULL,
        protocol_id TEXT,
        related_inspection_id TEXT,
        hours_to_report REAL,
        detail TEXT,
        fine_usd REAL,
        status TEXT
    );

    DROP TABLE IF EXISTS context_notes;
    CREATE TABLE context_notes (
        note_id TEXT PRIMARY KEY,
        asset_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        author_user_id TEXT,
        note_type TEXT NOT NULL,
        inspection_id TEXT,
        field TEXT,
        original_value TEXT,
        corrected_value TEXT,
        text TEXT NOT NULL,
        valid_from TEXT,
        valid_to TEXT
    );

    CREATE TABLE IF NOT EXISTS user_feedback_overrides (
        override_id INTEGER PRIMARY KEY AUTOINCREMENT,
        scope TEXT NOT NULL CHECK(scope IN ('inspection_field', 'well_type_rule', 'spill_false_positive', 'general')),
        target_id TEXT NOT NULL,
        field_name TEXT NOT NULL,
        original_value TEXT,
        corrected_value TEXT NOT NULL,
        author_user_id TEXT NOT NULL,
        rationale TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS unconfirmed_claims (
        claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        asset_id TEXT NOT NULL,
        claim_text TEXT NOT NULL,
        conflicting_evidence TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_rules (
        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        target_scope TEXT NOT NULL,
        rule_name TEXT NOT NULL,
        rule_value TEXT NOT NULL,
        rationale TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1
    );

    -- Documents & FTS
    DROP TABLE IF EXISTS documents;
    CREATE TABLE documents (
        doc_id TEXT PRIMARY KEY,
        title TEXT,
        category TEXT,
        asset_id TEXT,
        section TEXT,
        content TEXT,
        citation_ref TEXT
    );

    DROP TABLE IF EXISTS documents_fts;
    CREATE VIRTUAL TABLE documents_fts USING fts5(
        doc_id UNINDEXED,
        title,
        category,
        asset_id,
        section,
        content,
        citation_ref,
        content='documents',
        content_rowid='rowid'
    );

    -- Fast lookup indices
    CREATE INDEX IF NOT EXISTS idx_inspections_asset_date ON inspections(asset_id, inspected_at);
    CREATE INDEX IF NOT EXISTS idx_inspections_spill ON inspections(spill_detected);
    CREATE INDEX IF NOT EXISTS idx_maintenance_asset_date ON maintenance(asset_id, started_at);
    CREATE INDEX IF NOT EXISTS idx_maintenance_triggered ON maintenance(triggered_by_inspection_id);
    CREATE INDEX IF NOT EXISTS idx_reg_events_asset_date ON regulatory_events(asset_id, date);
    CREATE INDEX IF NOT EXISTS idx_context_asset ON context_notes(asset_id);
    CREATE INDEX IF NOT EXISTS idx_overrides_lookup ON user_feedback_overrides(target_id, field_name, is_active);
    """)
    conn.commit()


def create_views(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.executescript("""
    -- 1. Effective Telemetry View (supporting T200, T350, T500 with human corrections)
    DROP VIEW IF EXISTS v_inspections_effective;
    CREATE VIEW v_inspections_effective AS
    SELECT 
        i.inspection_id,
        i.asset_id,
        w.name AS well_name,
        w.well_type,
        w.area_id,
        a.name AS area_name,
        i.inspected_at,
        i.inspector_user_id,
        i.method,
        i.ambient_temp_c,
        -- Effective Wellhead Temperature
        COALESCE(CAST(o_temp.corrected_value AS REAL), i.wellhead_temp_c) AS wellhead_temp_c,
        i.wellhead_temp_c AS raw_wellhead_temp_c,
        o_temp.override_id AS wellhead_temp_override_id,
        o_temp.author_user_id AS wellhead_temp_override_author,
        o_temp.rationale AS wellhead_temp_override_rationale,
        
        -- Calculated Delta T (°C)
        ROUND(COALESCE(CAST(o_temp.corrected_value AS REAL), i.wellhead_temp_c) - i.ambient_temp_c, 2) AS delta_temp_c,
        
        -- Production threshold delta: T200 >= 15.0, T350 >= 20.0, T500 >= 25.0
        CASE 
            WHEN w.well_type = 'T200' THEN 15.0 
            WHEN w.well_type = 'T350' THEN 20.0 
            WHEN w.well_type = 'T500' THEN 25.0
            ELSE 20.0 
        END AS threshold_delta_c,
        
        -- Dynamic Production Status (1 = producing, 0 = non-producing)
        CASE 
            WHEN w.well_type = 'T200' AND (COALESCE(CAST(o_temp.corrected_value AS REAL), i.wellhead_temp_c) - i.ambient_temp_c) >= 15.0 THEN 1
            WHEN w.well_type = 'T350' AND (COALESCE(CAST(o_temp.corrected_value AS REAL), i.wellhead_temp_c) - i.ambient_temp_c) >= 20.0 THEN 1
            WHEN w.well_type = 'T500' AND (COALESCE(CAST(o_temp.corrected_value AS REAL), i.wellhead_temp_c) - i.ambient_temp_c) >= 25.0 THEN 1
            ELSE 0 
        END AS is_producing_dynamically,

        CASE 
            WHEN w.well_type = 'T200' AND (COALESCE(CAST(o_temp.corrected_value AS REAL), i.wellhead_temp_c) - i.ambient_temp_c) >= 15.0 THEN 'producing'
            WHEN w.well_type = 'T350' AND (COALESCE(CAST(o_temp.corrected_value AS REAL), i.wellhead_temp_c) - i.ambient_temp_c) >= 20.0 THEN 'producing'
            WHEN w.well_type = 'T500' AND (COALESCE(CAST(o_temp.corrected_value AS REAL), i.wellhead_temp_c) - i.ambient_temp_c) >= 25.0 THEN 'producing'
            ELSE 'non_producing' 
        END AS dynamic_status,

        -- False positive spill override
        CASE 
            WHEN o_false.override_id IS NOT NULL THEN 0
            ELSE i.spill_detected 
        END AS spill_detected,
        i.spill_detected AS raw_spill_detected,
        o_false.override_id AS spill_false_positive_override_id,
        
        -- Spill Volume (with override priority)
        CASE 
            WHEN o_false.override_id IS NOT NULL THEN 0.0
            ELSE COALESCE(CAST(o_vol.corrected_value AS REAL), i.spill_est_volume_bbl)
        END AS spill_est_volume_bbl,
        i.spill_est_volume_bbl AS raw_spill_est_volume_bbl,
        o_vol.override_id AS spill_volume_override_id,

        i.spill_area_pct,
        i.notes
    FROM inspections i
    JOIN wells w ON i.asset_id = w.asset_id
    LEFT JOIN areas a ON w.area_id = a.area_id
    LEFT JOIN user_feedback_overrides o_temp 
        ON o_temp.target_id = i.inspection_id 
        AND o_temp.field_name = 'wellhead_temp_c' 
        AND o_temp.is_active = 1
    LEFT JOIN user_feedback_overrides o_vol 
        ON o_vol.target_id = i.inspection_id 
        AND o_vol.field_name = 'spill_est_volume_bbl' 
        AND o_vol.is_active = 1
    LEFT JOIN user_feedback_overrides o_false 
        ON o_false.target_id = i.inspection_id 
        AND o_false.field_name = 'spill_detected' 
        AND (o_false.corrected_value = '0' OR LOWER(o_false.corrected_value) = 'false')
        AND o_false.is_active = 1;

    -- 2. Spills & SOP Containment View (SR-02 4.0-hour limit)
    DROP VIEW IF EXISTS v_spill_incidents;
    CREATE VIEW v_spill_incidents AS
    SELECT 
        i.inspection_id,
        i.asset_id,
        w.name AS well_name,
        w.well_type,
        w.area_id,
        a.name AS area_name,
        i.inspected_at,
        i.spill_detected,
        i.spill_est_volume_bbl,
        m.maintenance_id,
        m.started_at AS maintenance_started_at,
        m.containment_hours,
        m.sr02_met,
        CASE 
            WHEN m.sr02_met = 0 OR m.containment_hours > 4.0 THEN 0
            WHEN m.sr02_met = 1 OR (m.containment_hours IS NOT NULL AND m.containment_hours <= 4.0) THEN 1
            ELSE NULL
        END AS is_contained_within_sop_limit,
        4.0 AS sop_limit_hours,
        m.report_file,
        i.notes AS inspection_notes
    FROM v_inspections_effective i
    JOIN wells w ON i.asset_id = w.asset_id
    LEFT JOIN areas a ON w.area_id = a.area_id
    LEFT JOIN maintenance m ON m.triggered_by_inspection_id = i.inspection_id
    WHERE i.spill_detected = 1;
    """)
    conn.commit()


def ingest_fleet(conn: sqlite3.Connection):
    cur = conn.cursor()
    # 1. areas.json
    areas_path = DATASET_DIR / "fleet" / "areas.json"
    if areas_path.exists():
        with open(areas_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for a in data.get("areas", []):
                cur.execute(
                    "INSERT OR REPLACE INTO areas VALUES (?, ?, ?, ?, ?)",
                    (a["area_id"], a["name"], a["team_id"], a.get("center", {}).get("lat"), a.get("center", {}).get("lon"))
                )
            for t in data.get("teams", []):
                cur.execute(
                    "INSERT OR REPLACE INTO teams VALUES (?, ?, ?)",
                    (t["team_id"], t["name"], t.get("lead_user_id"))
                )

    # 2. users.json
    users_path = DATASET_DIR / "fleet" / "users.json"
    if users_path.exists():
        with open(users_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            users_list = data.get("users", []) if isinstance(data, dict) else data
            for u in users_list:
                cur.execute(
                    "INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?)",
                    (u["user_id"], u["name"], u["role"], u.get("team_id"))
                )
    conn.commit()
    print("Fleet metadata ingested.")


def ingest_wells_data(conn: sqlite3.Connection):
    cur = conn.cursor()
    asset_dirs = sorted(glob.glob(str(DATASET_DIR / "assets" / "WELL-*")))
    print(f"Ingesting {len(asset_dirs)} wells from {DATASET_DIR}...")

    wells_batch = []
    inspections_batch = []
    maintenance_batch = []
    reg_events_batch = []
    notes_batch = []
    seed_corrections = []

    for idx, asset_dir in enumerate(asset_dirs, 1):
        asset_path = Path(asset_dir)
        asset_id = asset_path.name

        # 1. metadata.json
        meta_file = asset_path / "metadata.json"
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
                loc = meta.get("location", {})
                last_insp = meta.get("last_inspection", {})
                wells_batch.append((
                    meta["asset_id"],
                    meta["name"],
                    meta.get("asset_category", "oil_well"),
                    meta["well_type"],
                    meta["area_id"],
                    meta["team_id"],
                    meta.get("in_charge_user_id"),
                    loc.get("lat"),
                    loc.get("lon"),
                    meta.get("installed_on"),
                    meta.get("recorded_status"),
                    meta.get("status"),
                    meta.get("decommissioned_on"),
                    last_insp.get("inspection_id"),
                    last_insp.get("inspected_at"),
                    last_insp.get("inspector_user_id")
                ))

        # 2. inspections.jsonl
        insp_file = asset_path / "inspections.jsonl"
        if insp_file.exists():
            with open(insp_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    inspections_batch.append((
                        row["inspection_id"],
                        row["asset_id"],
                        row["inspected_at"],
                        row.get("inspector_user_id"),
                        row.get("method"),
                        row.get("ambient_temp_c"),
                        row.get("wellhead_temp_c"),
                        1 if row.get("spill_detected") else 0,
                        row.get("spill_area_pct"),
                        row.get("spill_est_volume_bbl"),
                        row.get("recorded_at"),
                        row.get("notes")
                    ))

        # 3. maintenance.jsonl
        maint_file = asset_path / "maintenance.jsonl"
        if maint_file.exists():
            with open(maint_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    cost = row.get("cost_usd", {})
                    cost_rev = json.dumps(row.get("cost_revision")) if row.get("cost_revision") else None
                    maintenance_batch.append((
                        row["maintenance_id"],
                        row["asset_id"],
                        row["started_at"],
                        row.get("completed_at"),
                        row["maintenance_type"],
                        row.get("equipment_kind"),
                        row.get("issue"),
                        row.get("action_taken"),
                        row.get("technician_user_id"),
                        row.get("contractor"),
                        row.get("downtime_hours"),
                        cost.get("labor"),
                        cost.get("parts"),
                        cost.get("total"),
                        cost_rev,
                        row.get("recorded_at"),
                        row.get("triggered_by_inspection_id"),
                        row.get("report_file"),
                        None,  # containment_hours (populated from report text)
                        None   # sr02_met (populated from report text)
                    ))

        # 4. regulatory-events.jsonl
        reg_file = asset_path / "regulatory-events.jsonl"
        if reg_file.exists():
            with open(reg_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    reg_events_batch.append((
                        row["event_id"],
                        row["asset_id"],
                        row["date"],
                        row.get("agency"),
                        row["event_type"],
                        row.get("protocol_id"),
                        row.get("related_inspection_id"),
                        row.get("hours_to_report"),
                        row.get("detail"),
                        row.get("fine_usd"),
                        row.get("status")
                    ))

        # 5. context.jsonl
        ctx_file = asset_path / "context.jsonl"
        if ctx_file.exists():
            with open(ctx_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    note_id = row.get("note_id")
                    note_type = row.get("note_type")
                    insp_id = row.get("inspection_id")
                    field = row.get("field")
                    orig_val = str(row.get("original_value")) if row.get("original_value") is not None else None
                    corr_val = str(row.get("corrected_value")) if row.get("corrected_value") is not None else None
                    text = row.get("text", "")

                    notes_batch.append((
                        note_id,
                        row["asset_id"],
                        row["created_at"],
                        row.get("author_user_id"),
                        note_type,
                        insp_id,
                        field,
                        orig_val,
                        corr_val,
                        text,
                        row.get("valid_from"),
                        row.get("valid_to")
                    ))

                    # Seed formal override if note is a correction or data_correction
                    if note_type in ("correction", "data_correction") and insp_id:
                        if field and corr_val is not None:
                            seed_corrections.append((
                                "inspection_field",
                                insp_id,
                                field,
                                orig_val or "",
                                corr_val,
                                row.get("author_user_id", "system"),
                                text
                            ))
                        lower_text = text.lower()
                        if "rainwater" in lower_text or "not a spill" in lower_text or "not crude" in lower_text:
                            seed_corrections.append((
                                "spill_false_positive",
                                insp_id,
                                "spill_detected",
                                "1",
                                "0",
                                row.get("author_user_id", "system"),
                                text
                            ))

        if idx % 100 == 0 or idx == len(asset_dirs):
            print(f"Processed {idx}/{len(asset_dirs)} wells...")

    print("Writing records to database...")
    cur.executemany("INSERT OR REPLACE INTO wells VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", wells_batch)
    cur.executemany("INSERT OR REPLACE INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", inspections_batch)
    cur.executemany("INSERT OR REPLACE INTO maintenance VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", maintenance_batch)
    cur.executemany("INSERT OR REPLACE INTO regulatory_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", reg_events_batch)
    cur.executemany("INSERT OR REPLACE INTO context_notes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", notes_batch)

    if seed_corrections:
        cur.executemany("""
            INSERT OR REPLACE INTO user_feedback_overrides 
            (scope, target_id, field_name, original_value, corrected_value, author_user_id, rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, seed_corrections)
        print(f"Seeded {len(seed_corrections)} formal user_feedback_overrides from context notes.")

    conn.commit()
    print("Database tables populated successfully.")


def ingest_documents_and_containment(conn: sqlite3.Connection):
    cur = conn.cursor()
    docs_to_insert = []
    containment_updates = []

    # 1. Operating Manuals (T200, T350, T500)
    for mf in glob.glob(str(DATASET_DIR / "fleet" / "well-types" / "*.md")):
        path = Path(mf)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            sections = content.split("## ")
            doc_title = sections[0].strip().replace("# ", "")
            for s in sections[1:]:
                header = s.split("\n")[0].strip()
                body = "\n".join(s.split("\n")[1:]).strip()
                sec_id = f"MANUAL-{path.stem}-{header.split()[0]}"
                docs_to_insert.append((
                    sec_id,
                    f"{path.stem} Manual: {header}",
                    "manual",
                    None,
                    header,
                    f"Document: {doc_title}\nSection: {header}\n\n{body}",
                    f"Manual {path.stem} §{header}"
                ))

    # 2. SOPs (Operations rev2, Spill Response, Compliance, Memos, Recall)
    for sf in glob.glob(str(DATASET_DIR / "fleet" / "sops" / "*.md")):
        path = Path(sf)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            sections = content.split("## ")
            doc_title = sections[0].strip().replace("# ", "")
            for s in sections[1:]:
                header = s.split("\n")[0].strip()
                body = "\n".join(s.split("\n")[1:]).strip()
                sec_id = f"SOP-{path.stem}-{header.split()[0]}"
                docs_to_insert.append((
                    sec_id,
                    f"SOP {path.stem}: {header}",
                    "sop",
                    None,
                    header,
                    f"Standard Operating Procedure: {doc_title}\nSection: {header}\n\n{body}",
                    f"SOP {path.stem} §{header}"
                ))

    # 3. Free-text Maintenance Reports
    report_files = glob.glob(str(DATASET_DIR / "assets" / "WELL-*" / "maintenance-reports" / "*.md"))
    print(f"Indexing {len(report_files)} maintenance reports and parsing containment metrics...")
    for rf in report_files:
        path = Path(rf)
        asset_id = path.parent.parent.name
        doc_id = path.stem  # e.g. MNT-0001-002
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            docs_to_insert.append((
                doc_id,
                f"Maintenance Report {doc_id} ({asset_id})",
                "maintenance_report",
                asset_id,
                "Report Full Text",
                content,
                f"Report {doc_id}"
            ))

            # Extract containment hours and SR-02 compliance
            hours = None
            m_hours = re.search(r'contained (?:about )?([\d\.]+) hours', content, re.IGNORECASE)
            if m_hours:
                try:
                    hours = float(m_hours.group(1))
                except ValueError:
                    pass

            sr02_met = None
            if re.search(r'SR-02\s*\|\s*\*\*Not met\*\*', content, re.IGNORECASE) or re.search(r'SR-02\s*\|\s*Not met', content, re.IGNORECASE):
                sr02_met = 0
            elif re.search(r'SR-02\s*\|\s*Met', content, re.IGNORECASE):
                sr02_met = 1

            if hours is not None or sr02_met is not None:
                containment_updates.append((hours, sr02_met, doc_id))

    print(f"Inserting {len(docs_to_insert)} documents into SQLite FTS5...")
    cur.executemany("INSERT OR REPLACE INTO documents VALUES (?, ?, ?, ?, ?, ?, ?)", docs_to_insert)
    cur.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")

    if containment_updates:
        print(f"Updating {len(containment_updates)} maintenance records with containment metrics...")
        cur.executemany("""
            UPDATE maintenance
            SET containment_hours = ?, sr02_met = ?
            WHERE maintenance_id = ?
        """, containment_updates)

    conn.commit()
    print("Documents and containment metrics indexed.")


def main():
    start_time = time.time()
    print(f"=== Starting Ingestion for Test Dataset (600 Wells) ===")
    print(f"Dataset directory: {DATASET_DIR}")
    print(f"SQLite DB: {SQLITE_DB_PATH}")

    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        setup_schema(conn)
        ingest_fleet(conn)
        ingest_wells_data(conn)
        ingest_documents_and_containment(conn)
        create_views(conn)
    finally:
        conn.close()

    elapsed = time.time() - start_time
    print(f"=== Ingestion Complete in {elapsed:.2f} seconds! ===")


if __name__ == "__main__":
    main()
