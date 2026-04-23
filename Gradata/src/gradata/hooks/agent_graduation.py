"""PostToolUse hook: emit AGENT_OUTCOME event after Agent tool completes."""

from __future__ import annotations

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "PostToolUse",
    "matcher": "Agent",
    "profile": Profile.STANDARD,
    "timeout": 10000,
}

# Keys Claude Code has used for PostToolUse output across versions. Newer
# builds emit ``tool_response`` (sometimes as a dict with ``.content`` /
# ``.output`` / ``.result``); older builds used ``tool_output``/``output``.
_OUTPUT_KEYS = ("tool_response", "tool_output", "tool_result", "output", "response")
_NESTED_KEYS = ("content", "output", "result", "summary", "text")


def _infer_agent_type(data: dict) -> str:
    tool_input = data.get("tool_input", {})
    return tool_input.get("subagent_type", "") or tool_input.get("type", "") or "general"


def _extract_output(data: dict) -> str:
    """Pull agent output from whichever key Claude Code populated.

    Structured payloads (dicts, Claude-style content lists) are unwrapped
    one level; anything else is str()'d so downstream consumers get a
    non-empty preview whenever the agent actually produced output.
    """
    for key in _OUTPUT_KEYS:
        raw = data.get(key)
        if raw in (None, ""):
            continue

        if isinstance(raw, str):
            return raw

        if isinstance(raw, list):
            parts: list[str] = []
            for item in raw:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or item))
            joined = "\n".join(p for p in parts if p)
            if joined:
                return joined

        if isinstance(raw, dict):
            for nested in _NESTED_KEYS:
                val = raw.get(nested)
                if isinstance(val, str) and val:
                    return val
                if isinstance(val, list) and val:
                    return _extract_output({nested: val}) or str(raw)
            return str(raw)

        return str(raw)

    return ""


def main(data: dict) -> dict | None:
    try:
        brain_dir = resolve_brain_dir()
        if not brain_dir:
            return None

        agent_type = _infer_agent_type(data)
        output = _extract_output(data)
        if not output:
            return None  # Don't pollute AGENT_OUTCOME with empty rows

        preview = output[:200]

        from gradata._events import emit
        from gradata._paths import BrainContext

        ctx = BrainContext.from_brain_dir(brain_dir)
        emit(
            "AGENT_OUTCOME",
            source="hook:agent_graduation",
            data={
                "agent_type": agent_type,
                "output_preview": preview,
                "output_length": len(output),
            },
            ctx=ctx,
        )
    except Exception:
        pass
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
