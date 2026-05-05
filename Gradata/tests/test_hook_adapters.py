from __future__ import annotations

from pathlib import Path

import pytest

from gradata.hooks.adapters._base import AGENTS, adapter_config_path, get_adapter


@pytest.mark.parametrize("agent", AGENTS)
def test_hook_adapter_install_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent: str
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
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
