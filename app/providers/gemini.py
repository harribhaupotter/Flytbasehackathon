import json
import uuid
import re
import asyncio
import logging
from typing import AsyncGenerator, List, Any, Dict, Optional
import httpx

from app.providers.base import LLMProvider, LLMChunk
from app.schemas import InternalMessage, ToolCall
from app.errors import UpstreamProviderError
from app.config import settings

logger = logging.getLogger("aether.provider.gemini")

def _redact_key(text: str, key: Optional[str]) -> str:
    """Replaces API key in strings to prevent leakage in logs or exceptions."""
    if key and len(key) >= 4 and key in text:
        return text.replace(key, "[REDACTED]")
    return text


def _clean_schema_for_gemini(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively strips keywords unsupported by the Gemini API (e.g. $schema, additionalProperties)."""
    if not isinstance(schema, dict):
        return schema

    cleaned: Dict[str, Any] = {}
    UNSUPPORTED_KEYS = {"$schema", "additionalProperties", "$defs", "title", "$ref", "default"}

    for k, v in schema.items():
        if k in UNSUPPORTED_KEYS:
            continue
        if k == "type" and isinstance(v, str):
            cleaned["type"] = v.upper() if v.lower() in ("object", "string", "number", "integer", "boolean", "array") else v
        elif k == "properties" and isinstance(v, dict):
            cleaned["properties"] = {
                prop_name: _clean_schema_for_gemini(prop_schema)
                for prop_name, prop_schema in v.items()
            }
        elif k == "items" and isinstance(v, dict):
            cleaned["items"] = _clean_schema_for_gemini(v)
        elif isinstance(v, dict):
            cleaned[k] = _clean_schema_for_gemini(v)
        else:
            cleaned[k] = v

    return cleaned


class GeminiProvider(LLMProvider):
    """Native client for Gemini API powering Gemma 4 models with MCP function calling."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str,
        default_model: str = "gemma-4-26b-a4b-it",
        system_prompt_mode: str = "prepend",
        thinking_level: str = "minimal",
        tool_call_mode: str = "native",
        timeout_seconds: float = 45.0,
    ):
        self.api_key = api_key
        self.default_model = default_model
        self.system_prompt_mode = system_prompt_mode
        self.thinking_level = thinking_level
        self.tool_call_mode = tool_call_mode
        self.timeout = httpx.Timeout(timeout_seconds, connect=10.0)
        self.client = httpx.AsyncClient(timeout=self.timeout)

    def _format_payload(
        self,
        messages: List[InternalMessage],
        temperature: float,
        max_output_tokens: int,
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        target_model: str = "",
    ) -> Dict[str, Any]:
        contents = []

        # If prompted mode is active and tools are supplied, describe them in the system prompt
        effective_system_prompt = system_prompt
        if tools and self.tool_call_mode == "prompted":
            tool_signatures = "\n".join(
                f"- {t['name']}: {t.get('description', '')} | arguments: {json.dumps(t.get('input_schema', {}))}"
                for t in tools
            )
            effective_system_prompt += (
                f"\n\nYou have access to external tools:\n{tool_signatures}\n\n"
                "To call a tool, respond with ONLY a valid JSON object in this format:\n"
                '{"tool": "<name>", "arguments": {<arguments>}}\n'
                "If you do not need to call a tool, respond normally."
            )

        for idx, msg in enumerate(messages):
            parts: List[Dict[str, Any]] = []

            if msg.role == "user":
                role = "user"
                content_text = msg.content
                if idx == 0 and self.system_prompt_mode == "prepend" and effective_system_prompt:
                    content_text = f"System Instructions:\n{effective_system_prompt}\n\n{content_text}"

                if content_text:
                    parts.append({"text": content_text})

                if msg.images:
                    for img in msg.images:
                        parts.append(
                            {
                                "inlineData": {
                                    "mimeType": img.mime,
                                    "data": img.data_b64,
                                }
                            }
                        )

            elif msg.role == "assistant":
                role = "model"
                tool_calls = getattr(msg, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        part_dict = {"functionCall": {"name": tc.name, "args": tc.arguments}}
                        sig = getattr(tc, "thought_signature", None)
                        if sig:
                            part_dict["thoughtSignature"] = sig
                        parts.append(part_dict)
                if msg.content:
                    parts.append({"text": msg.content})

            elif msg.role == "tool":
                # Gemini expects function response parts from user turn
                role = "user"
                tool_name = getattr(msg, "name", None) or "tool"
                parts.append(
                    {
                        "functionResponse": {
                            "name": tool_name,
                            "response": {"output": msg.content},
                        }
                    }
                )
            else:
                role = "user"
                if msg.content:
                    parts.append({"text": msg.content})

            if parts:
                if contents and contents[-1]["role"] == role:
                    contents[-1]["parts"].extend(parts)
                else:
                    contents.append({"role": role, "parts": parts})

        generation_config: Dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        }
        chosen_model = target_model or self.default_model
        if "gemma" in chosen_model.lower():
            generation_config["thinkingConfig"] = {
                "thinkingLevel": "MINIMAL" if self.thinking_level == "minimal" else "HIGH"
            }

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }

        # Native system prompt mode
        # TODO: Verify native systemInstruction support for Gemma 4 models.
        if self.system_prompt_mode == "native" and effective_system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": effective_system_prompt}]
            }

        # Pass native function declarations if native tool mode
        if tools and self.tool_call_mode == "native":
            declarations = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": _clean_schema_for_gemini(t.get("input_schema", {})),
                }
                for t in tools
            ]
            payload["tools"] = [{"functionDeclarations": declarations}]

        return payload

    async def _execute_with_retry(self, request_fn):
        """Retries once with backoff on 429, 5xx, or network timeouts."""
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                return await request_fn()
            except (httpx.TimeoutException, httpx.NetworkError) as err:
                if attempt == max_attempts:
                    logger.error(f"Gemini upstream timeout/network error after retry: {err}")
                    raise UpstreamProviderError(
                        status_code=504,
                        code="upstream_timeout",
                        message="Upstream model provider timed out.",
                    )
                await asyncio.sleep(1.0)
            except httpx.HTTPStatusError as err:
                status = err.response.status_code
                if status == 429 or status >= 500:
                    if attempt == max_attempts:
                        retry_after = err.response.headers.get("Retry-After")
                        retry_sec = int(retry_after) if retry_after and retry_after.isdigit() else 5
                        logger.error(f"Gemini upstream HTTP {status} error after retry.")
                        raise UpstreamProviderError(
                            status_code=429 if status == 429 else 503,
                            code="upstream_rate_limit" if status == 429 else "upstream_unavailable",
                            message="Upstream model provider is currently overloaded.",
                            retry_after=retry_sec,
                        )
                    await asyncio.sleep(1.0)
                else:
                    redacted = _redact_key(err.response.text, self.api_key)
                    logger.error(f"Gemini upstream client error: {redacted}")
                    raise UpstreamProviderError(
                        status_code=502,
                        code="upstream_error",
                        message=f"Upstream provider error: {redacted[:200]}",
                    )

    async def stream_chat(
        self,
        messages: List[InternalMessage],
        model: str,
        temperature: float,
        max_output_tokens: int,
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        target_model = model if model and model != "mock" else self.default_model
        url = f"{self.BASE_URL}/models/{target_model}:streamGenerateContent?alt=sse"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = self._format_payload(messages, temperature, max_output_tokens, system_prompt, tools=tools, target_model=target_model)

        max_attempts = 4
        for attempt in range(1, max_attempts + 1):
            try:
                req = self.client.build_request("POST", url, headers=headers, json=payload)
                resp = await self.client.send(req, stream=True)
                if resp.status_code == 429 or resp.status_code >= 500:
                    err_body = await resp.aread()
                    await resp.aclose()
                    redacted = _redact_key(err_body.decode(errors="replace"), self.api_key)
                    retry_after = resp.headers.get("Retry-After")
                    retry_sec = float(retry_after) if retry_after and retry_after.isdigit() else max(2.0, 1.5 * attempt)
                    if resp.status_code == 429:
                        cascade = [
                            "gemini-3.5-flash-lite",
                            "gemini-flash-lite-latest",
                            "gemini-3.1-flash-lite",
                            "gemini-3.5-flash",
                            "gemini-3.6-flash",
                        ]
                        next_models = [m for m in cascade if m != target_model]
                        next_model = next_models[(attempt - 1) % len(next_models)]
                        logger.warning(f"Model {target_model} rate-limited (HTTP 429). Falling over immediately to {next_model} (attempt {attempt}/{max_attempts})...")
                        target_model = next_model
                        url = f"{self.BASE_URL}/models/{target_model}:streamGenerateContent?alt=sse"
                        payload = self._format_payload(messages, temperature, max_output_tokens, system_prompt, tools=tools, target_model=target_model)
                        continue

                    if attempt == max_attempts:
                        if settings.GROQ_API_KEY:
                            logger.warning("Gemini API rate limited after retries. Automatically failing over to Groq API...")
                            try:
                                from app.providers.openai_compat import OpenAICompatProvider
                                groq_p = OpenAICompatProvider(
                                    base_url=settings.GROQ_BASE_URL,
                                    api_key=settings.GROQ_API_KEY,
                                    default_model=settings.GROQ_MODEL,
                                    timeout_seconds=self.timeout.read or 45.0,
                                )
                                async for g_chunk in groq_p.stream_chat(
                                    messages=messages,
                                    model=settings.GROQ_MODEL,
                                    temperature=temperature,
                                    max_output_tokens=max_output_tokens,
                                    system_prompt=system_prompt,
                                    tools=tools,
                                ):
                                    yield g_chunk
                                return
                            except Exception as groq_err:
                                logger.error(f"Groq API fallback also failed: {groq_err}")

                        logger.error(f"Gemini upstream error {resp.status_code} after {max_attempts} attempts: {redacted}")
                        raise UpstreamProviderError(
                            status_code=429 if resp.status_code == 429 else 503,
                            code="upstream_rate_limit" if resp.status_code == 429 else "upstream_unavailable",
                            message="Upstream model provider is currently overloaded or rate limited.",
                            retry_after=int(retry_sec),
                        )
                    logger.warning(f"Gemini {resp.status_code} on attempt {attempt}/{max_attempts}. Backing off for {retry_sec:.1f}s. Detail: {redacted[:120]}")
                    await asyncio.sleep(retry_sec)
                    continue

                if resp.status_code >= 400:
                    err_body = await resp.aread()
                    await resp.aclose()
                    redacted = _redact_key(err_body.decode(errors="replace"), self.api_key)
                    logger.error(f"Gemini upstream stream error {resp.status_code}: {redacted}")
                    raise UpstreamProviderError(
                        status_code=502 if resp.status_code != 429 else 429,
                        code="upstream_rate_limit" if resp.status_code == 429 else "upstream_error",
                        message=f"Upstream provider error: {redacted[:200]}",
                    )

                resp.raise_for_status()

                # In prompted mode, buffer if the first non-whitespace character is "{"
                is_prompted_mode = bool(tools and self.tool_call_mode == "prompted")
                checked_first_char = False
                is_tool_call_stream = False
                buffered_chunks: List[str] = []

                try:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw_data = line[6:].strip()
                        if not raw_data or raw_data == "[DONE]":
                            continue

                        try:
                            data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            continue

                        candidates = data.get("candidates", [])
                        if not candidates:
                            continue

                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            # 1. Native function call handling
                            if "functionCall" in part:
                                fc = part["functionCall"]
                                sig = part.get("thoughtSignature") or fc.get("thoughtSignature")
                                yield LLMChunk(
                                    tool_calls=[
                                        ToolCall(
                                            id=fc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                                            name=fc.get("name", ""),
                                            arguments=fc.get("args", {}),
                                            thought_signature=sig,
                                        )
                                    ]
                                )
                                continue

                            # 2. Thinking token handling
                            if part.get("thought") is True:
                                thought_text = part.get("text", "")
                                yield LLMChunk(is_thinking=True, thought=thought_text)
                                continue

                            text = part.get("text", "")
                            if not text:
                                continue

                            # 3. Prompted mode tool call heuristic
                            if is_prompted_mode and not checked_first_char:
                                stripped = text.lstrip()
                                if stripped:
                                    checked_first_char = True
                                    if stripped.startswith("{") or stripped.startswith("```"):
                                        is_tool_call_stream = True
                                        buffered_chunks.append(text)
                                        continue
                                    else:
                                        # Plain text stream -> yield immediately
                                        yield LLMChunk(token=text)
                                        continue
                                else:
                                    buffered_chunks.append(text)
                                    continue

                            if is_prompted_mode and is_tool_call_stream:
                                buffered_chunks.append(text)
                                continue

                            # Normal plain text token
                            yield LLMChunk(token=text)

                    # If prompted mode buffered a potential tool call JSON
                    if is_prompted_mode and is_tool_call_stream and buffered_chunks:
                        full_buffered = "".join(buffered_chunks).strip()
                        clean_json = re.sub(
                            r"^```(?:json)?\s*|\s*```$",
                            "",
                            full_buffered,
                            flags=re.MULTILINE,
                        ).strip()
                        try:
                            parsed_tool = json.loads(clean_json)
                            if "tool" in parsed_tool:
                                yield LLMChunk(
                                    tool_calls=[
                                        ToolCall(
                                            id=f"call_{uuid.uuid4().hex[:8]}",
                                            name=parsed_tool["tool"],
                                            arguments=parsed_tool.get("arguments", {}),
                                        )
                                    ]
                                )
                                return
                        except Exception:
                            pass

                        # If JSON parse failed or was plain text after all, flush tokens
                        for chunk in buffered_chunks:
                            yield LLMChunk(token=chunk)

                    return
                finally:
                    await resp.aclose()

            except (httpx.TimeoutException, httpx.NetworkError) as err:
                if attempt == 2:
                    raise UpstreamProviderError(
                        status_code=504,
                        code="upstream_timeout",
                        message="Upstream model provider timed out.",
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
        target_model = model if model and model != "mock" else self.default_model
        url = f"{self.BASE_URL}/models/{target_model}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = self._format_payload(messages, temperature, max_output_tokens, system_prompt, tools=tools, target_model=target_model)

        async def _call():
            resp = await self.client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            answer_parts = [p.get("text", "") for p in parts if not p.get("thought")]
            return "".join(answer_parts)

        return await self._execute_with_retry(_call)

    async def close(self) -> None:
        await self.client.aclose()
