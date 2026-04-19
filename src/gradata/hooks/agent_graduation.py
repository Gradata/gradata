"""PostToolUse hook: emit AGENT_OUTCOME event after Agent tool completes."""
from __future__ import annotations

from ._base import resolve_brain_dir, run_hook
from ._base import Profile

HOOK_META = {
    "event": "PostToolUse",
    "matcher": "Agent",
    "profile": Profile.STANDARD,
    "timeout": 10000,
}


def main(data: dict) -> dict | None:
    try:
        brain_dir = resolve_brain_dir()
        if not brain_dir:
            return None

        _ti = data.get("tool_input", {})
        agent_type = _ti.get("subagent_type", "") or _ti.get("type", "") or "general"
        output = data.get("tool_output", "") or ""
        if isinstance(output, dict):
            output = str(output)
        preview = output[:200] if output else ""

        from .._events import emit
        from .._paths import BrainContext
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
