#!/usr/bin/env python3
"""
scripts/index_documents_sqlite.py

Populates SQLite FTS5 table with all Operating Manuals, SOPs, and Maintenance Reports
for instant, deterministic, zero-quota full-text search.
"""

import glob
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "flytbase" / "flytbase-ahc-swe-asset-intelligence-dataset" / "sample-data"
SQLITE_DB_PATH = BASE_DIR / "storage" / "local.db"


def main():
    import argparse
    global DATASET_DIR

    parser = argparse.ArgumentParser(description="Index FlytBase documents into SQLite FTS5")
    parser.add_argument("--data-dir", type=str, default=str(DATASET_DIR), help="Path to sample-data or test-data directory")
    args = parser.parse_args()

    DATASET_DIR = Path(args.data_dir).resolve()
    print(f"Indexing documents from {DATASET_DIR} into SQLite FTS5 at {SQLITE_DB_PATH}...")
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            title TEXT,
            category TEXT,
            asset_id TEXT,
            section TEXT,
            content TEXT,
            citation_ref TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
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
    """)

    docs_to_insert = []

    # 1. Operating Manuals
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

    # 2. SOPs
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
    for rf in glob.glob(str(DATASET_DIR / "assets" / "WELL-*" / "maintenance-reports" / "*.md")):
        path = Path(rf)
        asset_id = path.parent.parent.name
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            docs_to_insert.append((
                path.stem,
                f"Maintenance Report {path.stem} ({asset_id})",
                "maintenance_report",
                asset_id,
                "Report Details",
                f"Asset: {asset_id}\nReport ID: {path.stem}\nContent:\n{content}",
                f"Report {path.stem}"
            ))

    cur.executemany("""
        INSERT OR REPLACE INTO documents (doc_id, title, category, asset_id, section, content, citation_ref)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, docs_to_insert)

    # Rebuild FTS index
    cur.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild');")
    conn.commit()
    conn.close()
    print(f"Indexed {len(docs_to_insert)} documents into SQLite FTS5 successfully!")


if __name__ == "__main__":
    main()
