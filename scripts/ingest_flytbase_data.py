#!/usr/bin/env python3
"""
scripts/ingest_flytbase_data.py

High-performance data ingestion pipeline for the FlytBase Asset Intelligence Copilot.
Populates SQLite (`storage/local.db`) with relational telemetry and embedded Qdrant
(`storage/qdrant_db`) with chunked SOPs, manuals, reports, and context notes.
"""

import os
import glob
import json
import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "flytbase" / "flytbase-ahc-swe-asset-intelligence-dataset" / "sample-data"
SQLITE_DB_PATH = BASE_DIR / "storage" / "local.db"
QDRANT_STORAGE_PATH = BASE_DIR / "storage" / "qdrant_db"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
QDRANT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)


# ============================================================================
# 1. SQLITE SCHEMA SETUP
# ============================================================================

def setup_sqlite_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.executescript("""
    PRAGMA journal_mode = WAL;
    PRAGMA synchronous = NORMAL;

    CREATE TABLE IF NOT EXISTS areas (
        area_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        team_id TEXT NOT NULL,
        lat REAL,
        lon REAL
    );

    CREATE TABLE IF NOT EXISTS teams (
        team_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        lead_user_id TEXT
    );

    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        team_id TEXT
    );

    CREATE TABLE IF NOT EXISTS wells (
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
        last_inspection_id TEXT,
        last_inspection_time TEXT,
        last_inspection_inspector TEXT
    );

    CREATE TABLE IF NOT EXISTS inspections (
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
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS maintenance (
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
        triggered_by_inspection_id TEXT,
        report_file TEXT
    );

    CREATE TABLE IF NOT EXISTS regulatory_events (
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

    CREATE TABLE IF NOT EXISTS context_notes (
        note_id TEXT PRIMARY KEY,
        asset_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        author_user_id TEXT,
        note_type TEXT NOT NULL,
        inspection_id TEXT,
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

    -- Indices for fast joins and aggregations
    CREATE INDEX IF NOT EXISTS idx_inspections_asset_date ON inspections(asset_id, inspected_at);
    CREATE INDEX IF NOT EXISTS idx_maintenance_asset_date ON maintenance(asset_id, started_at);
    CREATE INDEX IF NOT EXISTS idx_reg_events_asset_date ON regulatory_events(asset_id, date);
    CREATE INDEX IF NOT EXISTS idx_context_asset ON context_notes(asset_id);
    CREATE INDEX IF NOT EXISTS idx_overrides_lookup ON user_feedback_overrides(target_id, field_name, is_active);

    -- Effective View incorporating Dynamic Production Status and Human Feedback Overrides
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
        
        -- Production threshold delta for well type
        CASE WHEN w.well_type = 'T200' THEN 15.0 ELSE 20.0 END AS threshold_delta_c,
        
        -- Dynamic Production Status (1 = producing, 0 = non-producing)
        CASE 
            WHEN w.well_type = 'T200' AND (COALESCE(CAST(o_temp.corrected_value AS REAL), i.wellhead_temp_c) - i.ambient_temp_c) >= 15.0 THEN 1
            WHEN w.well_type = 'T350' AND (COALESCE(CAST(o_temp.corrected_value AS REAL), i.wellhead_temp_c) - i.ambient_temp_c) >= 20.0 THEN 1
            ELSE 0 
        END AS is_producing_dynamically,

        CASE 
            WHEN w.well_type = 'T200' AND (COALESCE(CAST(o_temp.corrected_value AS REAL), i.wellhead_temp_c) - i.ambient_temp_c) >= 15.0 THEN 'producing'
            WHEN w.well_type = 'T350' AND (COALESCE(CAST(o_temp.corrected_value AS REAL), i.wellhead_temp_c) - i.ambient_temp_c) >= 20.0 THEN 'producing'
            ELSE 'non_producing' 
        END AS dynamic_status,

        -- False positive spill override (e.g. CTX-0001-001 rainwater)
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
    """)
    conn.commit()


# ============================================================================
# 2. INGEST STRUCTURED DATA
# ============================================================================

def ingest_fleet_metadata(conn: sqlite3.Connection):
    cur = conn.cursor()
    # Ingest areas.json
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

    # Ingest users.json
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


def ingest_all_wells(conn: sqlite3.Connection):
    cur = conn.cursor()
    asset_dirs = sorted(glob.glob(str(DATASET_DIR / "assets" / "WELL-*")))
    print(f"Found {len(asset_dirs)} asset directories to ingest...")

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
                cur.execute("""
                    INSERT OR REPLACE INTO wells VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
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
                        row.get("triggered_by_inspection_id"),
                        row.get("report_file")
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
                    text = row.get("text", "")
                    notes_batch.append((
                        note_id,
                        row["asset_id"],
                        row["created_at"],
                        row.get("author_user_id"),
                        note_type,
                        insp_id,
                        text,
                        row.get("valid_from"),
                        row.get("valid_to")
                    ))
                    # Seed formal override if note is a correction
                    if note_type == "correction" and insp_id:
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

        if idx % 50 == 0 or idx == len(asset_dirs):
            print(f"Processed {idx}/{len(asset_dirs)} wells...")

    print("Inserting batch records into SQLite...")
    cur.executemany("INSERT OR REPLACE INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", inspections_batch)
    cur.executemany("INSERT OR REPLACE INTO maintenance VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", maintenance_batch)
    cur.executemany("INSERT OR REPLACE INTO regulatory_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", reg_events_batch)
    cur.executemany("INSERT OR REPLACE INTO context_notes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", notes_batch)

    # Insert seeded corrections
    for c in seed_corrections:
        cur.execute("""
            INSERT OR IGNORE INTO user_feedback_overrides 
            (scope, target_id, field_name, original_value, corrected_value, author_user_id, rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, c)

    conn.commit()
    print(f"SQLite population complete: {len(inspections_batch)} inspections, {len(maintenance_batch)} repairs, {len(reg_events_batch)} reg events, {len(notes_batch)} notes.")


# ============================================================================
# 3. EMBED & INGEST UNSTRUCTURED DOCUMENTS INTO QDRANT
# ============================================================================

def get_gemini_embeddings_batch(texts: List[str], batch_size: int = 16) -> List[List[float]]:
    """Batched embedding generation via Google Gemini Embeddings API."""
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY not set. Generating zero vectors for offline testing.")
        return [[0.0] * 768 for _ in texts]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents?key={GEMINI_API_KEY}"
    embeddings = []

    # Process in batches of 16
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        requests = [
            {
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": t[:2000]}]},  # Cap chunk text size
                "outputDimensionality": 768
            }
            for t in chunk
        ]

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, json={"requests": requests})
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("embeddings", []):
                        embeddings.append(item.get("values", []))
                else:
                    print(f"Gemini embedding batch failed ({resp.status_code}): {resp.text[:100]}")
                    for _ in chunk:
                        embeddings.append([0.0] * 768)
        except Exception as err:
            print(f"Gemini API request error: {err}")
            for _ in chunk:
                embeddings.append([0.0] * 768)

        time.sleep(0.1)  # Mild pacing to respect rate limits

    return embeddings


def ingest_unstructured_to_qdrant():
    print(f"Initializing local embedded Qdrant client at {QDRANT_STORAGE_PATH}...")
    qclient = QdrantClient(path=str(QDRANT_STORAGE_PATH))

    collection_name = "oilfield_knowledge"
    if qclient.collection_exists(collection_name):
        qclient.delete_collection(collection_name)

    qclient.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(size=768, distance=qmodels.Distance.COSINE),
    )

    documents_to_embed = []

    # 1. Operating Manuals (T200, T350)
    manual_files = glob.glob(str(DATASET_DIR / "fleet" / "well-types" / "*.md"))
    for mf in manual_files:
        path = Path(mf)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            # Split sections by markdown headings
            sections = content.split("## ")
            doc_title = sections[0].strip().replace("# ", "")
            for s in sections[1:]:
                header = s.split("\n")[0].strip()
                body = "\n".join(s.split("\n")[1:]).strip()
                documents_to_embed.append({
                    "title": f"{path.stem} Manual: {header}",
                    "document_id": f"MANUAL-{path.stem}",
                    "category": "manual",
                    "well_type": path.stem,
                    "section": header,
                    "text": f"Document: {doc_title}\nSection: {header}\n\n{body}",
                    "citation_ref": f"Manual {path.stem} §{header}"
                })

    # 2. SOPs (Spill Response, Regulatory Compliance, Field Work)
    sop_files = glob.glob(str(DATASET_DIR / "fleet" / "sops" / "*.md"))
    for sf in sop_files:
        path = Path(sf)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            sections = content.split("## ")
            doc_title = sections[0].strip().replace("# ", "")
            for s in sections[1:]:
                header = s.split("\n")[0].strip()
                body = "\n".join(s.split("\n")[1:]).strip()
                documents_to_embed.append({
                    "title": f"SOP {path.stem}: {header}",
                    "document_id": f"SOP-{path.stem}",
                    "category": "sop",
                    "section": header,
                    "text": f"Standard Operating Procedure: {doc_title}\nSection: {header}\n\n{body}",
                    "citation_ref": f"SOP {path.stem} §{header}"
                })

    # 3. Free-text Maintenance Reports (~1500 reports)
    report_files = glob.glob(str(DATASET_DIR / "assets" / "WELL-*" / "maintenance-reports" / "*.md"))
    print(f"Indexing {len(report_files)} free-text maintenance reports...")
    for rf in report_files:
        path = Path(rf)
        asset_id = path.parent.parent.name
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            documents_to_embed.append({
                "title": f"Maintenance Report {path.stem} ({asset_id})",
                "document_id": path.stem,
                "category": "maintenance_report",
                "asset_id": asset_id,
                "section": "Report Summary",
                "text": f"Asset: {asset_id}\nReport ID: {path.stem}\nContent:\n{content[:1500]}",
                "citation_ref": f"Report {path.stem}"
            })

    print(f"Total documents to embed: {len(documents_to_embed)}")
    all_texts = [d["text"] for d in documents_to_embed]

    # Generate vectors in batches
    embeddings = get_gemini_embeddings_batch(all_texts, batch_size=20)

    # Insert into Qdrant in chunks of 100
    points = []
    for idx, (doc, vec) in enumerate(zip(documents_to_embed, embeddings)):
        points.append(
            qmodels.PointStruct(
                id=idx + 1,
                vector=vec,
                payload=doc
            )
        )

    for i in range(0, len(points), 100):
        qclient.upsert(
            collection_name=collection_name,
            points=points[i:i + 100]
        )

    qclient.close()
    print("Qdrant indexing complete!")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    import argparse
    global DATASET_DIR

    parser = argparse.ArgumentParser(description="Ingest FlytBase Asset Intelligence dataset")
    parser.add_argument("--data-dir", type=str, default=str(DATASET_DIR), help="Path to sample-data or test-data directory")
    parser.add_argument("--skip-qdrant", action="store_true", help="Skip Qdrant embeddings vector ingestion")
    parser.add_argument("--skip-sqlite", action="store_true", help="Skip SQLite ingestion")
    args = parser.parse_args()

    DATASET_DIR = Path(args.data_dir).resolve()
    print(f"Using dataset directory: {DATASET_DIR}")
    print(f"Connecting to SQLite database: {SQLITE_DB_PATH}")

    if not args.skip_sqlite:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        try:
            setup_sqlite_schema(conn)
            ingest_fleet_metadata(conn)
            ingest_all_wells(conn)
        finally:
            conn.close()

    if not args.skip_qdrant:
        ingest_unstructured_to_qdrant()

    print("\nIngestion pipeline finished successfully!")


if __name__ == "__main__":
    main()
