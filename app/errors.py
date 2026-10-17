from typing import Any, Optional
from pydantic import BaseModel
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AppException(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Any] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers or {}
        super().__init__(message)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Invalid or missing authentication token."):
        super().__init__(
            status_code=401,
            code="unauthorized",
            message=message,
            headers={"WWW-Authenticate": "Bearer"},
        )


class PayloadTooLargeException(AppException):
    def __init__(self, message: str = "Request body exceeds maximum allowed size."):
        super().__init__(
            status_code=413,
            code="payload_too_large",
            message=message,
        )


class UpstreamProviderError(AppException):
    def __init__(
        self,
        status_code: int = 503,
        code: str = "upstream_error",
        message: str = "Upstream model provider error.",
        retry_after: Optional[int] = None,
    ):
        headers = {}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        super().__init__(
            status_code=status_code,
            code=code,
            message=message,
            headers=headers,
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    content = ErrorResponse(
        error=ErrorDetail(code=exc.code, message=exc.message, details=exc.details)
    ).model_dump()
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Ensure all error elements are serializable (extracting loc, msg, type)
    sanitized_errors = []
    for err in exc.errors():
        sanitized_errors.append(
            {
                "loc": [str(item) for item in err.get("loc", [])],
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
        )

    content = ErrorResponse(
        error=ErrorDetail(
            code="validation_error",
            message="Request validation failed.",
            details=sanitized_errors,
        )
    ).model_dump()
    return JSONResponse(status_code=422, content=content)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "http_error"
    if exc.status_code == 404:
        code = "not_found"
    elif exc.status_code == 405:
        code = "method_not_allowed"
    elif exc.status_code == 401:
        code = "unauthorized"
    elif exc.status_code == 403:
        code = "forbidden"
    elif exc.status_code == 413:
        code = "payload_too_large"
    elif exc.status_code == 429:
        code = "rate_limited"

    content = ErrorResponse(
        error=ErrorDetail(code=code, message=str(exc.detail))
    ).model_dump()
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    content = ErrorResponse(
        error=ErrorDetail(
            code="internal_server_error",
            message="An unexpected server error occurred.",
        )
    ).model_dump()
    return JSONResponse(status_code=500, content=content)
