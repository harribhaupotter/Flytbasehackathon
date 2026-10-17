import json
import time
import uuid
import logging
from typing import Callable
from starlette.datastructures import Headers

logger = logging.getLogger("aether.access")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class PureRequestIDMiddleware:
    """Pure ASGI middleware for tracing requests with X-Request-ID and logging metrics."""

    def __init__(self, app: Callable):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = headers.get("x-request-id") or str(uuid.uuid4())
        scope["state"] = scope.get("state", {})
        scope["state"]["request_id"] = request_id

        start_time = time.perf_counter()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Append x-request-id header
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode("latin1")))
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            client = scope.get("client")
            client_ip = client[0] if client else "-"
            method = scope.get("method", "-")
            path = scope.get("path", "-")
            # Structured log entry (never logging prompt content or secrets)
            log_entry = json.dumps(
                {
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                }
            )
            logger.info(log_entry)


class PureRequestBodyLimitMiddleware:
    """
    Pure ASGI middleware that enforces MAX_REQUEST_BODY_BYTES.
    Passes non-body messages (like http.disconnect) through unchanged.
    """

    def __init__(self, app: Callable, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        content_length_header = headers.get("content-length")

        if content_length_header is not None:
            try:
                content_length = int(content_length_header)
                if content_length > self.max_bytes:
                    await self._send_413_response(send)
                    return
            except ValueError:
                pass

        accumulated = 0
        limit_exceeded = False

        async def custom_receive():
            nonlocal accumulated, limit_exceeded
            message = await receive()

            # Pass non-request messages (e.g. http.disconnect) through unchanged
            if message["type"] != "http.request":
                return message

            body = message.get("body", b"")
            accumulated += len(body)
            if accumulated > self.max_bytes:
                limit_exceeded = True

            return message

        async def send_wrapper(message):
            if limit_exceeded:
                # Intercept normal response if limit exceeded during stream reading
                return
            await send(message)

        try:
            await self.app(scope, custom_receive, send_wrapper)
        except Exception:
            if limit_exceeded:
                await self._send_413_response(send)
                return
            raise

        if limit_exceeded:
            await self._send_413_response(send)

    async def _send_413_response(self, send):
        payload = json.dumps(
            {
                "error": {
                    "code": "payload_too_large",
                    "message": f"Request body exceeds maximum allowed size of {self.max_bytes} bytes.",
                }
            }
        ).encode("utf-8")

        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode("latin1")),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": payload,
            }
        )
