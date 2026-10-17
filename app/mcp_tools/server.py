import os
import re
import json
import time
import socket
import sqlite3
import ipaddress
import urllib.parse
from typing import List, Any, Optional

import httpx
from bs4 import BeautifulSoup

try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server import MCPServer as FastMCP


# FastMCP Server Instance
server = FastMCP("AetherTools")


def _get_db_path() -> str:
    path = os.environ.get("SQLITE_DB_PATH", "storage/local.db")
    return path if path else "storage/local.db"


def _is_write_allowed() -> bool:
    return os.environ.get("SQLITE_ALLOW_WRITE", "false").lower() in ("true", "1", "yes")


# ============================================================================
# TOOL 1: Web Page Fetcher with Strict SSRF Defense
# ============================================================================

def _validate_host_ssrf(hostname: str, port: int) -> Optional[str]:
    """Resolves DNS and verifies all IP addresses are global public IPs."""
    try:
        addr_info = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as err:
        return f"DNS resolution failed for '{hostname}': {err}"

    if not addr_info:
        return f"No address records found for '{hostname}'."

    for item in addr_info:
        ip_str = item[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
            # Unwrap IPv4-mapped IPv6 address (e.g. ::ffff:127.0.0.1)
            if getattr(ip, "ipv4_mapped", None):
                ip = ip.ipv4_mapped

            # Strictly reject all non-global addresses
            if not ip.is_global:
                return (
                    f"Access to non-global/private IP ({ip}) is blocked for security "
                    "(blocks loopback, private RFC1918, link-local 169.254.169.254, and reserved networks)."
                )
        except ValueError:
            return f"Invalid IP address representation: {ip_str}"

    return None


@server.tool()
async def fetch_url(url: str, max_chars: int = 6000) -> str:
    """
    Fetches an HTTP/HTTPS web page with strict SSRF defense, 10s timeout,
    and HTML text extraction. Returns page title, clean text, and top links.

    Args:
        url: The web URL (http:// or https://) to fetch.
        max_chars: Maximum characters of text to return (default 6000).
    """
    current_url = url.strip()
    redirect_count = 0
    max_redirects = 3
    max_download_bytes = 2 * 1024 * 1024  # 2 MB limit
    accumulated_bytes = b""

    timeout = httpx.Timeout(10.0, connect=5.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            while True:
                parsed = urllib.parse.urlparse(current_url)

                # Protocol validation: http/https only
                if parsed.scheme.lower() not in ("http", "https"):
                    return f"Error: Unsupported protocol '{parsed.scheme}'. Only HTTP and HTTPS schemes are allowed."

                # Reject URLs with embedded credentials
                if parsed.username or parsed.password:
                    return "Error: URLs with embedded username/password credentials are rejected."

                hostname = parsed.hostname
                if not hostname:
                    return "Error: Invalid URL with missing hostname."

                port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)

                # SSRF Protection: Resolve and validate IP before making connection
                ssrf_error = _validate_host_ssrf(hostname, port)
                if ssrf_error:
                    return f"Error: {ssrf_error}"

                # Send request
                req = client.build_request("GET", current_url, headers={"User-Agent": "Aether-MCP-Fetcher/1.0"})
                resp = await client.send(req, stream=True)

                # Handle manual redirects (up to 3 hops)
                if resp.is_redirect:
                    await resp.aclose()
                    redirect_count += 1
                    if redirect_count > max_redirects:
                        return f"Error: Exceeded maximum of {max_redirects} redirects."

                    location = resp.headers.get("location")
                    if not location:
                        return "Error: Received HTTP redirect status without a Location header."

                    current_url = urllib.parse.urljoin(current_url, location)
                    continue

                if resp.status_code >= 400:
                    await resp.aclose()
                    return f"Error: HTTP {resp.status_code} returned from {current_url}"

                # Stream response body up to 2 MB
                async for chunk in resp.aiter_bytes():
                    accumulated_bytes += chunk
                    if len(accumulated_bytes) > max_download_bytes:
                        await resp.aclose()
                        return f"Error: Response body exceeded maximum allowed limit of 2 MB."

                await resp.aclose()
                break

        # Parse with BeautifulSoup
        soup = BeautifulSoup(accumulated_bytes, "html.parser")
        title = soup.title.string.strip() if (soup.title and soup.title.string) else "No Title"

        # Remove scripts, styles, navigation, headers, footers
        for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "aside"]):
            tag.decompose()

        # Extract readable text
        readable_text = soup.get_text(separator="\n", strip=True)
        if len(readable_text) > max_chars:
            readable_text = readable_text[:max_chars] + "\n...[truncated]"

        # Extract first 20 links
        links = []
        for a in soup.find_all("a", href=True):
            raw_href = a["href"].strip()
            if raw_href and not raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
                full_href = urllib.parse.urljoin(current_url, raw_href)
                link_text = a.get_text(strip=True) or full_href
                links.append(f"- [{link_text}]({full_href})")
                if len(links) >= 20:
                    break

        links_block = "\n".join(links) if links else "None found."

        return (
            f"### Page Title: {title}\n\n"
            f"### Content Summary:\n{readable_text}\n\n"
            f"### Links (first 20):\n{links_block}"
        )

    except httpx.TimeoutException:
        return "Error: Request timed out after 10 seconds."
    except Exception as exc:
        return f"Error fetching URL: {exc}"


# ============================================================================
# TOOL 2: SQLite Query and Schema Inspection Tools
# ============================================================================

def _ensure_db_file(db_path: str) -> None:
    """Pre-creates the directory and SQLite database file if not already existing."""
    dir_name = os.path.dirname(db_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    if not os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.close()


def _get_read_only_conn(db_path: str) -> sqlite3.Connection:
    """Returns a read-only SQLite connection with query_only=ON enabled."""
    _ensure_db_file(db_path)
    abs_path = os.path.abspath(db_path)
    # Open using URI mode=ro
    conn = sqlite3.connect(f"file:{abs_path}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON;")
    return conn


def _attach_timeout_handler(conn: sqlite3.Connection, timeout_sec: float = 5.0) -> None:
    """Attaches a progress handler that interrupts execution if query exceeds deadline."""
    start_time = time.monotonic()

    def progress_callback():
        if time.monotonic() - start_time > timeout_sec:
            return 1  # Non-zero return aborts query with sqlite3.OperationalError: interrupted
        return 0

    conn.set_progress_handler(progress_callback, 1000)


@server.tool()
def list_tables() -> str:
    """Lists all user tables in the SQLite database."""
    try:
        with _get_read_only_conn(_get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
            )
            tables = [row[0] for row in cursor.fetchall()]
            return json.dumps({"tables": tables})
    except Exception as exc:
        return f"Error listing tables: {exc}"


@server.tool()
def describe_table(table: str) -> str:
    """Describes table columns, data types, and primary keys from sqlite_master.

    Args:
        table: Name of the database table to describe.
    """
    clean_table = table.strip()
    try:
        with _get_read_only_conn(_get_db_path()) as conn:
            cursor = conn.cursor()
            # Validate table existence using parameterized lookup against sqlite_master
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = ?;",
                (clean_table,),
            )
            row = cursor.fetchone()
            if not row:
                return f"Error: Table '{clean_table}' does not exist in database."

            # Table existence verified! Safely quote identifier for PRAGMA
            safe_name = clean_table.replace('"', '""')
            cursor.execute(f'PRAGMA table_info("{safe_name}");')
            columns = [
                {
                    "cid": col[0],
                    "name": col[1],
                    "type": col[2],
                    "notnull": bool(col[3]),
                    "default_value": col[4],
                    "primary_key": bool(col[5]),
                }
                for col in cursor.fetchall()
            ]
            return json.dumps({"table": clean_table, "columns": columns}, indent=2)
    except Exception as exc:
        return f"Error describing table '{clean_table}': {exc}"


@server.tool()
def query(sql: str, params: Optional[List[Any]] = None) -> str:
    """
    Executes a read-only SELECT or WITH statement against the database.
    Parameterized, capped at 100 rows, with a 5s execution timeout.

    Args:
        sql: The SQL SELECT or WITH query to execute (e.g. 'SELECT count(*) FROM table').
        params: Optional list of query parameters.
    """
    raw_sql = sql.strip()

    # Allow one trailing semicolon, reject inner semicolons to block multi-statements
    clean_sql = re.sub(r";\s*$", "", raw_sql)
    if ";" in clean_sql:
        return "Error: Multi-statement queries are not allowed."

    # Validate statement starts with SELECT or WITH
    if not re.match(r"^(SELECT|WITH)\b", clean_sql, re.IGNORECASE):
        return "Error: Only SELECT and WITH statements are allowed in query()."

    try:
        with _get_read_only_conn(_get_db_path()) as conn:
            _attach_timeout_handler(conn, timeout_sec=5.0)
            cursor = conn.cursor()
            cursor.execute(clean_sql, params or [])
            cols = [d[0] for d in cursor.description] if cursor.description else []
            rows = cursor.fetchmany(100)
            records = [dict(zip(cols, row)) for row in rows]
            return json.dumps({"row_count": len(records), "rows": records}, default=str, indent=2)
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            return "Error: Query execution was interrupted because it exceeded the 5.0 second timeout limit."
        return f"Error executing query: {exc}"
    except Exception as exc:
        return f"Error executing query: {exc}"


# ============================================================================
# TOOL 3: Domain-Specific Oilfield Asset Intelligence Tools
# ============================================================================

@server.tool()
def get_well_status(asset_id: str) -> str:
    """
    Retrieves real-time operational status, thermal delta, dynamic production state,
    and active maintenance or shut-in context for a given oil well.

    Args:
        asset_id: The well ID (e.g. 'WELL-0001', 'WELL-0164').
    """
    clean_id = asset_id.strip().upper()
    db_path = _get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # 1. Fetch metadata
            cur.execute("""
                SELECT w.asset_id, w.name, w.well_type, w.area_id, a.name AS area_name,
                       w.recorded_status, w.in_charge_user_id, u.name AS in_charge_name
                FROM wells w
                LEFT JOIN areas a ON w.area_id = a.area_id
                LEFT JOIN users u ON w.in_charge_user_id = u.user_id
                WHERE w.asset_id = ?;
            """, (clean_id,))
            well_row = cur.fetchone()
            if not well_row:
                return json.dumps({"error": f"Well '{clean_id}' not found in database."})

            # 2. Fetch latest inspection from effective view
            cur.execute("""
                SELECT inspection_id, inspected_at, inspector_user_id, method,
                       ambient_temp_c, wellhead_temp_c, raw_wellhead_temp_c, delta_temp_c,
                       threshold_delta_c, is_producing_dynamically, dynamic_status,
                       wellhead_temp_override_author, wellhead_temp_override_rationale,
                       spill_detected, spill_est_volume_bbl, notes
                FROM v_inspections_effective
                WHERE asset_id = ?
                ORDER BY inspected_at DESC
                LIMIT 1;
            """, (clean_id,))
            insp_row = cur.fetchone()

            # 3. Fetch inspector name
            inspector_name = "Unknown"
            if insp_row and insp_row["inspector_user_id"]:
                cur.execute("SELECT name FROM users WHERE user_id = ?", (insp_row["inspector_user_id"],))
                u = cur.fetchone()
                if u:
                    inspector_name = u["name"]

            # 4. Fetch active or upcoming context notes
            cur.execute("""
                SELECT note_id, created_at, author_user_id, note_type, text, valid_from, valid_to
                FROM context_notes
                WHERE asset_id = ?
                ORDER BY created_at DESC
                LIMIT 3;
            """, (clean_id,))
            notes = [dict(r) for r in cur.fetchall()]

            # 5. Fetch open/recent maintenance jobs
            cur.execute("""
                SELECT maintenance_id, started_at, completed_at, maintenance_type, equipment_kind, issue, action_taken
                FROM maintenance
                WHERE asset_id = ?
                ORDER BY started_at DESC
                LIMIT 2;
            """, (clean_id,))
            repairs = [dict(r) for r in cur.fetchall()]

            result = {
                "asset_id": well_row["asset_id"],
                "name": well_row["name"],
                "well_type": well_row["well_type"],
                "area": well_row["area_name"] or well_row["area_id"],
                "in_charge": well_row["in_charge_name"] or well_row["in_charge_user_id"],
                "recorded_status": well_row["recorded_status"],
                "latest_inspection": dict(insp_row) if insp_row else None,
                "inspector_name": inspector_name,
                "recent_context_notes": notes,
                "recent_repairs": repairs,
                "is_recorded_status_stale": (
                    bool(insp_row and ((insp_row["dynamic_status"] == "producing" and well_row["recorded_status"] == "down") or
                         (insp_row["dynamic_status"] == "non_producing" and well_row["recorded_status"] == "active")))
                )
            }
            return json.dumps(result, indent=2, default=str)
    except Exception as exc:
        return json.dumps({"error": f"Failed to retrieve well status: {exc}"})


@server.tool()
def record_user_feedback(
    user_id: str,
    target_id: str,
    field_name: str,
    corrected_value: str,
    rationale: str,
    scope: str = "inspection_field"
) -> str:
    """
    Saves an operator's feedback or correction into the system of record.
    The correction immediately takes priority over raw data in all future queries.

    Args:
        user_id: User ID of the operator making the correction (e.g. 'U-201').
        target_id: Target ID being corrected (e.g. 'INS-0164-0205', 'WELL-0151', 'T350').
        field_name: Field being updated (e.g. 'wellhead_temp_c', 'spill_est_volume_bbl', 'spill_detected').
        corrected_value: The new verified value (e.g. '41.0', '5.4', 'false').
        rationale: Reason for the change (e.g. 'Faulty handheld thermal gun; re-measured by field crew').
        scope: Scope of correction ('inspection_field', 'well_type_rule', 'spill_false_positive').
    """
    db_path = _get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            # Fetch original value if available
            orig_val = None
            if scope == "inspection_field" and target_id.startswith("INS-"):
                if field_name == "wellhead_temp_c":
                    cur.execute("SELECT wellhead_temp_c FROM inspections WHERE inspection_id = ?", (target_id,))
                    row = cur.fetchone()
                    if row:
                        orig_val = str(row[0])
                elif field_name == "spill_est_volume_bbl":
                    cur.execute("SELECT spill_est_volume_bbl FROM inspections WHERE inspection_id = ?", (target_id,))
                    row = cur.fetchone()
                    if row:
                        orig_val = str(row[0])

            cur.execute("""
                INSERT INTO user_feedback_overrides
                (scope, target_id, field_name, original_value, corrected_value, author_user_id, rationale, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1);
            """, (scope, target_id, field_name, orig_val or "raw_default", str(corrected_value), user_id, rationale))
            conn.commit()
            override_id = cur.lastrowid
            return json.dumps({
                "status": "success",
                "override_id": override_id,
                "message": f"Feedback successfully recorded. Future queries for {target_id}.{field_name} will use {corrected_value} instead of {orig_val or 'raw value'}.",
                "author": user_id,
                "rationale": rationale
            })
    except Exception as exc:
        return json.dumps({"status": "error", "message": f"Failed to record feedback: {exc}"})


@server.tool()
def record_unconfirmed_claim(user_id: str, asset_id: str, claim_text: str, conflicting_evidence: str) -> str:
    """
    Logs an unconfirmed claim when an operator's statement contradicts verified database records.
    Explicitly tracks the contradiction without silently overriding verified data.

    Args:
        user_id: The operator making the claim.
        asset_id: The affected well ID.
        claim_text: The operator's statement (e.g. 'WELL-0175 is running fine').
        conflicting_evidence: The contradictory record (e.g. '15 Oct inspection shows ΔT = 0.4°C, shut in').
    """
    db_path = _get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO unconfirmed_claims (user_id, asset_id, claim_text, conflicting_evidence)
                VALUES (?, ?, ?, ?);
            """, (user_id, asset_id, claim_text, conflicting_evidence))
            conn.commit()
            return json.dumps({
                "status": "logged_as_unconfirmed",
                "claim_id": cur.lastrowid,
                "note": "Claim recorded with unconfirmed status due to contradictory sensor readings."
            })
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)})


@server.tool()
def record_well_type_rule(user_id: str, well_type: str, rule_name: str, rule_value: str, rationale: str) -> str:
    """
    Stores an operational rule applied across an entire well type (e.g. RCA after 2 repairs for T350).

    Args:
        user_id: Author user ID.
        well_type: 'T200' or 'T350'.
        rule_name: Rule identifier (e.g. 'pump_jack_rca_threshold').
        rule_value: Rule value (e.g. '2').
        rationale: Operational rationale.
    """
    db_path = _get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO user_rules (user_id, target_scope, rule_name, rule_value, rationale, is_active)
                VALUES (?, ?, ?, ?, ?, 1);
            """, (user_id, well_type, rule_name, rule_value, rationale))
            conn.commit()
            return json.dumps({
                "status": "success",
                "message": f"Rule '{rule_name}={rule_value}' active for all {well_type} wells by {user_id}."
            })
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)})


@server.tool()
def get_maintenance_report(report_id_or_asset_id: str) -> str:
    """
    Retrieves full maintenance and repair report details (containment duration,
    work done, root cause, protocol compliance like SR-02 4-hour containment limit)
    for a maintenance job or asset.

    Args:
        report_id_or_asset_id: Maintenance ID (e.g. 'MNT-0082-028') or asset ID (e.g. 'WELL-0082').
    """
    clean_id = report_id_or_asset_id.strip().upper()
    db_path = _get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT doc_id, title, category, asset_id, content
                FROM documents
                WHERE doc_id = ? OR doc_id LIKE ? OR asset_id = ?
                ORDER BY doc_id DESC
                LIMIT 5;
            """, (clean_id, f"%{clean_id}%", clean_id))
            rows = [dict(r) for r in cur.fetchall()]
            if not rows:
                return json.dumps({"error": f"No maintenance report found matching '{clean_id}'."})
            return json.dumps({"reports": rows}, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@server.tool()
def search_documents(query_str: Optional[str] = None, query: Optional[str] = None, category: Optional[str] = None, limit: int = 5) -> str:
    """
    Full-text search across all operating manuals, SOPs, MOC memos, and maintenance reports.
    Useful for finding specific procedures, recalled pump lots, root causes, soil sampling rules, etc.

    Args:
        query_str: Search terms or keywords (e.g. 'recalled pump LOT-2409-A', 'Soil samples sent to the lab', 'temporary flowline bypass').
        query: Alternative parameter name for search terms.
        category: Optional filter: 'sop', 'manual', or 'maintenance_report'.
        limit: Max results to return (default 5).
    """
    db_path = _get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            raw_input = query_str or query or ""
            clean_query = re.sub(r'[^\w\s\-\.]', ' ', raw_input).strip()
            terms = clean_query.split()
            if not terms:
                return json.dumps({"results": []})
            fts_query = " OR ".join([f'"{t}"' for t in terms[:6]])
            if category:
                cur.execute("""
                    SELECT doc_id, title, category, asset_id, section, snippet(documents_fts, 5, '<b>', '</b>', '...', 25) AS snippet, citation_ref
                    FROM documents_fts
                    WHERE documents_fts MATCH ? AND category = ?
                    ORDER BY rank
                    LIMIT ?;
                """, (fts_query, category, limit))
            else:
                cur.execute("""
                    SELECT doc_id, title, category, asset_id, section, snippet(documents_fts, 5, '<b>', '</b>', '...', 25) AS snippet, citation_ref
                    FROM documents_fts
                    WHERE documents_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?;
                """, (fts_query, limit))
            rows = [dict(r) for r in cur.fetchall()]
            return json.dumps({"count": len(rows), "results": rows}, indent=2)
    except Exception as exc:
        return json.dumps({"error": f"Search failed: {exc}"})


if __name__ == "__main__":
    # Run over stdio transport
    server.run(transport="stdio")

