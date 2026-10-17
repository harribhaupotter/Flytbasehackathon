import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx
from dotenv import load_dotenv

try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server import MCPServer as FastMCP

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

load_dotenv()

server = FastMCP("OilfieldKnowledgeTools")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
QDRANT_STORAGE_PATH = BASE_DIR / "storage" / "qdrant_db"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def _get_qdrant_client() -> QdrantClient:
    return QdrantClient(path=str(QDRANT_STORAGE_PATH))


def _embed_query(query: str) -> List[float]:
    """Generates a 768-dim query embedding using Gemini Embedding API."""
    if not GEMINI_API_KEY:
        return [0.0] * 768

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={GEMINI_API_KEY}"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json={
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": query}]},
                "outputDimensionality": 768
            })
            if resp.status_code == 200:
                data = resp.json()
                return data.get("embedding", {}).get("values", [0.0] * 768)
    except Exception as exc:
        print(f"Embedding error: {exc}", file=sys.stderr)

    return [0.0] * 768


@server.tool()
def search_knowledge_base(
    query: str,
    category: Optional[str] = None,
    asset_id: Optional[str] = None,
    limit: int = 5
) -> str:
    """
    Performs semantic vector search across Standard Operating Procedures (SOPs),
    Well Operating Manuals (T200, T350), and Free-text Maintenance Reports.

    Args:
        query: Natural language query (e.g. 'T200 production temperature threshold', 'spill containment time limit', 'SR-01 protocol').
        category: Optional filter: 'sop', 'manual', or 'maintenance_report'.
        asset_id: Optional asset filter (e.g. 'WELL-0001').
        limit: Number of ranked chunks to return (default: 5).
    """
    clean_query = query.strip()
    if not clean_query:
        return json.dumps({"error": "Empty search query", "results": []})

    client = _get_qdrant_client()
    try:
        collection_name = "oilfield_knowledge"
        if not client.collection_exists(collection_name):
            return json.dumps({
                "error": f"Collection '{collection_name}' not yet indexed. Run data ingestion first.",
                "results": []
            })

        query_vector = _embed_query(clean_query)

        must_filters = []
        if category:
            must_filters.append(
                qmodels.FieldCondition(
                    key="category",
                    match=qmodels.MatchValue(value=category)
                )
            )
        if asset_id:
            must_filters.append(
                qmodels.FieldCondition(
                    key="asset_id",
                    match=qmodels.MatchValue(value=asset_id.strip().upper())
                )
            )

        q_filter = qmodels.Filter(must=must_filters) if must_filters else None

        if hasattr(client, "query_points"):
            response = client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=q_filter,
                limit=limit,
                with_payload=True
            )
            results = response.points
        else:
            results = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=q_filter,
                limit=limit,
                with_payload=True
            )

        formatted = []
        for r in results:
            p = r.payload or {}
            formatted.append({
                "score": round(r.score, 4),
                "title": p.get("title", "Untitled Document"),
                "document_id": p.get("document_id", "N/A"),
                "category": p.get("category", "general"),
                "asset_id": p.get("asset_id"),
                "section": p.get("section"),
                "content": p.get("text", "").strip(),
                "citation_ref": p.get("citation_ref", p.get("document_id"))
            })

        return json.dumps({
            "query": clean_query,
            "total_hits": len(formatted),
            "results": formatted
        }, indent=2)

    except Exception as exc:
        return json.dumps({"error": f"Vector search failed: {exc}", "results": []})
    finally:
        client.close()


if __name__ == "__main__":
    server.run(transport="stdio")
