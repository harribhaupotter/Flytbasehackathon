from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field, model_validator
from app.config import settings


class ImageAttachment(BaseModel):
    mime: str = Field(..., description="Image MIME type (e.g. image/png, image/jpeg, image/webp)")
    data_b64: str = Field(..., description="Base64-encoded image data without data URI prefix")

    @model_validator(mode="after")
    def validate_image_payload(self):
        if not self.mime.startswith("image/"):
            raise ValueError("Only image MIME types are permitted in image attachments.")
        if len(self.data_b64) > 8_000_000:
            raise ValueError("Individual image attachment exceeds 5 MB limit.")
        return self


class ToolCall(BaseModel):
    id: str = Field(..., description="Unique tool call identifier.")
    name: str = Field(..., description="Namespaced tool name to invoke.")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool invocation arguments.")
    thought_signature: Optional[str] = Field(default=None, description="Cryptographic thought signature for Gemini function calls.")


class ClientMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(
        ...,
        description="Role of the author. Only 'user' and 'assistant' are permitted; server injects system prompt.",
    )
    content: str = Field(
        ...,
        max_length=settings.MAX_CHARS_PER_MESSAGE,
        description="Text content of the message.",
    )
    images: Optional[List[ImageAttachment]] = Field(
        default=None,
        description="Optional image attachments for multimodal input.",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_tool_roles_and_calls(cls, data: Any):
        if isinstance(data, dict):
            if data.get("role") == "tool":
                raise ValueError("Clients may not specify role 'tool'.")
            if "tool_calls" in data:
                raise ValueError("Clients may not inject 'tool_calls'.")
        return data


# Backward-compatible alias
ChatMessage = ClientMessage


class InternalMessage(BaseModel):
    role: Literal["user", "assistant", "tool"] = Field(..., description="Author role.")
    content: str = Field(default="", description="Text content or tool response string.")
    images: Optional[List[ImageAttachment]] = Field(default=None, description="Optional images.")
    tool_call_id: Optional[str] = Field(default=None, description="ID of the matching tool call.")
    name: Optional[str] = Field(default=None, description="Name of the tool that was called.")
    tool_calls: Optional[List[ToolCall]] = Field(default=None, description="Tool calls requested by assistant.")


class ChatRequest(BaseModel):
    messages: List[ClientMessage] = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_MESSAGES,
        description="Conversation history leading up to the current turn.",
    )
    model: Optional[str] = Field(
        default=None,
        description="Model to use. Must be in ALLOWED_MODELS.",
    )
    stream: bool = Field(
        default=True,
        description="Whether to stream the response as Server-Sent Events.",
    )
    use_tools: bool = Field(
        default=False,
        description="Whether to allow the model to discover and call MCP tools.",
    )
    temperature: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature between 0.0 and 2.0.",
    )
    max_output_tokens: Optional[int] = Field(
        default=settings.DEFAULT_MAX_OUTPUT_TOKENS,
        ge=1,
        le=8192,
        description="Maximum tokens to generate.",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional client-side conversation identifier.",
    )
    user_id: Optional[str] = Field(
        default="U-201",
        description="Operator user ID (e.g. 'U-201' for Michael Turner).",
    )

    @model_validator(mode="after")
    def validate_total_chars_and_model(self):
        total_chars = sum(len(m.content) for m in self.messages)
        if total_chars > settings.MAX_TOTAL_CHARS:
            raise ValueError(
                f"Total character count across all messages ({total_chars}) exceeds "
                f"limit of {settings.MAX_TOTAL_CHARS} characters."
            )

        if self.model and self.model not in settings.ALLOWED_MODELS:
            raise ValueError(
                f"Model '{self.model}' is not permitted. Allowed models: {settings.ALLOWED_MODELS}"
            )
        return self


class ChatResponse(BaseModel):
    id: str
    model: str
    content: str
    finish_reason: str = "stop"
    usage: Optional[dict] = None


class ToolDefinition(BaseModel):
    name: str = Field(..., description="Namespaced tool name.")
    description: Optional[str] = Field(default="", description="Tool purpose and behavior.")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema for tool parameters.")


class ToolsResponse(BaseModel):
    tools: List[ToolDefinition]


class ModelsResponse(BaseModel):
    models: List[str]
    default_model: str


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_s: float
