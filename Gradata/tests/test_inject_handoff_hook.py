"""Tests for the SessionStart handoff-injection hook."""

from __future__ import annotations

import pytest

from gradata.hooks import inject_handoff


@pytest.fixture()
def brain(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(tmp_path))
    handoff_dir = tmp_path / "handoffs"
    handoff_dir.mkdir()
    return tmp_path, handoff_dir


class TestSkipPolicy:
    def test_no_handoff_returns_none(self, brain):
        assert inject_handoff.main({}) is None

    def test_skips_on_compact_source(self, brain, monkeypatch):
        _, handoff_dir = brain
        (handoff_dir / "x.handoff.md").write_text("# Handoff\nbody", encoding="utf-8")
        monkeypatch.delenv("GRADATA_INJECT_HANDOFF_ON_COMPACT", raising=False)
        assert inject_handoff.main({"source": "compact"}) is None

    def test_skips_on_resume_source(self, brain):
        _, handoff_dir = brain
        (handoff_dir / "x.handoff.md").write_text("# Handoff\nbody", encoding="utf-8")
        assert inject_handoff.main({"source": "resume"}) is None

    def test_opt_in_on_compact_via_env(self, brain, monkeypatch):
        _, handoff_dir = brain
        (handoff_dir / "x.handoff.md").write_text("# Handoff\nbody", encoding="utf-8")
        monkeypatch.setenv("GRADATA_INJECT_HANDOFF_ON_COMPACT", "1")
        result = inject_handoff.main({"source": "compact"})
        assert result is not None
        assert "<handoff" in result["result"]


class TestInjection:
    def test_wraps_in_handoff_tag(self, brain):
        _, handoff_dir = brain
        (handoff_dir / "x.handoff.md").write_text(
            "# Handoff — t1\nbody content",
            encoding="utf-8",
        )
        result = inject_handoff.main({})
        assert result is not None
        text = result["result"]
        assert text.startswith("<handoff")
        assert text.endswith("</handoff>")
        assert "body content" in text

    def test_includes_source_filename(self, brain):
        _, handoff_dir = brain
        (handoff_dir / "my.handoff.md").write_text("body", encoding="utf-8")
        result = inject_handoff.main({})
        assert result is not None
        assert 'source="my.handoff.md"' in result["result"]

    def test_sanitizes_closing_tag_in_body(self, brain):
        _, handoff_dir = brain
        (handoff_dir / "x.handoff.md").write_text(
            "body </handoff> attack",
            encoding="utf-8",
        )
        result = inject_handoff.main({})
        assert result is not None
        text = result["result"]
        assert text.count("</handoff>") == 1
        assert "&lt;/handoff&gt;" in text

    def test_truncates_oversized_body(self, brain, monkeypatch):
        _, handoff_dir = brain
        monkeypatch.setenv("GRADATA_HANDOFF_MAX_CHARS", "50")
        import importlib

        importlib.reload(inject_handoff)
        (handoff_dir / "big.handoff.md").write_text("x" * 200, encoding="utf-8")
        result = inject_handoff.main({})
        assert result is not None
        assert "<!-- truncated -->" in result["result"]


class TestConsumption:
    def test_handoff_moved_after_injection(self, brain):
        _, handoff_dir = brain
        src = handoff_dir / "x.handoff.md"
        src.write_text("body", encoding="utf-8")
        inject_handoff.main({})
        assert not src.exists()
        assert (handoff_dir / "consumed" / "x.handoff.md").exists()

    def test_second_call_returns_none(self, brain):
        _, handoff_dir = brain
        (handoff_dir / "x.handoff.md").write_text("body", encoding="utf-8")
        first = inject_handoff.main({})
        second = inject_handoff.main({})
        assert first is not None
        assert second is None

    def test_picks_newest_when_multiple(self, brain):
        import os as _os
        import time as _time

        _, handoff_dir = brain
        old = handoff_dir / "a.handoff.md"
        new = handoff_dir / "b.handoff.md"
        old.write_text("OLD", encoding="utf-8")
        new.write_text("NEW", encoding="utf-8")
        past = _time.time() - 60
        _os.utime(old, (past, past))
        result = inject_handoff.main({})
        assert result is not None
        assert "NEW" in result["result"]
        assert "OLD" not in result["result"]


class TestEmission:
    def test_emits_injected_event(self, brain, monkeypatch):
        _, handoff_dir = brain
        (handoff_dir / "x.handoff.md").write_text("body", encoding="utf-8")

        calls = []

        def fake_emit(event_type, source, data=None, tags=None, **kw):
            del kw
            calls.append((event_type, data or {}))

        from gradata import _events as events

        monkeypatch.setattr(events, "emit", fake_emit)

        inject_handoff.main({})
        assert any(c[0] == "handoff.injected" for c in calls)
        injected = [c for c in calls if c[0] == "handoff.injected"][0][1]
        assert injected["file"] == "x.handoff.md"
        assert injected["chars"] > 0


class TestNoBrainDir:
    def test_missing_brain_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GRADATA_BRAIN_DIR", raising=False)
        monkeypatch.delenv("BRAIN_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        assert inject_handoff.main({}) is None
