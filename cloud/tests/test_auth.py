"""Tests for API key and JWT authentication."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth import verify_api_key, verify_jwt


@pytest.mark.asyncio
async def test_verify_api_key_valid(mock_supabase):
    """Valid API key returns brain record."""
    mock_supabase.add_response(
        "brains",
        "select",
        [{"id": "brain-1", "workspace_id": "ws-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    brain = await verify_api_key("gd_TVAL")
    assert brain["id"] == "brain-1"


@pytest.mark.asyncio
async def test_verify_api_key_missing():
    """Empty API key raises 401."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key("")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_invalid(mock_supabase):
    """Unknown API key raises 401."""
    mock_supabase.add_response("brains", "select", [])
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key("gd_nonexistent")
    assert exc_info.value.status_code == 401


def test_verify_jwt_valid():
    """Valid JWT extracts user_id."""
    from jose import jwt as jose_jwt

    # Generate a test-only JWT (hmac_key is NOT a real credential)
    hmac_key = "test-only-hmac-not-a-real-credential-x"
    payload = {"sub": "user-123", "role": "authenticated"}
    signed = jose_jwt.encode(payload, hmac_key, algorithm="HS256")
    user_id = verify_jwt(signed, hmac_key)
    assert user_id == "user-123"


def test_verify_jwt_expired():
    """Expired JWT raises 401."""
    from jose import jwt as jose_jwt
    import time

    hmac_key = "test-only-hmac-not-a-real-credential-x"
    payload = {"sub": "user-123", "exp": int(time.time()) - 100}
    signed = jose_jwt.encode(payload, hmac_key, algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        verify_jwt(signed, hmac_key)
    assert exc_info.value.status_code == 401
