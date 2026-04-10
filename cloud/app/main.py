"""FastAPI application entrypoint."""
from __future__ import annotations

import logging

from fastapi import FastAPI

from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(
        title="Gradata Cloud API",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
    )

    from app.middleware import setup_middleware
    setup_middleware(app, settings)

    from app.routes import router
    app.include_router(router, prefix="/api/v1")

    from app.routes.health import router as health_router
    app.include_router(health_router)

    return app


app = create_app()
