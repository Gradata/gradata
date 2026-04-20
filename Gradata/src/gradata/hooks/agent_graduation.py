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


def _infer_agent_type(data: dict) -> str:
    tool_input = data.get("tool_input", {})
    return (
        tool_input.get("subagent_type", "")
        or tool_input.get("type", "")
        or "general"
    )


def main(data: dict) -> dict | None:
    try:
        brain_dir = resolve_brain_dir()
        if not brain_dir:
            return None

        agent_type = _infer_agent_type(data)
        output = data.get("tool_output", "") or ""
        if isinstance(output, dict):
            output = str(output)
        preview = output[:200] if output else ""

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
