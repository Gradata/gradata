from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path

import pytest

from gradata.hooks.adapters._base import AGENTS, adapter_config_path, get_adapter

_REAL_HOME = Path(os.path.expanduser("~"))


@pytest.mark.parametrize("agent", AGENTS)
def test_hook_adapter_install_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent: str
) -> None:
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    config_path = adapter_config_path(agent)

    adapter = get_adapter(agent)
    first = adapter.install(brain_dir, config_path)
    second = adapter.install(brain_dir, config_path)

    assert first.action == "added"
    assert second.action == "already_present"
    assert config_path.exists()
    assert "gradata" in config_path.read_text(encoding="utf-8").lower()


def test_codex_adapter_writes_valid_toml_with_quoted_brain_path(tmp_path: Path) -> None:
    # Use a brain path with chars that REQUIRE TOML quoting (spaces) but NOT
    # filesystem-reserved chars (no " on Windows, no ' since the codex adapter
    # shell-escapes apostrophes via '\'' which breaks substring matching).
    # Goal of this test: confirm the adapter writes TOML that round-trips
    # through tomllib.loads — quoting bug from Round 2 stays caught.
    brain_dir = tmp_path / "brain with spaces"
    brain_dir.mkdir()
    config_path = adapter_config_path("codex", home=tmp_path / "home")

    result = get_adapter("codex").install(brain_dir, config_path)

    assert result.action == "added"
    parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
    hook = parsed["hooks"]["pre_tool"][0]
    assert hook["id"].startswith("gradata:codex:")
    # Round-trip: the brain dir must appear in the hook id (which is
    # build-from-brain-dir before any shell-escaping).
    # Adapter normalizes to POSIX path for cross-platform stable signature,
    # so compare against as_posix() not raw str() (Windows uses backslashes).
    assert brain_dir.as_posix() in hook["id"]


def test_codex_adapter_installs_pre_post_and_session_hooks(tmp_path: Path) -> None:
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    config_path = adapter_config_path("codex", home=tmp_path / "home")

    result = get_adapter("codex").install(brain_dir, config_path)

    assert result.action == "added"
    parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert set(parsed["hooks"]) >= {"pre_tool", "post_tool", "session_end"}
    assert "gradata.hooks.inject_brain_rules" in parsed["hooks"]["pre_tool"][0]["command"]
    assert "gradata.hooks.auto_correct" in parsed["hooks"]["post_tool"][0]["command"]
    assert "gradata.hooks.session_close" in parsed["hooks"]["session_end"][0]["command"]


def test_hermes_adapter_installs_pre_post_and_session_hooks(tmp_path: Path) -> None:
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    config_path = adapter_config_path("hermes", home=tmp_path / "home")

    result = get_adapter("hermes").install(brain_dir, config_path)

    assert result.action == "added"
    text = config_path.read_text(encoding="utf-8")
    assert "pre_tool_call:" in text
    assert "post_tool_call:" in text
    assert "on_session_end:" in text
    assert "gradata.hooks.inject_brain_rules" in text
    assert "gradata.hooks.auto_correct" in text
    assert "gradata.hooks.session_close" in text


def test_opencode_adapter_installs_pre_post_and_session_hooks(tmp_path: Path) -> None:
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    config_path = adapter_config_path("opencode", home=tmp_path / "home")

    result = get_adapter("opencode").install(brain_dir, config_path)

    assert result.action == "added"
    parsed = json.loads(config_path.read_text(encoding="utf-8"))
    assert set(parsed["hooks"]) >= {"preTool", "postTool", "sessionEnd"}
    assert "gradata.hooks.inject_brain_rules" in parsed["hooks"]["preTool"][0]["command"]
    assert "gradata.hooks.auto_correct" in parsed["hooks"]["postTool"][0]["command"]
    assert "gradata.hooks.session_close" in parsed["hooks"]["sessionEnd"][0]["command"]


@pytest.mark.parametrize("agent", AGENTS)
def test_adapter_install_does_not_touch_real_user_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent: str
) -> None:
    real_config = adapter_config_path(agent, home=_REAL_HOME)
    before = real_config.read_text(encoding="utf-8") if real_config.exists() else None
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    result = get_adapter(agent).install(brain_dir, adapter_config_path(agent))

    assert result.action == "added"
    after = real_config.read_text(encoding="utf-8") if real_config.exists() else None
    assert after == before


def test_agent_install_default_brain_is_user_production_brain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from argparse import Namespace

    from gradata.cli import _resolve_agent_brain_root

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("BRAIN_DIR", raising=False)
    monkeypatch.delenv("GRADATA_BRAIN", raising=False)

    assert (
        _resolve_agent_brain_root(Namespace(brain=None, brain_dir=None))
        == home / ".gradata" / "brain"
    )


def test_agent_brain_resolution_preserves_env_first_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from argparse import Namespace

    from gradata.cli import _resolve_agent_brain_root

    monkeypatch.setenv("GRADATA_BRAIN", str(tmp_path / "gradata-brain"))
    monkeypatch.setenv("BRAIN_DIR", str(tmp_path / "brain-dir"))

    assert (
        _resolve_agent_brain_root(Namespace(brain=str(tmp_path / "cli"), brain_dir=None))
        == tmp_path / "gradata-brain"
    )

    monkeypatch.delenv("GRADATA_BRAIN")
    assert (
        _resolve_agent_brain_root(Namespace(brain=str(tmp_path / "cli"), brain_dir=None))
        == tmp_path / "brain-dir"
    )


def test_agent_brain_resolution_absolutizes_relative_cli_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from argparse import Namespace

    from gradata.cli import _resolve_agent_brain_root

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GRADATA_BRAIN", raising=False)
    monkeypatch.delenv("BRAIN_DIR", raising=False)

    assert _resolve_agent_brain_root(Namespace(brain="relative-brain", brain_dir=None)) == (
        tmp_path / "relative-brain"
    )


def test_claude_code_install_replaces_stale_same_event_module_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Installing Claude hooks must not accumulate temp-brain duplicates."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    stale_brain = tmp_path / "missing-brain"
    config_path = adapter_config_path("claude-code")
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f"BRAIN_DIR={stale_brain} python -m gradata.hooks.inject_brain_rules",
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    result = get_adapter("claude-code").install(brain_dir, config_path)

    assert result.action == "added"
    settings = json.loads(config_path.read_text(encoding="utf-8"))
    pre_tool_use = settings["hooks"]["PreToolUse"]
    commands = [hook["command"] for group in pre_tool_use for hook in group["hooks"]]
    inject_commands = [cmd for cmd in commands if "gradata.hooks.inject_brain_rules" in cmd]
    assert len(inject_commands) == 1
    assert str(stale_brain) not in inject_commands[0]


def test_claude_code_reinstall_removes_stale_duplicate_when_current_hook_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    config_path = adapter_config_path("claude-code")
    adapter = get_adapter("claude-code")
    assert adapter.install(brain_dir, config_path).action == "added"
    assert adapter.install(brain_dir, config_path).action == "already_present"

    stale_brain = tmp_path / "missing-brain"
    settings = json.loads(config_path.read_text(encoding="utf-8"))
    settings["hooks"]["PreToolUse"].append(
        {
            "matcher": "*",
            "hooks": [
                {
                    "type": "command",
                    "command": f"BRAIN_DIR={stale_brain} python -m gradata.hooks.inject_brain_rules",
                }
            ],
        }
    )
    config_path.write_text(json.dumps(settings), encoding="utf-8")

    assert adapter.install(brain_dir, config_path).action == "added"
    settings = json.loads(config_path.read_text(encoding="utf-8"))
    commands = [
        hook["command"] for group in settings["hooks"]["PreToolUse"] for hook in group["hooks"]
    ]
    inject_commands = [cmd for cmd in commands if "gradata.hooks.inject_brain_rules" in cmd]
    assert len(inject_commands) == 1
    assert str(stale_brain) not in inject_commands[0]
