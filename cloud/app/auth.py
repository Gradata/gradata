"""Authentication: API key validation + JWT verification."""

from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jose import JWTError, jwt as jose_jwt, jwk

from app.config import get_settings
from app.db import get_db
from app.sentry_init import tag_user

_log = logging.getLogger(__name__)
_bearer = HTTPBearer()

# Cache JWKS so we don't fetch on every request
_jwks_cache: dict | None = None

# Operator allowlist — god-mode admin access
OPERATOR_DOMAINS = {"gradata.ai", "sprites.ai"}


async def _get_jwks() -> dict:
    """Fetch and cache the Supabase JWKS for ES256 verification."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    settings = get_settings()
    url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


async def verify_api_key(key: str) -> dict:
    """Validate an SDK API key. Returns the brain record or raises 401."""
    if not key:
        raise HTTPException(status_code=401, detail="API key required")

    db = get_db()
    rows = await db.select("brains", filters={"api_key": key})
    if not rows:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return rows[0]


async def verify_jwt_claims(signed_jwt: str) -> dict:
    """Verify a Supabase JWT (ES256 or HS256) and return the full claims dict."""
    settings = get_settings()

    # Try ES256 with JWKS first (modern Supabase projects)
    try:
        jwks_data = await _get_jwks()
        keys = jwks_data.get("keys", [])
        if keys:
            # Get the signing key from JWKS
            header = jose_jwt.get_unverified_header(signed_jwt)
            kid = header.get("kid")
            key_data = next((k for k in keys if k.get("kid") == kid), keys[0])
            public_key = jwk.construct(key_data)
            claims = jose_jwt.decode(
                signed_jwt,
                public_key,
                algorithms=["ES256"],
                options={"verify_aud": False},
            )
            if not claims.get("sub"):
                raise HTTPException(status_code=401, detail="Invalid JWT: no sub claim")
            return claims
    except JWTError:
        pass  # Fall through to HS256

    # Fallback: HS256 with JWT secret (older Supabase projects)
    try:
        claims = jose_jwt.decode(
            signed_jwt,
            settings.supabase_jwt_key,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        if not claims.get("sub"):
            raise HTTPException(status_code=401, detail="Invalid JWT: no sub claim")
        return claims
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid JWT: {e}") from e


async def verify_jwt(signed_jwt: str) -> str:
    """Verify a Supabase JWT and return just the user_id."""
    claims = await verify_jwt_claims(signed_jwt)
    return claims["sub"]


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
        brain = await verify_api_key(cred)
        tag_user(str(brain.get("user_id") or brain.get("id") or ""),
                 workspace_id=str(brain.get("workspace_id") or "") or None)
        return brain

    user_id = await verify_jwt(cred)
    db = get_db()
    rows = await db.select("brains", filters={"user_id": user_id})
    if not rows:
        raise HTTPException(status_code=404, detail="No brain found for this user")
    tag_user(user_id, workspace_id=str(rows[0].get("workspace_id") or "") or None)
    return rows[0]


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> str:
    """Extract user_id from JWT. For dashboard-only endpoints."""
    user_id = await verify_jwt(credentials.credentials)
    tag_user(user_id)
    return user_id


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

    user_id = await verify_jwt(cred)
    return await verify_brain_ownership(brain_id, user_id)


async def _resolve_user_email(user_id: str, claims: dict) -> str | None:
    """Resolve the caller's email — prefer JWT claim, fall back to auth.users lookup."""
    email = claims.get("email")
    if email:
        return email

    # Fallback: query auth.users via the Supabase service-role client.
    # Supabase exposes auth users through the admin REST endpoint, not PostgREST.
    # If your db wrapper doesn't expose that, the JWT claim path is the primary route.
    try:
        db = get_db()
        rows = await db.select("users", columns="email", filters={"id": user_id})
        if rows:
            return rows[0].get("email")
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("Failed to resolve email for user=%s: %s", user_id, exc)
    return None


async def require_operator(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> str:
    """Require the caller's email domain to be in OPERATOR_DOMAINS.

    Resolves email from the JWT's ``email`` claim when present; otherwise falls
    back to a ``users`` table lookup by ``user_id``. Raises 403 otherwise.
    Returns the user_id for downstream use.
    """
    claims = await verify_jwt_claims(credentials.credentials)
    user_id = claims["sub"]

    email = await _resolve_user_email(user_id, claims)
    if not email:
        raise HTTPException(status_code=403, detail="Operator access requires a verified email")

    domain = email.split("@", 1)[1].lower() if "@" in email else ""
    if domain not in OPERATOR_DOMAINS:
        raise HTTPException(status_code=403, detail="Operator access denied")

    tag_user(user_id)
    return user_id
