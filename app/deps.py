import secrets
from typing import Optional
from fastapi import Request, Header
from app.config import settings
from app.errors import UnauthorizedException
from app.providers.base import LLMProvider


async def verify_auth(
    authorization: Optional[str] = Header(default=None)
) -> bool:
    """
    Validates the optional AUTH_TOKEN.
    If AUTH_TOKEN is unset or empty, auth is a no-op and requests pass through freely.
    If AUTH_TOKEN is configured, expects 'Authorization: Bearer <AUTH_TOKEN>'.
    """
    if not settings.AUTH_TOKEN:
        return True

    if not authorization:
        raise UnauthorizedException("Missing Authorization header.")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedException("Malformed Authorization header. Format must be 'Bearer <token>'.")

    if not secrets.compare_digest(token, settings.AUTH_TOKEN):
        raise UnauthorizedException("Invalid authorization token.")

    return True


def get_llm_provider(request: Request) -> LLMProvider:
    """Retrieves the active LLM provider instance from the application lifespan state."""
    provider: Optional[LLMProvider] = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        raise RuntimeError("LLMProvider was not properly initialized in app lifespan state.")
    return provider
