"""Test the GRADATA_DISABLE_WRITE_THROUGH gate on session_close cloud sync.

#194 day 4: Brain.correct() write-through is the default cloud sync path.
The session_close hook's legacy cloud_sync_tick is now skipped by default
to avoid double-writes. Only runs when GRADATA_DISABLE_WRITE_THROUGH=1.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from gradata.hooks import session_close


def test_run_cloud_sync_skipped_when_write_through_default(monkeypatch):
    """Default behavior: write-through covers it, session_close tick is skipped."""
    monkeypatch.setenv("GRADATA_API_KEY", "gd_live_test")
    monkeypatch.delenv("GRADATA_DISABLE_WRITE_THROUGH", raising=False)
    with patch("gradata._core.cloud_sync_tick") as mock_tick:
        session_close._run_cloud_sync("/tmp/fake-brain", {"session_number": 1})
    (
        mock_tick.assert_not_called(),
        ("session_close must NOT call cloud_sync_tick when write-through is on"),
    )


def test_run_cloud_sync_invoked_when_write_through_disabled(monkeypatch):
    """Opt-out via GRADATA_DISABLE_WRITE_THROUGH=1: legacy path runs."""
    monkeypatch.setenv("GRADATA_API_KEY", "gd_live_test")
    monkeypatch.setenv("GRADATA_DISABLE_WRITE_THROUGH", "1")
    with patch("gradata._core.cloud_sync_tick") as mock_tick:
        session_close._run_cloud_sync("/tmp/fake-brain", {"session_number": 1})
    mock_tick.assert_called_once_with("/tmp/fake-brain", 1)


def test_run_cloud_sync_skipped_when_no_api_key(monkeypatch):
    """No API key: never call cloud regardless of write-through state."""
    monkeypatch.delenv("GRADATA_API_KEY", raising=False)
    monkeypatch.setenv("GRADATA_DISABLE_WRITE_THROUGH", "1")
    with patch("gradata._core.cloud_sync_tick") as mock_tick:
        session_close._run_cloud_sync("/tmp/fake-brain", {"session_number": 1})
    mock_tick.assert_not_called()


def test_run_graduation_exports_agents_md_for_new_rule(tmp_path: Path, monkeypatch):
    """Session-close graduation smoke: synthetic RULE promotion populates AGENTS.md."""
    monkeypatch.setenv("GRADATA_BETA_LB_GATE", "0")
    (tmp_path / "lessons.md").write_text(
        "# Lessons\n\n"
        "[2026-06-03] [PATTERN:0.95] PROCESS: Always verify work before reporting done\n"
        "  Root cause: User correction\n"
        "  Fire count: 5 | Sessions since fire: 0 | Misfires: 0\n",
        encoding="utf-8",
    )

    session_close._run_graduation(str(tmp_path))

    lessons_text = (tmp_path / "lessons.md").read_text(encoding="utf-8")
    agents_text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "[RULE:0.95] PROCESS: Always verify work before reporting done" in lessons_text
    assert "- Always verify work before reporting done" in agents_text

    session_close._run_graduation(str(tmp_path))
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == agents_text
    assert agents_text.count("Always verify work before reporting done") == 1
