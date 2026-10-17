import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.config import settings


@pytest_asyncio.fixture
async def client():
    """Provides an asynchronous test client for the FastAPI app."""
    # Ensure test configuration defaults
    original_mcp = settings.MCP_ENABLED
    settings.AUTH_TOKEN = None
    settings.LLM_PROVIDER = "mock"
    settings.MCP_ENABLED = False

    test_app = create_app()
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        # Trigger lifespan
        async with test_app.router.lifespan_context(test_app):
            yield ac
    settings.MCP_ENABLED = original_mcp

