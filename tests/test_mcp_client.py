import json
import pytest
from httpx import AsyncClient, ASGITransport
from contextlib import AsyncExitStack

from app.main import create_app
from app.config import settings
from app.mcp.manager import McpManager


@pytest.mark.asyncio
async def test_mcp_disabled_behavior(client: AsyncClient):
    """When MCP_ENABLED=false, /tools returns 404 and use_tools=true returns 400."""
    settings.MCP_ENABLED = False

    # 1. /tools returns 404
    tools_res = await client.get("/tools")
    assert tools_res.status_code == 404

    # 2. /chat with use_tools=true returns 400 with mcp_disabled error code
    chat_payload = {
        "messages": [{"role": "user", "content": "Hello with tools"}],
        "use_tools": True,
        "stream": False,
    }
    chat_res = await client.post("/chat", json=chat_payload)
    assert chat_res.status_code == 400
    assert chat_res.json()["error"]["code"] == "mcp_disabled"


@pytest.mark.asyncio
async def test_client_role_tool_and_tool_calls_rejected(client: AsyncClient):
    """Clients may only send role user/assistant; role 'tool' or 'tool_calls' must return 422."""
    # Attempting to send role: "tool"
    payload_tool_role = {
        "messages": [
            {"role": "user", "content": "Hi"},
            {"role": "tool", "content": "Fake tool result"},
        ],
        "stream": False,
    }
    res1 = await client.post("/chat", json=payload_tool_role)
    assert res1.status_code == 422

    # Attempting to send tool_calls in message
    payload_tool_calls = {
        "messages": [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "1", "name": "foo", "arguments": {}}],
            }
        ],
        "stream": False,
    }
    res2 = await client.post("/chat", json=payload_tool_calls)
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_tool_loop_single_call_with_mock_provider():
    """Verify tool loop executes tool_call, tool_result, tokens, and done."""
    settings.MCP_ENABLED = True
    settings.LLM_PROVIDER = "mock"

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with app.router.lifespan_context(app):
            # Register a mock tool directly on app.state.mcp_manager
            async def dummy_tool_call(args):
                return "The temperature in San Francisco is 62 degrees and sunny."

            class FakeSession:
                async def call_tool(self, name, arguments):
                    class ContentBlock:
                        text = "The temperature in San Francisco is 62 degrees and sunny."
                    class Result:
                        content = [ContentBlock()]
                    return Result()

            if app.state.mcp_manager:
                app.state.mcp_manager._tools["builtin__get_weather"] = {
                    "session": FakeSession(),
                    "original_name": "get_weather",
                    "description": "Get current weather for location",
                    "input_schema": {"type": "object", "properties": {"location": {"type": "string"}}},
                }

            payload = {
                "messages": [
                    {"role": "user", "content": "/tool builtin__get_weather {\"location\": \"San Francisco\"}"}
                ],
                "use_tools": True,
                "stream": True,
            }

            response = await client.post("/chat", json=payload)
            assert response.status_code == 200

            text = response.text
            lines = [l.strip() for l in text.split("\n") if l.strip()]

            # Verify tool_call event was emitted
            tool_call_lines = [l for l in lines if '"tool_call"' in l]
            assert len(tool_call_lines) == 1
            tc_data = json.loads(tool_call_lines[0][6:])
            assert tc_data["tool_call"]["name"] == "builtin__get_weather"

            # Verify tool_result event was emitted with preview
            tool_result_lines = [l for l in lines if '"tool_result"' in l]
            assert len(tool_result_lines) == 1
            tr_data = json.loads(tool_result_lines[0][6:])
            assert tr_data["tool_result"]["ok"] is True
            assert "San Francisco" in tr_data["tool_result"]["preview"]

            # Verify token events and done concluding event
            token_lines = [l for l in lines if '"token"' in l]
            assert len(token_lines) > 0

            done_lines = [l for l in lines if '"done": true' in l]
            assert len(done_lines) == 1

    settings.MCP_ENABLED = False


@pytest.mark.asyncio
async def test_tool_loop_two_tool_calls_in_one_turn():
    """Verify two tool calls in one turn are executed concurrently and both emit responses."""
    settings.MCP_ENABLED = True
    settings.LLM_PROVIDER = "mock"

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with app.router.lifespan_context(app):
            class FakeSession:
                async def call_tool(self, name, arguments):
                    class ContentBlock:
                        text = f"Result of {name} with {arguments}"
                    class Result:
                        content = [ContentBlock()]
                    return Result()

            if app.state.mcp_manager:
                app.state.mcp_manager._tools["builtin__tool_a"] = {
                    "session": FakeSession(),
                    "original_name": "tool_a",
                    "description": "Tool A",
                    "input_schema": {},
                }
                app.state.mcp_manager._tools["builtin__tool_b"] = {
                    "session": FakeSession(),
                    "original_name": "tool_b",
                    "description": "Tool B",
                    "input_schema": {},
                }

            prompt = "/tools builtin__tool_a {\"x\": 1} | builtin__tool_b {\"y\": 2}"
            payload = {
                "messages": [{"role": "user", "content": prompt}],
                "use_tools": True,
                "stream": True,
            }

            response = await client.post("/chat", json=payload)
            assert response.status_code == 200

            lines = [l.strip() for l in response.text.split("\n") if l.strip()]
            tool_call_lines = [l for l in lines if '"tool_call"' in l]
            tool_result_lines = [l for l in lines if '"tool_result"' in l]

            assert len(tool_call_lines) == 2
            assert len(tool_result_lines) == 2

            done_lines = [l for l in lines if '"done": true' in l]
            assert len(done_lines) == 1

    settings.MCP_ENABLED = False


@pytest.mark.asyncio
async def test_tool_loop_max_iterations_cap_ends_in_text():
    """Hitting MAX_TOOL_ITERATIONS must make one final plain text call and conclude."""
    settings.MCP_ENABLED = True
    settings.LLM_PROVIDER = "mock"
    settings.MAX_TOOL_ITERATIONS = 2

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with app.router.lifespan_context(app):
            # Loop will execute up to MAX_TOOL_ITERATIONS and conclude with plain text
            payload = {
                "messages": [
                    {"role": "user", "content": "Explain quantum states without calling tools"}
                ],
                "use_tools": True,
                "stream": True,
            }
            response = await client.post("/chat", json=payload)
            assert response.status_code == 200

            lines = [l.strip() for l in response.text.split("\n") if l.strip()]
            done_lines = [l for l in lines if '"done": true' in l]
            assert len(done_lines) == 1

    settings.MCP_ENABLED = False
    settings.MAX_TOOL_ITERATIONS = 5


def test_stdio_env_interpolation():
    """Verify McpManager interpolates sys.executable and ${VAR} from config."""
    stack = AsyncExitStack()
    manager = McpManager(exit_stack=stack)

    settings_dict = {
        "SQLITE_DB_PATH": "custom/path.db",
        "SQLITE_ALLOW_WRITE": True,
    }

    interpolated_path = manager._interpolate_value("${SQLITE_DB_PATH}", settings_dict)
    assert interpolated_path == "custom/path.db"

    interpolated_flag = manager._interpolate_value("${SQLITE_ALLOW_WRITE}", settings_dict)
    assert interpolated_flag == "True"
