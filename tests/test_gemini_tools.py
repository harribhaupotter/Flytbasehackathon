import json
import pytest
import httpx
from app.providers.gemini import GeminiProvider, _clean_schema_for_gemini
from app.schemas import InternalMessage, ToolCall


def test_clean_schema_for_gemini():
    """Verify _clean_schema_for_gemini strips unsupported keys and formats types."""
    raw_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "SearchQuery",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "query": {
                "type": "string",
                "title": "Query",
                "default": "default query",
                "description": "Search term",
            },
            "limit": {
                "type": "integer",
                "default": 10,
            },
            "tags": {
                "type": "array",
                "items": {
                    "type": "string",
                    "title": "TagItem",
                },
            },
        },
        "required": ["query"],
        "$defs": {"something": {}},
    }

    cleaned = _clean_schema_for_gemini(raw_schema)

    # Top level stripped
    assert "$schema" not in cleaned
    assert "title" not in cleaned
    assert "$defs" not in cleaned
    assert "additionalProperties" not in cleaned
    assert cleaned["type"] == "OBJECT"
    assert cleaned["required"] == ["query"]

    # Properties cleaned
    props = cleaned["properties"]
    assert "query" in props
    assert props["query"]["type"] == "STRING"
    assert "title" not in props["query"]
    assert "default" not in props["query"]
    assert props["query"]["description"] == "Search term"

    assert props["limit"]["type"] == "INTEGER"
    assert "default" not in props["limit"]

    # Nested items cleaned
    assert props["tags"]["type"] == "ARRAY"
    assert props["tags"]["items"]["type"] == "STRING"
    assert "title" not in props["tags"]["items"]


@pytest.mark.asyncio
async def test_gemini_native_tool_formatting():
    """Verify native tool definitions, functionCall parts, and functionResponse parts."""
    provider = GeminiProvider(
        api_key="fake-key",
        tool_call_mode="native",
    )

    tools = [
        {
            "name": "builtin__fetch_url",
            "description": "Fetch a URL",
            "input_schema": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
                "additionalProperties": False,
            },
        }
    ]

    messages = [
        InternalMessage(role="user", content="Fetch example.com"),
        InternalMessage(
            role="assistant",
            content="",
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="builtin__fetch_url",
                    arguments={"url": "https://example.com"},
                )
            ],
        ),
        InternalMessage(
            role="tool",
            name="builtin__fetch_url",
            tool_call_id="call_1",
            content="Example Domain content",
        ),
    ]

    payload = provider._format_payload(
        messages=messages,
        temperature=0.7,
        max_output_tokens=1000,
        system_prompt="Assistant prompt",
        tools=tools,
    )

    # 1. Check tools declarations
    assert "tools" in payload
    assert len(payload["tools"]) == 1
    decls = payload["tools"][0]["functionDeclarations"]
    assert len(decls) == 1
    assert decls[0]["name"] == "builtin__fetch_url"
    assert decls[0]["parameters"]["type"] == "OBJECT"
    assert "additionalProperties" not in decls[0]["parameters"]

    # 2. Check assistant turn has functionCall
    contents = payload["contents"]
    assert len(contents) == 3

    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"
    assert "functionCall" in contents[1]["parts"][0]
    assert contents[1]["parts"][0]["functionCall"]["name"] == "builtin__fetch_url"
    assert contents[1]["parts"][0]["functionCall"]["args"] == {"url": "https://example.com"}

    # 3. Check tool turn has functionResponse in user role
    assert contents[2]["role"] == "user"
    assert "functionResponse" in contents[2]["parts"][0]
    assert contents[2]["parts"][0]["functionResponse"]["name"] == "builtin__fetch_url"
    assert contents[2]["parts"][0]["functionResponse"]["response"]["output"] == "Example Domain content"

    await provider.close()


@pytest.mark.asyncio
async def test_gemini_prompted_tool_formatting():
    """Verify prompted mode appends tool signatures to system instructions and does not set payload['tools']."""
    provider = GeminiProvider(
        api_key="fake-key",
        tool_call_mode="prompted",
        system_prompt_mode="prepend",
    )

    tools = [
        {
            "name": "builtin__read_query",
            "description": "Run read-only SQL query",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        }
    ]

    messages = [
        InternalMessage(role="user", content="Show users table"),
    ]

    payload = provider._format_payload(
        messages=messages,
        temperature=0.5,
        max_output_tokens=500,
        system_prompt="Base system instruction.",
        tools=tools,
    )

    # tools should NOT be in payload
    assert "tools" not in payload

    # System instruction prepended to first user turn should include tool details
    first_part_text = payload["contents"][0]["parts"][0]["text"]
    assert "builtin__read_query" in first_part_text
    assert "To call a tool, respond with ONLY a valid JSON object" in first_part_text
    assert "Show users table" in first_part_text

    await provider.close()


@pytest.mark.asyncio
async def test_gemini_prompted_streaming_first_char_decision():
    """Verify prompted mode buffers JSON tool call when starting with '{' or code fences, but streams immediately for text."""
    provider = GeminiProvider(
        api_key="fake-key",
        tool_call_mode="prompted",
    )

    tools = [
        {
            "name": "calc",
            "description": "Calculator",
            "input_schema": {},
        }
    ]

    # Subtest 1: Model outputs JSON tool call
    sse_lines_tool = [
        'data: {"candidates": [{"content": {"parts": [{"text": "{\\"tool\\": \\"calc\\", "}]}}]}\n\n',
        'data: {"candidates": [{"content": {"parts": [{"text": "\\"arguments\\": {\\"expr\\": \\"2+2\\"}}"}]}}]}\n\n',
        'data: [DONE]\n\n',
    ]

    class MockStreamResponse:
        def __init__(self, lines):
            self.lines = lines
            self.status_code = 200

        def raise_for_status(self):
            pass

        async def aiter_lines(self):
            for line in self.lines:
                yield line

        async def aclose(self):
            pass

    # Patch client.send
    async def mock_send(req, stream=True):
        return MockStreamResponse(sse_lines_tool)

    provider.client.send = mock_send

    chunks = []
    async for chunk in provider.stream_chat(
        messages=[InternalMessage(role="user", content="Calculate 2+2")],
        model="gemma-4-26b-a4b-it",
        temperature=0.0,
        max_output_tokens=100,
        system_prompt="",
        tools=tools,
    ):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert chunks[0].tool_calls is not None
    assert len(chunks[0].tool_calls) == 1
    assert chunks[0].tool_calls[0].name == "calc"
    assert chunks[0].tool_calls[0].arguments == {"expr": "2+2"}

    # Subtest 2: Model outputs plain text answer (first non-whitespace char is not '{')
    sse_lines_text = [
        'data: {"candidates": [{"content": {"parts": [{"text": "  Hello! "}]}}]}\n\n',
        'data: {"candidates": [{"content": {"parts": [{"text": "How can I "}]}}]}\n\n',
        'data: {"candidates": [{"content": {"parts": [{"text": "assist you?"}]}}]}\n\n',
        'data: [DONE]\n\n',
    ]

    async def mock_send_text(req, stream=True):
        return MockStreamResponse(sse_lines_text)

    provider.client.send = mock_send_text

    text_chunks = []
    async for chunk in provider.stream_chat(
        messages=[InternalMessage(role="user", content="Hi")],
        model="gemma-4-26b-a4b-it",
        temperature=0.0,
        max_output_tokens=100,
        system_prompt="",
        tools=tools,
    ):
        text_chunks.append(chunk)

    # Should stream immediately chunk by chunk
    assert len(text_chunks) == 3
    assert text_chunks[0].token == "  Hello! "
    assert text_chunks[1].token == "How can I "
    assert text_chunks[2].token == "assist you?"

    await provider.close()


@pytest.mark.asyncio
async def test_gemini_native_streaming_function_call_and_thinking():
    """Verify native functionCall part and thought parts in SSE stream."""
    provider = GeminiProvider(
        api_key="fake-key",
        tool_call_mode="native",
    )

    sse_lines = [
        'data: {"candidates": [{"content": {"parts": [{"thought": true, "text": "Thinking about the weather..."}]}}]}\n\n',
        'data: {"candidates": [{"content": {"parts": [{"functionCall": {"name": "get_weather", "args": {"location": "Tokyo"}}}]}}]}\n\n',
        'data: [DONE]\n\n',
    ]

    class MockStreamResponse:
        def __init__(self, lines):
            self.lines = lines
            self.status_code = 200

        def raise_for_status(self):
            pass

        async def aiter_lines(self):
            for line in self.lines:
                yield line

        async def aclose(self):
            pass

    async def mock_send(req, stream=True):
        return MockStreamResponse(sse_lines)

    provider.client.send = mock_send

    chunks = []
    async for chunk in provider.stream_chat(
        messages=[InternalMessage(role="user", content="What's the weather in Tokyo?")],
        model="gemma-4-26b-a4b-it",
        temperature=0.0,
        max_output_tokens=100,
        system_prompt="",
        tools=[{"name": "get_weather", "input_schema": {}}],
    ):
        chunks.append(chunk)

    assert len(chunks) == 2
    # First chunk is thinking
    assert chunks[0].is_thinking is True
    assert chunks[0].thought == "Thinking about the weather..."

    # Second chunk is function call
    assert chunks[1].tool_calls is not None
    assert chunks[1].tool_calls[0].name == "get_weather"
    assert chunks[1].tool_calls[0].arguments == {"location": "Tokyo"}

    await provider.close()
