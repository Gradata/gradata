"""Regression tests for the Hermes hook adapter event names.

Hermes recognises ``pre_tool_call`` / ``post_tool_call`` / ``on_session_end``
natively; the Claude-Code-style names (``pre_tool_use`` / ``post_tool_use`` /
``session_end``) are silently ignored. An earlier version of this adapter
wrote the wrong (Claude-Code) names into ``~/.hermes/config.yaml``, which
caused 5+ days of zero PostToolUse events in production. These tests pin the
correct names and verify that legacy configs get migrated to the new ones.

Refs Gradata/gradata#190.
"""

from __future__ import annotations

from pathlib import Path

from gradata.hooks.adapters import hermes


def test_install_writes_pre_tool_call_not_pre_tool_use(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    brain.mkdir()
    config = tmp_path / ".hermes" / "config.yaml"
    config.parent.mkdir()

    result = hermes.install(brain, config)

    assert result.action == "added", result.message
    text = config.read_text(encoding="utf-8")
    assert "pre_tool_call:" in text, text
    assert "pre_tool_use:" not in text, text


def test_install_is_idempotent_under_new_name(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    brain.mkdir()
    config = tmp_path / ".hermes" / "config.yaml"
    config.parent.mkdir()

    first = hermes.install(brain, config)
    second = hermes.install(brain, config)

    assert first.action == "added"
    assert second.action == "already_present"
    # One entry per native Hermes event, without duplicate installs.
    text = config.read_text(encoding="utf-8")
    sig = f"gradata:hermes:{brain.resolve().as_posix()}"
    assert text.count(sig) == 3, text
    lines = text.splitlines()
    assert lines.count("  pre_tool_call:") == 1, text
    assert lines.count("  post_tool_call:") == 1, text
    assert lines.count("  on_session_end:") == 1, text


def test_install_migrates_legacy_pre_tool_use_entry(tmp_path: Path) -> None:
    """An old broken install (entries under ``pre_tool_use``) must be migrated
    to ``pre_tool_call`` on the next ``gradata install --agent hermes`` run.
    """
    brain = tmp_path / "brain"
    brain.mkdir()
    config = tmp_path / ".hermes" / "config.yaml"
    config.parent.mkdir()
    legacy = (
        "hooks:\n"
        "  pre_tool_use:\n"
        "    - id: gradata:hermes:/some/other/brain\n"
        "      command: legacy-command\n"
    )
    config.write_text(legacy, encoding="utf-8")

    result = hermes.install(brain, config)

    assert result.action == "added", result.message
    text = config.read_text(encoding="utf-8")
    # Legacy key has been removed.
    assert "pre_tool_use:" not in text, text
    # New key holds both the migrated entry and the freshly-installed one.
    assert "pre_tool_call:" in text, text
    assert "legacy-command" in text, text
    assert f"gradata:hermes:{brain.resolve().as_posix()}" in text, text


def test_event_name_map_pins_hermes_runtime_contract() -> None:
    """Belt-and-braces: pin the Claude-Code ↔ Hermes event-name mapping so a
    future refactor can't silently regress the contract."""
    assert hermes.HERMES_EVENT_NAMES == {
        "pre_tool_use": "pre_tool_call",
        "post_tool_use": "post_tool_call",
        "session_end": "on_session_end",
    }
