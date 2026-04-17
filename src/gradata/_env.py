"""Canonical accessors for GRADATA_* environment variables.

Every GRADATA_* variable read from more than one call site is defined here
so defaults live in one place and tests can patch a single module.

Variables exposed via this module
----------------------------------
GRADATA_LLM_BASE        — Base URL for OpenAI-compat LLM API (default: "")
GRADATA_LLM_MODEL       — LLM model identifier (default: "gpt-4o-mini")
GRADATA_LLM_KEY         — API key for the LLM service (default: "")
GRADATA_GEMMA_API_KEY   — Google AI Studio API key (default: "")
GRADATA_GEMMA_MODEL     — Gemma model identifier (default: varies per caller)
GRADATA_ENCRYPTION_KEY  — Encryption key for brain-at-rest (default: "")
GRADATA_BRAIN           — Override path for the brain directory (default: "")
GRADATA_API_URL         — Gradata API URL (default: "https://api.gradata.ai/api/v1")
GRADATA_BYPASS          — Kill-switch raw value; callers compare to "1" (default: "")
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
