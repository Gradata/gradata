"""Platform source detection.

Auto-detects the runtime platform/IDE that an event originates from so
downstream analytics can attribute learning signal to its source.

Detection is environment-variable based (cheap, deterministic, no stack
introspection). Known platforms:

    claude-code   -> CLAUDECODE=1 (set by the Claude Code CLI)
    cursor        -> CURSOR / CURSOR_TRACE_ID env var
    windsurf      -> WINDSURF env var
    openai-sdk    -> OPENAI_API_KEY is set and no IDE env var above
    anthropic-sdk -> ANTHROPIC_API_KEY is set and no IDE env var above
    mcp-server    -> GRADATA_MCP_SERVER=1 (set by our MCP entrypoint)
    raw-python    -> fallback

The detected string is attached to each event's data dict under the
``platform_source`` key by ``_events.emit``. This does NOT change any
public API signatures.
"""

from __future__ import annotations

import os

# Ordered list: first match wins. More specific (IDE/agent surface) before
# generic SDK presence.
_PLATFORM_ENV_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("claude-code", ("CLAUDECODE", "CLAUDE_CODE")),
    ("cursor", ("CURSOR", "CURSOR_TRACE_ID")),
    ("windsurf", ("WINDSURF", "WINDSURF_SESSION_ID")),
    ("mcp-server", ("GRADATA_MCP_SERVER",)),
)

# SDK-presence checks run only when no IDE env var above matched.
_SDK_ENV_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("anthropic-sdk", ("ANTHROPIC_API_KEY",)),
    ("openai-sdk", ("OPENAI_API_KEY",)),
)


def detect_platform_source() -> str:
    """Return a short platform identifier for the current runtime.

    Pure env-var sniff. Never raises. Safe to call on every event emit.
    """
    # Explicit override wins (tests + advanced users).
    override = os.environ.get("GRADATA_PLATFORM_SOURCE")
    if override:
        return override.strip() or "raw-python"

    for label, env_vars in _PLATFORM_ENV_CHECKS:
        for var in env_vars:
            if os.environ.get(var):
                return label

    for label, env_vars in _SDK_ENV_CHECKS:
        for var in env_vars:
            if os.environ.get(var):
                return label

    return "raw-python"


__all__ = ["detect_platform_source"]
