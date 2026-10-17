import os
import json
import sqlite3
import pytest
from app.mcp_tools.server import (
    fetch_url,
    list_tables,
    describe_table,
    query,
    server as mcp_server,
)


@pytest.mark.asyncio
async def test_fetch_url_ssrf_rejections():
    """Verify fetch_url rejects private IPs, loopback, metadata IPs, file://, and credentials."""
    # 1. Loopback IP
    res_loopback = await fetch_url("http://127.0.0.1:8000")
    assert "Error:" in res_loopback
    assert "blocked for security" in res_loopback.lower()

    # 2. AWS / GCP Cloud Metadata Link-Local IP (169.254.169.254)
    res_metadata = await fetch_url("http://169.254.169.254/latest/meta-data/")
    assert "Error:" in res_metadata
    assert "blocked for security" in res_metadata.lower()

    # 3. Disallowed scheme (file://)
    res_file = await fetch_url("file:///etc/passwd")
    assert "Error:" in res_file
    assert "Unsupported protocol" in res_file

    # 4. Embedded credentials
    res_creds = await fetch_url("http://admin:secret@example.com")
    assert "Error:" in res_creds
    assert "embedded username/password" in res_creds


def test_sqlite_tools_workflow(tmp_path):
    """Test list_tables, describe_table, and read-only query on a temporary SQLite DB."""
    test_db = str(tmp_path / "test.db")
    os.environ["SQLITE_DB_PATH"] = test_db

    # Initialize table and insert sample rows
    conn = sqlite3.connect(test_db)
    conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL);")
    conn.execute("INSERT INTO products (name, price) VALUES ('Widget A', 19.99), ('Widget B', 29.99);")
    conn.commit()
    conn.close()

    # 1. list_tables
    tables_res = json.loads(list_tables())
    assert "products" in tables_res["tables"]

    # 2. describe_table
    desc_res = json.loads(describe_table("products"))
    col_names = [c["name"] for c in desc_res["columns"]]
    assert "id" in col_names
    assert "name" in col_names
    assert "price" in col_names

    # 3. describe_table malicious input rejected
    malicious_res = describe_table("products'; DROP TABLE products;--")
    assert "Error: Table" in malicious_res

    # 4. query valid SELECT
    query_res = json.loads(query("SELECT name, price FROM products ORDER BY price;"))
    assert query_res["row_count"] == 2
    assert query_res["rows"][0]["name"] == "Widget A"

    # 5. query rejects write / mutation statements
    drop_res = query("DROP TABLE products;")
    assert "Error:" in drop_res
    assert "Only SELECT and WITH" in drop_res

    delete_res = query("DELETE FROM products WHERE id = 1;")
    assert "Error:" in delete_res

    # 6. query rejects multi-statement inputs
    multi_res = query("SELECT 1; SELECT 2;")
    assert "Error: Multi-statement" in multi_res


def test_sqlite_query_interrupted_timeout(tmp_path):
    """Test that long-running recursive queries are interrupted by the 5s progress handler."""
    test_db = str(tmp_path / "timeout.db")
    os.environ["SQLITE_DB_PATH"] = test_db

    # Trigger a heavy recursive CTE that would run indefinitely
    runaway_sql = """
    WITH RECURSIVE r(i) AS (
      VALUES(0)
      UNION ALL
      SELECT i+1 FROM r WHERE i < 100000000
    )
    SELECT count(*) FROM r;
    """
    res = query(runaway_sql)
    assert "Error: Query execution was interrupted" in res or "timeout" in res.lower()


def test_sqlite_execute_absent_when_write_disabled():
    """Verify execute tool is absent when SQLITE_ALLOW_WRITE=false."""
    # Check registered tool names on the FastMCP server
    tools = mcp_server._tool_manager.list_tools() if hasattr(mcp_server, "_tool_manager") else []
    tool_names = [t.name for t in tools]
    assert "list_tables" in tool_names
    assert "describe_table" in tool_names
    assert "query" in tool_names
    assert "execute" not in tool_names
