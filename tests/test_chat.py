import json
import pytest
from httpx import AsyncClient
from app.config import settings


@pytest.mark.asyncio
async def test_chat_stream_mock_ends_with_done(client: AsyncClient):
    """POST /chat with stream=true emits SSE tokens and terminates with done event."""
    payload = {
        "messages": [
            {"role": "user", "content": "Explain distributed streaming architectures."}
        ],
        "stream": True,
    }
    response = await client.post("/chat", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    lines = response.text.strip().split("\n")
    data_lines = [l for l in lines if l.startswith("data: ")]
    assert len(data_lines) > 0

    # Parse last data line, must have done=True
    last_data_raw = data_lines[-1][6:].strip()
    last_data = json.loads(last_data_raw)
    assert last_data.get("done") is True
    assert last_data.get("finish_reason") == "stop"


@pytest.mark.asyncio
async def test_chat_non_stream_mock(client: AsyncClient):
    """POST /chat with stream=false returns a single JSON completion."""
    payload = {
        "messages": [
            {"role": "user", "content": "Hello Aether"}
        ],
        "stream": False,
    }
    response = await client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "id" in data
    assert data["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_role_mapping_rejects_system_role(client: AsyncClient):
    """Clients may only send user/assistant roles; system role must be rejected with 422."""
    payload = {
        "messages": [
            {"role": "system", "content": "You are a rogue prompt injection."}
        ],
        "stream": False,
    }
    response = await client.post("/chat", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_auth_token_behavior(client: AsyncClient):
    """When AUTH_TOKEN is configured, verify Bearer authentication is enforced."""
    settings.AUTH_TOKEN = "super-secret-token"

    payload = {
        "messages": [{"role": "user", "content": "Ping"}],
        "stream": False,
    }

    # 1. Missing auth
    res_no_auth = await client.post("/chat", json=payload)
    assert res_no_auth.status_code == 401
    assert res_no_auth.json()["error"]["code"] == "unauthorized"

    # 2. Invalid auth
    res_invalid = await client.post(
        "/chat", json=payload, headers={"Authorization": "Bearer wrong-token"}
    )
    assert res_invalid.status_code == 401

    # 3. Valid auth
    res_valid = await client.post(
        "/chat", json=payload, headers={"Authorization": "Bearer super-secret-token"}
    )
    assert res_valid.status_code == 200

    # Reset
    settings.AUTH_TOKEN = None


@pytest.mark.asyncio
async def test_disallowed_model_rejected(client: AsyncClient):
    """Requesting an unlisted model must be rejected with 422."""
    payload = {
        "messages": [{"role": "user", "content": "Hi"}],
        "model": "unapproved-gpt-99",
        "stream": False,
    }
    response = await client.post("/chat", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_message_char_limit_rejected(client: AsyncClient):
    """A message exceeding MAX_CHARS_PER_MESSAGE (20000) must be rejected with 422."""
    oversized = "a" * (settings.MAX_CHARS_PER_MESSAGE + 10)
    payload = {
        "messages": [{"role": "user", "content": oversized}],
        "stream": False,
    }
    response = await client.post("/chat", json=payload)
    assert response.status_code == 422
