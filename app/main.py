import time
from contextlib import asynccontextmanager, AsyncExitStack
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from app.config import settings
from app.errors import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
)
from app.middleware import (
    PureRequestIDMiddleware,
    PureRequestBodyLimitMiddleware,
)
from app.providers.mock import MockProvider
from app.providers.gemini import GeminiProvider
from app.providers.openai_compat import OpenAICompatProvider
from app.routers import health, models, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes server state, start time, active LLM provider, and optional MCP manager."""
    app.state.start_time = time.time()
    app.state.mcp_exit_stack = AsyncExitStack()

    async with app.state.mcp_exit_stack:
        # Determine and initialize active LLM provider
        effective_provider = settings.get_effective_provider()
        if effective_provider == "gemini" and settings.GEMINI_API_KEY:
            app.state.llm_provider = GeminiProvider(
                api_key=settings.GEMINI_API_KEY,
                default_model=settings.GEMMA_MODEL,
                system_prompt_mode=settings.SYSTEM_PROMPT_MODE,
                thinking_level=settings.THINKING_LEVEL,
                timeout_seconds=settings.UPSTREAM_TIMEOUT_SECONDS,
            )
        elif effective_provider == "groq" and settings.GROQ_API_KEY:
            app.state.llm_provider = OpenAICompatProvider(
                base_url=settings.GROQ_BASE_URL,
                api_key=settings.GROQ_API_KEY,
                default_model=settings.GROQ_MODEL,
                timeout_seconds=settings.UPSTREAM_TIMEOUT_SECONDS,
            )
        elif effective_provider == "openai_compat":
            app.state.llm_provider = OpenAICompatProvider(
                base_url=settings.LLM_BASE_URL,
                api_key=settings.LLM_API_KEY,
                default_model=settings.LLM_MODEL,
                timeout_seconds=settings.UPSTREAM_TIMEOUT_SECONDS,
            )
        else:
            app.state.llm_provider = MockProvider()

        # Initialize MCP Manager ONLY when MCP_ENABLED is True
        if settings.MCP_ENABLED:
            from app.mcp.manager import McpManager
            mcp_mgr = McpManager(exit_stack=app.state.mcp_exit_stack)
            await mcp_mgr.start()
            app.state.mcp_manager = mcp_mgr
        else:
            app.state.mcp_manager = None

        yield

        # Clean shutdown for LLM provider
        if hasattr(app.state, "llm_provider") and app.state.llm_provider:
            await app.state.llm_provider.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Aether AI Backend",
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    # Global Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Core Always-On Routers
    app.include_router(health.router)
    app.include_router(models.router)
    app.include_router(chat.router)

    # Conditionally Mount MCP Tools Router
    if settings.MCP_ENABLED:
        from app.routers import tools
        app.include_router(tools.router)

    # Middlewares (In Starlette, add_middleware added last runs first/outermost)
    # 1. Inner: Request body size limit (10 MB) with pass-through for http.disconnect
    app.add_middleware(
        PureRequestBodyLimitMiddleware,
        max_bytes=settings.MAX_REQUEST_BODY_BYTES,
    )

    # 2. Middle: Request ID tracing and access logging
    app.add_middleware(PureRequestIDMiddleware)

    # 3. Outermost: CORSMiddleware (Guarantees error responses like 413/429/500 get CORS headers)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    return app


app = create_app()
