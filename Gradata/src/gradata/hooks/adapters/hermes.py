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
        existing = (
            agent_config_path.read_text(encoding="utf-8") if agent_config_path.exists() else ""
        )
        prefix = "" if existing.strip() else "hooks:\n  pre_tool_use: []\n"
        block = (
            "\nhooks:\n  pre_tool_use:\n"
            f"    - id: {sig}\n"
            f"      command: {hook_command(brain_dir)}\n"
            if not existing.strip()
            else (
                "\n# Gradata recall hook\n"
                "hooks:\n  pre_tool_use:\n"
                f"    - id: {sig}\n"
                f"      command: {hook_command(brain_dir)}\n"
            )
        )
        atomic_write_text(
            agent_config_path, (existing.rstrip() + "\n" + prefix + block).strip() + "\n"
        )
        return InstallResult(AGENT, agent_config_path, "added", "installed pre_tool_use hook")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
