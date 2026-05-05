from __future__ import annotations

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
    config_path = adapter_config_path("codex")

    result = get_adapter("codex").install(brain_dir, config_path)

    assert result.action == "added"
    parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
    hook = parsed["hooks"]["pre_tool"][0]
    assert hook["id"].startswith("gradata:codex:")
    # Round-trip: the brain dir must appear in the hook id (which is
    # build-from-brain-dir before any shell-escaping)
    assert str(brain_dir) in hook["id"]


def test_adapter_install_does_not_touch_real_user_config(tmp_path: Path) -> None:
    real_config = _REAL_HOME / ".codex" / "config.toml"
    before = real_config.read_text(encoding="utf-8") if real_config.exists() else None
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    result = get_adapter("codex").install(brain_dir, adapter_config_path("codex"))

    assert result.action == "added"
    after = real_config.read_text(encoding="utf-8") if real_config.exists() else None
    assert after == before
