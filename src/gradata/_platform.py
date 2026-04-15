"""Platform source detection.

Auto-detects the runtime platform/IDE that an event originates from so
downstream analytics can attribute learning signal to its source.

Detection is environment-variable based (cheap, deterministic, no stack
introspection). Known platforms:

    claude-code   -> CLAUDECODE=1 (set by the Claude Code CLI)
    cursor        -> CURSOR / CURSOR_TRACE_ID env var
    windsurf      -> WINDSURF env var
    mcp-server    -> GRADATA_MCP_SERVER=1 (set by our MCP entrypoint)
    anthropic-sdk -> ANTHROPIC_API_KEY is set and no IDE env var above
    openai-sdk    -> OPENAI_API_KEY is set and no IDE env var above
    raw-python    -> fallback

The detected string is attached to each event's data dict under the
``platform_source`` key by ``_events.emit``. This does NOT change any
public API signatures.
"""

from __future__ import annotations

import os

# Ordered: first match wins. IDE / agent surfaces before generic SDK
# presence so an IDE that also exports an API key still attributes to the
# IDE.
_PLATFORM_ENV_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("claude-code", ("CLAUDECODE", "CLAUDE_CODE")),
    ("cursor", ("CURSOR", "CURSOR_TRACE_ID")),
    ("windsurf", ("WINDSURF", "WINDSURF_SESSION_ID")),
    ("mcp-server", ("GRADATA_MCP_SERVER",)),
    ("anthropic-sdk", ("ANTHROPIC_API_KEY",)),
    ("openai-sdk", ("OPENAI_API_KEY",)),
)

_OVERRIDE_ENV: str = "GRADATA_PLATFORM_SOURCE"
_FALLBACK: str = "raw-python"


def detect_platform_source() -> str:
    """Return a short platform identifier for the current runtime.

    Pure env-var sniff. Never raises. Safe to call on every event emit.
    """
    # Explicit override wins (tests + advanced users).
    override = os.environ.get(_OVERRIDE_ENV, "").strip()
    if override:
        return override

    for label, env_vars in _PLATFORM_ENV_CHECKS:
        if any(os.environ.get(var) for var in env_vars):
            return label

    return _FALLBACK


__all__ = ["detect_platform_source"]
