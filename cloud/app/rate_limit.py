"""Rate limiting via slowapi.

Three buckets:
- `public_limit`    — 60 req/min per IP on /health, /ready, other public GETs.
- `auth_limit`      — 300 req/min per authenticated user on API routes.
- `sensitive_limit` — 10 req/min per IP on /auth/*, /billing/webhook.

`limiter` keys by remote IP. `auth_limiter` keys by a hashed bearer-token
prefix when one is present (falls back to IP for anonymous requests).
Both instances share the same in-memory storage, so you can mix them
freely across routes.

By default, rate limits are DISABLED in test environments so the 115
existing tests don't start hitting per-IP caps. Set
`GRADATA_RATE_LIMIT_ENABLED=true` in tests that specifically exercise
the limiter (see `tests/test_rate_limit.py`).
"""
from __future__ import annotations

import hashlib
import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings


def _auth_or_ip_key(request: Request) -> str:
    """Key by hashed bearer token when present, else remote IP."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            # 12 hex chars = 48 bits — enough to disambiguate callers without
            # keeping the raw credential in limiter memory.
            return "u:" + hashlib.blake2b(token.encode("utf-8"), digest_size=6).hexdigest()
    return "ip:" + get_remote_address(request)


def limits_enabled() -> bool:
    """Resolve whether limits should be enforced.

    Production: enabled unless `GRADATA_RATE_LIMIT_ENABLED=false`.
    Test env:  disabled unless `GRADATA_RATE_LIMIT_ENABLED=true` (explicit opt-in).
    """
    raw = os.environ.get("GRADATA_RATE_LIMIT_ENABLED")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return get_settings().environment != "test"


# IP-keyed limiter (public + sensitive buckets)
limiter = Limiter(
    key_func=get_remote_address,
    enabled=limits_enabled(),
    headers_enabled=False,
)

# Bearer-token-keyed limiter (authenticated API bucket)
auth_limiter = Limiter(
    key_func=_auth_or_ip_key,
    enabled=limits_enabled(),
    headers_enabled=False,
)


def refresh_enabled_flag() -> None:
    """Recompute `enabled` on both limiters. Called from middleware setup.

    Needed because the module-level `limits_enabled()` call runs at import
    time, before test fixtures can set env vars. `setup_middleware` calls
    this after `get_settings.cache_clear()` so the latest config takes.
    """
    flag = limits_enabled()
    limiter.enabled = flag
    auth_limiter.enabled = flag


# Slowapi accepts a callable for the limit string, so the decorator reads
# the configured value lazily. `get_settings()` is cache-backed, so these
# are fast.
def _public() -> str:
    return get_settings().rate_limit_public


def _authenticated() -> str:
    return get_settings().rate_limit_authenticated


def _sensitive() -> str:
    return get_settings().rate_limit_sensitive


# Pre-built decorator factories so routes read cleanly:
#     @public_limit
#     async def health(...): ...
public_limit = limiter.limit(_public)
auth_limit = auth_limiter.limit(_authenticated)
sensitive_limit = limiter.limit(_sensitive)
