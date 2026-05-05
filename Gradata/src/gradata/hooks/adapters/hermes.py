from __future__ import annotations

from pathlib import Path

from gradata._atomic import atomic_write_text
from gradata.hooks.adapters._base import (
    InstallResult,
    contains_signature,
    failure,
    hook_command,
    hook_signature,
)

AGENT = "hermes"


def install(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    try:
        sig = hook_signature(AGENT, brain_dir)
        if contains_signature(agent_config_path, sig):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )
        import yaml

        existing = (
            agent_config_path.read_text(encoding="utf-8") if agent_config_path.exists() else ""
        )
        loaded = yaml.safe_load(existing) if existing.strip() else {}
        data = loaded if isinstance(loaded, dict) else {}
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            hooks = {}
            data["hooks"] = hooks
        pre_tool_use = hooks.setdefault("pre_tool_use", [])
        if not isinstance(pre_tool_use, list):
            pre_tool_use = []
            hooks["pre_tool_use"] = pre_tool_use
        if any(isinstance(entry, dict) and entry.get("id") == sig for entry in pre_tool_use):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )
        pre_tool_use.append({"id": sig, "command": hook_command(brain_dir)})
        atomic_write_text(agent_config_path, yaml.safe_dump(data, sort_keys=False))
        return InstallResult(AGENT, agent_config_path, "added", "installed pre_tool_use hook")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
