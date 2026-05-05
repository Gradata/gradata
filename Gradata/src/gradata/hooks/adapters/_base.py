"""Shared helpers for Gradata hook adapter installers."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from gradata._atomic import atomic_write_text

Action = Literal["added", "already_present", "failed"]

AGENTS = ("claude-code", "codex", "gemini", "cursor", "hermes", "opencode")
_MODULES = {
    "claude-code": "claude_code",
    "codex": "codex",
    "gemini": "gemini",
    "cursor": "cursor",
    "hermes": "hermes",
    "opencode": "opencode",
}
_CONFIGS = {
    "claude-code": Path(".claude/settings.json"),
    "codex": Path(".codex/config.toml"),
    "gemini": Path(".gemini/settings.json"),
    "cursor": Path(".cursor/mcp.json"),
    "hermes": Path(".hermes/config.yaml"),
    "opencode": Path(".config/opencode/config.json"),
}


@dataclass(frozen=True)
class InstallResult:
    agent: str
    config_path: Path
    action: Action
    message: str


def adapter_config_path(agent: str, *, home: Path | None = None) -> Path:
    if agent not in _CONFIGS:
        raise ValueError(f"unknown agent: {agent}")
    return (home or Path.home()) / _CONFIGS[agent]


def get_adapter(agent: str):
    if agent not in _MODULES:
        raise ValueError(f"unknown agent: {agent}")
    return importlib.import_module(f"gradata.hooks.adapters.{_MODULES[agent]}")


def hook_signature(agent: str, brain_dir: Path) -> str:
    return f"gradata:{agent}:{brain_dir.resolve()}"


def hook_command(brain_dir: Path) -> str:
    return f'BRAIN_DIR="{brain_dir}" python -m gradata.hooks.inject_brain_rules'


def mcp_command(brain_dir: Path) -> list[str]:
    return ["python", "-m", "gradata.mcp_server", "--brain-dir", str(brain_dir)]


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def contains_signature(path: Path, signature: str) -> bool:
    return path.exists() and signature in path.read_text(encoding="utf-8", errors="replace")


def failure(agent: str, config_path: Path, exc: Exception) -> InstallResult:
    return InstallResult(agent, config_path, "failed", str(exc))
