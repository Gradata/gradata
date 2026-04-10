"""Route aggregation."""
from __future__ import annotations

from fastapi import APIRouter

from app.routes.sync import router as sync_router
from app.routes.brains import router as brains_router

router = APIRouter()
router.include_router(sync_router, tags=["sync"])
router.include_router(brains_router, tags=["brains"])
