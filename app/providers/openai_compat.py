import json
import asyncio
import logging
from typing import AsyncGenerator, List, Any, Dict, Optional
import httpx

from app.providers.base import LLMProvider, LLMChunk
from app.schemas import InternalMessage, ChatMessage
from app.errors import UpstreamProviderError

logger = logging.getLogger("aether.provider.openai_compat")


class OpenAICompatProvider(LLMProvider):
    """
    Client for OpenAI-compatible local endpoints (e.g. Ollama, vLLM, LocalAI)
    serving Gemma models. All configuration uses LLM_* parameters.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: Optional[str] = "ollama",
        default_model: str = "gemma-4-26b-a4b-it",
        timeout_seconds: float = 45.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "local"
        self.default_model = default_model
        self.timeout = httpx.Timeout(timeout_seconds, connect=10.0)
        self.client = httpx.AsyncClient(timeout=self.timeout)

    def _format_payload(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float,
        max_output_tokens: int,
        system_prompt: str,
        stream: bool,
    ) -> Dict[str, Any]:
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            formatted_messages.append({"role": msg.role, "content": msg.content})

        target_model = model if model and model != "mock" else self.default_model
        return {
            "model": target_model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "stream": stream,
        }

    async def stream_chat(
        self,
        messages: List[InternalMessage],
        model: str,
        temperature: float,
        max_output_tokens: int,
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._format_payload(
            messages, model, temperature, max_output_tokens, system_prompt, stream=True
        )

        for attempt in range(1, 3):
            try:
                req = self.client.build_request("POST", url, headers=headers, json=payload)
                resp = await self.client.send(req, stream=True)
                if resp.status_code == 429 or resp.status_code >= 500:
                    await resp.aclose()
                    if attempt == 2:
                        raise UpstreamProviderError(
                            status_code=resp.status_code,
                            code="upstream_rate_limit" if resp.status_code == 429 else "upstream_unavailable",
                            message="Upstream local provider error.",
                        )
                    await asyncio.sleep(1.0)
                    continue

                resp.raise_for_status()

                try:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:].strip()
                        if not raw or raw == "[DONE]":
                            continue

                        try:
                            chunk_data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        choices = chunk_data.get("choices", [])
                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield LLMChunk(token=content)
                    return
                finally:
                    await resp.aclose()

            except (httpx.TimeoutException, httpx.NetworkError) as err:
                if attempt == 2:
                    raise UpstreamProviderError(
                        status_code=504,
                        code="upstream_timeout",
                        message="Upstream local provider timed out.",
                    )
                await asyncio.sleep(1.0)

    async def complete_chat(
        self,
        messages: List[InternalMessage],
        model: str,
        temperature: float,
        max_output_tokens: int,
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._format_payload(
            messages, model, temperature, max_output_tokens, system_prompt, stream=False
        )

        for attempt in range(1, 3):
            try:
                resp = await self.client.post(url, headers=headers, json=payload)
                if resp.status_code == 429 or resp.status_code >= 500:
                    if attempt == 2:
                        raise UpstreamProviderError(
                            status_code=resp.status_code,
                            code="upstream_rate_limit" if resp.status_code == 429 else "upstream_unavailable",
                            message="Upstream local provider error.",
                        )
                    await asyncio.sleep(1.0)
                    continue

                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""
            except (httpx.TimeoutException, httpx.NetworkError) as err:
                if attempt == 2:
                    raise UpstreamProviderError(
                        status_code=504,
                        code="upstream_timeout",
                        message="Upstream local provider timed out.",
                    )
                await asyncio.sleep(1.0)
        return ""

    async def close(self) -> None:
        await self.client.aclose()
