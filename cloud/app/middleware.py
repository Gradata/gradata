"""CORS, rate limiting, payload size, and request logging middleware."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import Settings
from app.rate_limit import auth_limiter, limiter, refresh_enabled_flag

_log = logging.getLogger(__name__)

# Max request body: 2 MB
MAX_BODY_BYTES = 2 * 1024 * 1024


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a 429 with a uniform JSON shape and the `Retry-After` header."""
    # slowapi sets `X-RateLimit-*` headers on success responses via
    # `headers_enabled=True`. On rejection, expose `Retry-After`.
    retry_after = getattr(exc, "retry_after", None)
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(int(retry_after))
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too Many Requests",
            "limit": str(exc.detail) if exc.detail else None,
        },
        headers=headers,
    )


def setup_middleware(app: FastAPI, settings: Settings) -> None:
    """Configure middleware stack."""
    # Make sure limiter enabled state reflects current env (tests can toggle it).
    refresh_enabled_flag()

    # Rate limiting — expose limiters via app.state so slowapi's internals can
    # locate them on decorated routes. Both share the same 429 handler.
    app.state.limiter = limiter
    app.state.auth_limiter = auth_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def reject_oversized_payloads(request: Request, call_next):
        """Reject requests with body larger than MAX_BODY_BYTES."""
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Payload too large (max {MAX_BODY_BYTES // 1024}KB)"},
            )
        return await call_next(request)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.monotonic() - start) * 1000
            _log.error("%s %s -> ERROR (%.0fms)", request.method, request.url.path, elapsed)
            raise
        else:
            elapsed = (time.monotonic() - start) * 1000
            _log.info(
                "%s %s -> %d (%.0fms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed,
            )
            return response
