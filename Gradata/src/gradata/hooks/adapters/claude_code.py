from __future__ import annotations

from pathlib import Path

from gradata.hooks.adapters._base import (
    InstallResult,
    failure,
    hook_command,
    hook_signature,
    read_json,
    write_json,
)

AGENT = "claude-code"


def install(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    try:
        sig = hook_signature(AGENT, brain_dir)
        data = read_json(agent_config_path)
        hooks = data.setdefault("hooks", {})
        pre_tool = hooks.setdefault("PreToolUse", [])
        if any(sig in str(item) for item in pre_tool):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )
        pre_tool.append(
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": hook_command(brain_dir),
                        "id": sig,
                    }
                ],
            }
        )
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "added", "installed PreToolUse hook")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
