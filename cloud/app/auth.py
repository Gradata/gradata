"""Authentication: API key validation + JWT verification."""

from __future__ import annotations

import logging

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jose import JWTError, jwt as jose_jwt

from app.config import get_settings
from app.db import get_db

_log = logging.getLogger(__name__)
_bearer = HTTPBearer()


async def verify_api_key(key: str) -> dict:
    """Validate an SDK API key. Returns the brain record or raises 401."""
    if not key:
        raise HTTPException(status_code=401, detail="API key required")

    db = get_db()
    rows = await db.select("brains", filters={"api_key": key})
    if not rows:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return rows[0]


def verify_jwt(signed_jwt: str, hmac_key: str | None = None) -> str:
    """Verify a Supabase JWT and return the user_id (sub claim)."""
    key = hmac_key or get_settings().supabase_jwt_key
    try:
        claims = jose_jwt.decode(signed_jwt, key, algorithms=["HS256"])
        user_id = claims.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid JWT: no sub claim")
        return user_id
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid JWT: {e}") from e


async def get_current_brain(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """FastAPI dependency: extract brain from Authorization header.

    Accepts either:
    - SDK API key: "Bearer gd_xxxx" -> look up brain by api_key
    - Supabase JWT: "Bearer ey..." -> look up brain by user_id
    """
    cred = credentials.credentials
    if cred.startswith("gd_"):
        return await verify_api_key(cred)

    # JWT path for dashboard frontend
    user_id = verify_jwt(cred)
    db = get_db()
    rows = await db.select("brains", filters={"user_id": user_id})
    if not rows:
        raise HTTPException(status_code=404, detail="No brain found for this user")
    return rows[0]


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> str:
    """Extract user_id from JWT. For dashboard-only endpoints."""
    return verify_jwt(credentials.credentials)


async def verify_brain_ownership(brain_id: str, user_id: str) -> dict:
    """Verify the authenticated user owns the brain. Returns brain or raises 403."""
    db = get_db()
    rows = await db.select("brains", filters={"id": brain_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Brain not found")
    brain = rows[0]
    if brain.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not your brain")
    return brain


async def get_brain_for_request(
    brain_id: str,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """Dual-mode auth dependency: API key or JWT, verifies brain ownership."""
    cred = credentials.credentials
    if cred.startswith("gd_"):
        brain = await verify_api_key(cred)
        if brain.get("id") != brain_id:
            raise HTTPException(status_code=403, detail="Not your brain")
        return brain

    user_id = verify_jwt(cred)
    return await verify_brain_ownership(brain_id, user_id)
