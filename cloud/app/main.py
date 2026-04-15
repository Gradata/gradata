"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown resources (e.g. httpx client in SupabaseClient)."""
    yield
    db = get_db()
    if hasattr(db, "close"):
        await db.close()


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    # Sentry must init before FastAPI so the integration wraps the app.
    # No-op if GRADATA_SENTRY_DSN is unset.
    from app.sentry_init import init_sentry
    init_sentry(settings)

    is_prod = settings.environment == "production"

    app = FastAPI(
        title="Gradata Cloud API",
        version="0.1.0",
        docs_url=None if is_prod else "/docs",
        openapi_url=None if is_prod else "/openapi.json",
        redoc_url=None if is_prod else "/redoc",
        lifespan=lifespan,
    )

    from app.middleware import setup_middleware
    setup_middleware(app, settings)

    from app.routes import router
    app.include_router(router, prefix="/api/v1")

    from app.routes.health import router as health_router
    app.include_router(health_router)

    # Public, unauthenticated telemetry endpoint. Mounted at the root so the
    # SDK can POST to https://api.gradata.ai/telemetry/event without needing
    # an API key.
    from app.routes.telemetry import router as telemetry_router
    app.include_router(telemetry_router)

    return app


app = create_app()
