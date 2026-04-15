"""Health check endpoints for Railway/uptime monitoring + ops visibility."""
from __future__ import annotations

import logging
import os
import time
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import get_settings
from app.db import get_db
from app.rate_limit import public_limit

_log = logging.getLogger(__name__)

router = APIRouter()

_BOOTED_AT = time.time()


class HealthResponse(BaseModel):
    """Liveness — answers "is the process up". Cheap, no DB hit."""
    status: Literal["healthy"]
    service: str
    version: str


class ReadyResponse(BaseModel):
    """Readiness — answers "can we serve requests". Pings DB."""
    status: Literal["ready", "degraded", "unavailable"]
    service: str
    version: str
    environment: str
    release: str
    uptime_seconds: float
    db: Literal["ok", "fail"]
    db_latency_ms: float | None = None


@router.get("/health", response_model=HealthResponse)
@public_limit
async def health(request: Request) -> HealthResponse:
    """Liveness probe. Always returns 200 if the process is responding."""
    return HealthResponse(status="healthy", service="gradata-cloud", version="0.1.0")


@router.get("/ready", response_model=ReadyResponse)
@public_limit
async def ready(request: Request) -> ReadyResponse:
    """Readiness probe — verifies the DB is reachable. Use this for uptime monitors."""
    settings = get_settings()
    release = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "dev")[:7]
    uptime = round(time.time() - _BOOTED_AT, 2)

    db_status: Literal["ok", "fail"] = "fail"
    db_latency_ms: float | None = None
    try:
        db = get_db()
        t0 = time.time()
        # Cheap query — just count workspaces (no row data)
        await db.select("workspaces", columns="id", filters={"id": "00000000-0000-0000-0000-000000000000"})
        db_latency_ms = round((time.time() - t0) * 1000, 1)
        db_status = "ok"
    except Exception as exc:
        _log.warning("readiness DB probe failed: %s", exc)

    overall: Literal["ready", "degraded", "unavailable"] = (
        "ready" if db_status == "ok" else "unavailable"
    )

    return ReadyResponse(
        status=overall,
        service="gradata-cloud",
        version="0.1.0",
        environment=settings.environment,
        release=release,
        uptime_seconds=uptime,
        db=db_status,
        db_latency_ms=db_latency_ms,
    )
