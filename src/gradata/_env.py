"""Canonical accessors for GRADATA_* environment variables — every var read
from >1 call site lives here so defaults and tests share one patch point.
Exposes: LLM_BASE/MODEL/KEY, GEMMA_API_KEY/MODEL, ENCRYPTION_KEY, BRAIN
(override path), API_URL (default https://api.gradata.ai/api/v1), BYPASS
(callers compare raw value to "1").
"""

from __future__ import annotations

import os


def env_str(name: str, default: str = "") -> str:
    """Return the value of env var *name*, or *default* if unset or empty."""
    return os.environ.get(name, default)


def env_flag(name: str, default: bool = False) -> bool:
    """Return True when env var *name* is set to any non-empty string."""
    val = os.environ.get(name)
    if val is None:
        return default
    return bool(val)
