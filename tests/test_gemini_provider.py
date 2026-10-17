import json
import pytest
import httpx
from app.providers.gemini import GeminiProvider
from app.schemas import ChatMessage, ImageAttachment


@pytest.mark.asyncio
async def test_gemini_role_mapping_and_prepend_system_prompt():
    """Verify GeminiProvider maps assistant to model and prepends system prompt."""
    provider = GeminiProvider(
        api_key="fake-key",
        default_model="gemma-4-26b-a4b-it",
        system_prompt_mode="prepend",
        thinking_level="minimal",
    )

    messages = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi there!"),
        ChatMessage(role="user", content="How are you?"),
    ]

    payload = provider._format_payload(
        messages=messages,
        temperature=0.7,
        max_output_tokens=1000,
        system_prompt="Be concise",
    )

    contents = payload["contents"]
    assert len(contents) == 3

    # Check first user message has prepended system prompt
    assert contents[0]["role"] == "user"
    assert "System Instructions:\nBe concise\n\nHello" in contents[0]["parts"][0]["text"]

    # Check assistant role mapped to model
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][0]["text"] == "Hi there!"

    # Check third user message does not have prepended prompt again
    assert contents[2]["role"] == "user"
    assert contents[2]["parts"][0]["text"] == "How are you?"

    # Check thinkingConfig
    assert payload["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "MINIMAL"

    await provider.close()


@pytest.mark.asyncio
async def test_gemini_native_system_prompt_mode():
    """Verify GeminiProvider sets systemInstruction when system_prompt_mode='native'."""
    provider = GeminiProvider(
        api_key="fake-key",
        default_model="gemma-4-26b-a4b-it",
        system_prompt_mode="native",
        thinking_level="high",
    )

    messages = [ChatMessage(role="user", content="Hello")]
    payload = provider._format_payload(
        messages=messages,
        temperature=0.5,
        max_output_tokens=500,
        system_prompt="Act as an expert mathematician",
    )

    assert "systemInstruction" in payload
    assert payload["systemInstruction"]["parts"][0]["text"] == "Act as an expert mathematician"
    assert payload["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "HIGH"

    await provider.close()


@pytest.mark.asyncio
async def test_gemini_multimodal_image_attachment():
    """Verify image attachments are correctly mapped to inlineData parts."""
    provider = GeminiProvider(
        api_key="fake-key",
        default_model="gemma-4-26b-a4b-it",
    )

    img = ImageAttachment(mime="image/png", data_b64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    messages = [
        ChatMessage(role="user", content="Describe this image", images=[img])
    ]

    payload = provider._format_payload(
        messages=messages,
        temperature=0.7,
        max_output_tokens=1000,
        system_prompt="",
    )

    parts = payload["contents"][0]["parts"]
    assert len(parts) == 2
    assert parts[0]["text"] == "Describe this image"
    assert "inlineData" in parts[1]
    assert parts[1]["inlineData"]["mimeType"] == "image/png"
    assert parts[1]["inlineData"]["data"] == img.data_b64

    await provider.close()
