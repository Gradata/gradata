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

AGENT = "codex"


def install(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    try:
        sig = hook_signature(AGENT, brain_dir)
        if contains_signature(agent_config_path, sig):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )
        existing = (
            agent_config_path.read_text(encoding="utf-8") if agent_config_path.exists() else ""
        )
        block = f'\n[[hooks.pre_tool]]\nid = "{sig}"\ncommand = "{hook_command(brain_dir)}"\n'
        atomic_write_text(agent_config_path, existing.rstrip() + block)
        return InstallResult(AGENT, agent_config_path, "added", "installed pre_tool hook")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
