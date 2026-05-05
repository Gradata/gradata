from __future__ import annotations

import json
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


def _toml_string(value: str) -> str:
    return json.dumps(value)


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
        block = (
            "\n[[hooks.pre_tool]]\n"
            f"id = {_toml_string(sig)}\n"
            f"command = {_toml_string(hook_command(brain_dir))}\n"
        )
        atomic_write_text(agent_config_path, existing.rstrip() + block)
        return InstallResult(AGENT, agent_config_path, "added", "installed pre_tool hook")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
