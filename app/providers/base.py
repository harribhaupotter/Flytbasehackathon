from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Optional, Dict, Any
from pydantic import BaseModel
from app.schemas import InternalMessage, ToolCall


class LLMChunk(BaseModel):
    token: str = ""
    is_thinking: bool = False
    thought: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[InternalMessage],
        model: str,
        temperature: float,
        max_output_tokens: int,
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        """Stream chunks from the model provider."""
        ...

    @abstractmethod
    async def complete_chat(
        self,
        messages: List[InternalMessage],
        model: str,
        temperature: float,
        max_output_tokens: int,
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Return complete response text from the model provider."""
        ...

    async def close(self) -> None:
        """Release any open HTTP clients or connection pools."""
        pass
