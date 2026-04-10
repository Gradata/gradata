"""CORS and request logging middleware."""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings

_log = logging.getLogger(__name__)


def setup_middleware(app: FastAPI, settings: Settings) -> None:
    """Configure middleware stack."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
            _log.info("%s %s -> %d (%.0fms)", request.method, request.url.path, response.status_code, elapsed)
            return response
