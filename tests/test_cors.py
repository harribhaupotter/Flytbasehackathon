import pytest
from httpx import AsyncClient
from app.config import settings


@pytest.mark.asyncio
async def test_cors_headers_on_standard_response(client: AsyncClient):
    """Outermost CORS middleware ensures allowed origins receive CORS headers on normal responses."""
    origin = "http://localhost:5173"
    response = await client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "x-request-id" in response.headers


@pytest.mark.asyncio
async def test_cors_outermost_on_413_payload_too_large(client: AsyncClient):
    """
    When RequestBodyLimitMiddleware catches an oversized body and emits 413,
    the response passes through the outermost CORSMiddleware and receives CORS headers.
    """
    origin = "http://localhost:5173"
    # Send content-length header exceeding MAX_REQUEST_BODY_BYTES (10 MB)
    headers = {
        "Origin": origin,
        "Content-Length": str(settings.MAX_REQUEST_BODY_BYTES + 5000),
        "Content-Type": "application/json",
    }
    response = await client.post("/chat", headers=headers, content=b"{}")
    assert response.status_code == 413
    assert response.headers.get("access-control-allow-origin") == origin
    assert "x-request-id" in response.headers
