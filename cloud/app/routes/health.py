"""Health check endpoint for Railway/uptime monitoring."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "gradata-cloud", "version": "0.1.0"}
