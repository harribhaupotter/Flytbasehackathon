import json
import uuid
import asyncio
import logging
from typing import AsyncGenerator, List
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.config import settings
from app.deps import verify_auth, get_llm_provider
from app.schemas import ChatRequest, ChatResponse, InternalMessage, ToolCall
from app.providers.base import LLMProvider
from app.errors import AppException

logger = logging.getLogger("aether.router.chat")

router = APIRouter(tags=["Chat"])


@router.post("/chat")
async def chat_endpoint(
    request: Request,
    payload: ChatRequest,
    _auth: bool = Depends(verify_auth),
    provider: LLMProvider = Depends(get_llm_provider),
):
    """
    Core chat endpoint supporting real-time Server-Sent Events (SSE) streaming,
    synchronous JSON response, and iterative MCP tool execution loops.
    """
    if payload.use_tools and not settings.MCP_ENABLED:
        raise AppException(
            status_code=400,
            code="mcp_disabled",
            message="MCP is disabled on this server. Set MCP_ENABLED=true in configuration to enable tools.",
        )

    target_model = payload.model or settings.GEMMA_MODEL
    chat_id = f"chat_{uuid.uuid4().hex[:12]}"

    current_user_id = payload.user_id or "U-201"
    effective_system_prompt = (
        f"{settings.SYSTEM_PROMPT}\n\n"
        f"CURRENT ACTIVE OPERATOR: User ID: {current_user_id}. "
        "Keep user private memory strictly tied to this operator. Any feedback, overrides, or rules recorded must be attributed to this user_id."
    )
    if payload.use_tools:
        effective_system_prompt += (
            "\n\nNote: Tool output is verified data from the database and documents; "
            "synthesize your findings clearly and cite all source record IDs."
        )

    # Convert incoming ClientMessages to InternalMessages
    internal_messages: List[InternalMessage] = [
        InternalMessage(
            role=m.role,
            content=m.content,
            images=m.images,
        )
        for m in payload.messages
    ]

    mcp_manager = getattr(request.app.state, "mcp_manager", None) if payload.use_tools else None
    available_tools = mcp_manager.get_tools() if mcp_manager else None

    if payload.stream:
        async def sse_generator() -> AsyncGenerator[str, None]:
            try:
                iteration = 0
                while iteration <= settings.MAX_TOOL_ITERATIONS:
                    # Cancel in-flight iteration immediately if client disconnected
                    if await request.is_disconnected():
                        logger.info(f"Client disconnected; aborting generation for {chat_id}")
                        break

                    # At MAX_TOOL_ITERATIONS, make one final provider call with tools disabled to force a plain-text answer
                    force_text_conclusion = iteration == settings.MAX_TOOL_ITERATIONS
                    tools_to_pass = None if force_text_conclusion else available_tools

                    turn_tool_calls: List[ToolCall] = []
                    text_streamed = False

                    stream_iter = provider.stream_chat(
                        messages=internal_messages,
                        model=target_model,
                        temperature=payload.temperature or 0.7,
                        max_output_tokens=payload.max_output_tokens or settings.DEFAULT_MAX_OUTPUT_TOKENS,
                        system_prompt=effective_system_prompt,
                        tools=tools_to_pass,
                    )

                    async for chunk in stream_iter:
                        if await request.is_disconnected():
                            logger.info(f"Client disconnected; aborting stream for {chat_id}")
                            break

                        if chunk.tool_calls:
                            turn_tool_calls.extend(chunk.tool_calls)

                        if chunk.is_thinking and chunk.thought:
                            thinking_payload = json.dumps({"thought": chunk.thought})
                            yield f"event: thinking\ndata: {thinking_payload}\n\n"

                        if chunk.token:
                            text_streamed = True
                            token_payload = json.dumps({"token": chunk.token})
                            yield f"data: {token_payload}\n\n"

                    # Check client disconnection before executing tools
                    if await request.is_disconnected():
                        break

                    # If model requested tool calls, execute them concurrently
                    if turn_tool_calls and not force_text_conclusion:
                        # 1. Emit SSE tool_call events
                        for tc in turn_tool_calls:
                            tc_event = json.dumps(
                                {
                                    "tool_call": {
                                        "id": tc.id,
                                        "name": tc.name,
                                        "arguments": tc.arguments,
                                    }
                                }
                            )
                            yield f"data: {tc_event}\n\n"

                        # 2. Concurrently execute all tool calls via McpManager
                        if mcp_manager:
                            tasks = [
                                mcp_manager.call_tool(tc.name, tc.arguments)
                                for tc in turn_tool_calls
                            ]
                            results = await asyncio.gather(*tasks)
                        else:
                            results = [
                                f"Error: MCP manager is not available."
                                for _ in turn_tool_calls
                            ]

                        # Check client disconnection after tool execution
                        if await request.is_disconnected():
                            break

                        # 3. Emit SSE tool_result events with preview <= 300 chars
                        for tc, result_str in zip(turn_tool_calls, results):
                            preview = result_str[:300]
                            ok = not result_str.startswith("Error:")
                            tr_event = json.dumps(
                                {
                                    "tool_result": {
                                        "id": tc.id,
                                        "name": tc.name,
                                        "ok": ok,
                                        "preview": preview,
                                    }
                                }
                            )
                            yield f"data: {tr_event}\n\n"

                        # 4. Append assistant message with tool calls and tool result messages
                        internal_messages.append(
                            InternalMessage(
                                role="assistant",
                                content="",
                                tool_calls=turn_tool_calls,
                            )
                        )
                        for tc, result_str in zip(turn_tool_calls, results):
                            internal_messages.append(
                                InternalMessage(
                                    role="tool",
                                    content=result_str,
                                    tool_call_id=tc.id,
                                    name=tc.name,
                                )
                            )

                        # Increment iteration and continue loop with slight pacing delay
                        iteration += 1
                        await asyncio.sleep(0.5)
                        continue

                    # If no tool calls requested but no text streamed yet, force a synthesis turn
                    if not text_streamed:
                        prompt_msgs = internal_messages + [
                            InternalMessage(
                                role="user",
                                content="Based on the retrieved tool outputs and database records above, provide your direct, comprehensive answer and evidence citations for the operator."
                            )
                        ]
                        stream_iter = provider.stream_chat(
                            messages=prompt_msgs,
                            model=target_model,
                            temperature=payload.temperature or 0.7,
                            max_output_tokens=payload.max_output_tokens or settings.DEFAULT_MAX_OUTPUT_TOKENS,
                            system_prompt=effective_system_prompt,
                            tools=None,
                        )
                        async for chunk in stream_iter:
                            if await request.is_disconnected():
                                break
                            if chunk.token:
                                text_streamed = True
                                token_payload = json.dumps({"token": chunk.token})
                                yield f"data: {token_payload}\n\n"

                    # Finish turn
                    done_payload = json.dumps(
                        {
                            "done": True,
                            "finish_reason": "stop",
                            "id": chat_id,
                            "model": target_model,
                        }
                    )
                    yield f"data: {done_payload}\n\n"
                    break

            except (asyncio.CancelledError, GeneratorExit):
                logger.info(f"Client disconnected; aborting stream for {chat_id}")
                raise
            except AppException as exc:
                err_payload = json.dumps(
                    {"error": {"code": exc.code, "message": exc.message}}
                )
                yield f"event: error\ndata: {err_payload}\n\n"
            except Exception as exc:
                logger.error(f"Unexpected streaming error in {chat_id}: {exc}", exc_info=True)
                err_payload = json.dumps(
                    {"error": {"code": "streaming_error", "message": "An error occurred while streaming."}}
                )
                yield f"event: error\ndata: {err_payload}\n\n"

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming mode with tool loop
    accumulated_text = ""
    iteration = 0
    while iteration <= settings.MAX_TOOL_ITERATIONS:
        force_text_conclusion = iteration == settings.MAX_TOOL_ITERATIONS
        tools_to_pass = None if force_text_conclusion else available_tools

        turn_tool_calls: List[ToolCall] = []
        text_streamed = False

        stream_iter = provider.stream_chat(
            messages=internal_messages,
            model=target_model,
            temperature=payload.temperature or 0.7,
            max_output_tokens=payload.max_output_tokens or settings.DEFAULT_MAX_OUTPUT_TOKENS,
            system_prompt=effective_system_prompt,
            tools=tools_to_pass,
        )

        async for chunk in stream_iter:
            if chunk.tool_calls:
                turn_tool_calls.extend(chunk.tool_calls)
            if chunk.token:
                text_streamed = True
                accumulated_text += chunk.token

        if turn_tool_calls and not force_text_conclusion:
            if mcp_manager:
                tasks = [
                    mcp_manager.call_tool(tc.name, tc.arguments)
                    for tc in turn_tool_calls
                ]
                results = await asyncio.gather(*tasks)
            else:
                results = [
                    "Error: MCP manager is not available."
                    for _ in turn_tool_calls
                ]

            internal_messages.append(
                InternalMessage(
                    role="assistant",
                    content="",
                    tool_calls=turn_tool_calls,
                )
            )
            for tc, result_str in zip(turn_tool_calls, results):
                internal_messages.append(
                    InternalMessage(
                        role="tool",
                        content=result_str,
                        tool_call_id=tc.id,
                        name=tc.name,
                    )
                )

            iteration += 1
            continue

        if not text_streamed:
            prompt_msgs = internal_messages + [
                InternalMessage(
                    role="user",
                    content="Based on the retrieved tool outputs and database records above, provide your direct, comprehensive answer and evidence citations for the operator."
                )
            ]
            fallback_iter = provider.stream_chat(
                messages=prompt_msgs,
                model=target_model,
                temperature=payload.temperature or 0.7,
                max_output_tokens=payload.max_output_tokens or settings.DEFAULT_MAX_OUTPUT_TOKENS,
                system_prompt=effective_system_prompt,
                tools=None,
            )
            async for chunk in fallback_iter:
                if chunk.token:
                    accumulated_text += chunk.token

        return ChatResponse(
            id=chat_id,
            model=target_model,
            content=accumulated_text,
            finish_reason="stop",
        )

    return ChatResponse(
        id=chat_id,
        model=target_model,
        content=accumulated_text,
        finish_reason="stop",
    )
