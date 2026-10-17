import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_models(client: AsyncClient):
    """GET /models must list allowed models."""
    response = await client.get("/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "default_model" in data
    assert "gemma-4-26b-a4b-it" in data["models"]
    assert "mock" in data["models"]
