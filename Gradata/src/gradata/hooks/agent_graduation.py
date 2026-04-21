"""PostToolUse hook: emit AGENT_OUTCOME event after Agent tool completes."""

from __future__ import annotations

from gradata.hooks._base import emit_hook_event, run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "PostToolUse",
    "matcher": "Agent",
    "profile": Profile.STANDARD,
    "timeout": 10000,
}


def _infer_agent_type(data: dict) -> str:
    tool_input = data.get("tool_input", {})
    return tool_input.get("subagent_type", "") or tool_input.get("type", "") or "general"


def main(data: dict) -> dict | None:
    agent_type = _infer_agent_type(data)
    output = data.get("tool_output", "") or ""
    if isinstance(output, dict):
        output = str(output)
    preview = output[:200] if output else ""
    emit_hook_event(
        "AGENT_OUTCOME",
        "hook:agent_graduation",
        {
            "agent_type": agent_type,
            "output_preview": preview,
            "output_length": len(output),
        },
    )
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
