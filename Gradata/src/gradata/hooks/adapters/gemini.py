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

AGENT = "gemini"


def install(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    try:
        sig = hook_signature(AGENT, brain_dir)
        data = read_json(agent_config_path)
        tools = data.setdefault("tools", {})
        pre_call = tools.setdefault("preCall", [])
        if any(sig in str(item) for item in pre_call):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )
        pre_call.append({"id": sig, "command": hook_command(brain_dir)})
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "added", "installed tools.preCall hook")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
