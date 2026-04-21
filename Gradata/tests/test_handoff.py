"""Tests for gradata.contrib.patterns.handoff."""

from __future__ import annotations

import pytest

from gradata.contrib.patterns.handoff import (
    HandoffDoc,
    HandoffWatchdog,
    _read_threshold,
    consume_handoff,
    default_handoff_dir,
    load_handoff,
    measure_pressure,
    parse_rules_snapshot_ts,
    pick_latest_unconsumed,
)


class TestMeasurePressure:
    def test_mid_range(self):
        assert measure_pressure(650, 1000) == pytest.approx(0.65)

    def test_clamps_over_one(self):
        assert measure_pressure(2000, 1000) == 1.0

    def test_clamps_negative(self):
        assert measure_pressure(-5, 1000) == 0.0

    def test_zero_max_returns_zero(self):
        assert measure_pressure(100, 0) == 0.0


class TestReadThreshold:
    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("GRADATA_HANDOFF_THRESHOLD", raising=False)
        assert _read_threshold() == 0.65

    def test_valid_override(self, monkeypatch):
        monkeypatch.setenv("GRADATA_HANDOFF_THRESHOLD", "0.5")
        assert _read_threshold() == 0.5

    def test_out_of_range_falls_back(self, monkeypatch):
        monkeypatch.setenv("GRADATA_HANDOFF_THRESHOLD", "1.5")
        assert _read_threshold() == 0.65

    def test_garbage_falls_back(self, monkeypatch):
        monkeypatch.setenv("GRADATA_HANDOFF_THRESHOLD", "not-a-number")
        assert _read_threshold() == 0.65


class TestHandoffDocRender:
    def test_minimal_doc(self):
        doc = HandoffDoc(task_id="t1", agent_name="writer", summary="Drafted email A.")
        output = doc.render()
        assert "# Handoff — t1" in output
        assert "from_: writer" in output
        assert "Drafted email A." in output
        assert "Next action" not in output
        assert "Open questions" not in output

    def test_full_doc(self):
        doc = HandoffDoc(
            task_id="t2",
            agent_name="critic",
            summary="Reviewed draft v3.",
            open_questions=["Tone too casual?"],
            next_action="Revise opener.",
            artifacts=["drafts/v3.md"],
        )
        output = doc.render()
        assert "Revise opener." in output
        assert "- Tone too casual?" in output
        assert "- drafts/v3.md" in output

    def test_empty_summary_has_placeholder(self):
        doc = HandoffDoc(task_id="t3", agent_name="x", summary="")
        assert "(no summary provided)" in doc.render()


class TestHandoffWatchdog:
    def _make(self, tmp_path, threshold=0.65):
        def synth():
            return HandoffDoc(
                task_id="t1",
                agent_name="writer",
                summary="Halfway through.",
            )

        return HandoffWatchdog(
            task_id="t1",
            agent_name="writer",
            handoff_dir=tmp_path,
            synthesizer=synth,
            threshold=threshold,
        )

    def test_below_threshold_no_trigger(self, tmp_path):
        wd = self._make(tmp_path)
        assert wd.check(tokens_used=400, tokens_max=1000) is None
        assert not list(tmp_path.iterdir())

    def test_at_threshold_triggers(self, tmp_path):
        wd = self._make(tmp_path)
        doc = wd.check(tokens_used=650, tokens_max=1000)
        assert doc is not None
        written = list(tmp_path.iterdir())
        assert len(written) == 1
        assert written[0].name == "t1_writer.handoff.md"
        assert "Halfway through." in written[0].read_text(encoding="utf-8")

    def test_fires_once_then_silent(self, tmp_path):
        wd = self._make(tmp_path)
        first = wd.check(tokens_used=800, tokens_max=1000)
        second = wd.check(tokens_used=900, tokens_max=1000)
        assert first is not None
        assert second is None

    def test_reset_allows_refire(self, tmp_path):
        wd = self._make(tmp_path)
        wd.check(tokens_used=800, tokens_max=1000)
        wd.reset()
        again = wd.check(tokens_used=800, tokens_max=1000)
        assert again is not None

    def test_custom_threshold(self, tmp_path):
        wd = self._make(tmp_path, threshold=0.5)
        assert wd.check(tokens_used=500, tokens_max=1000) is not None


class TestHandoffWatchdogEmission:
    def test_emits_handoff_triggered_event(self, tmp_path, monkeypatch):
        calls = []

        def fake_emit(event_type, source, data=None, tags=None, **kw):
            del kw
            calls.append((event_type, source, data or {}, tags or []))

        from gradata import _events as events

        monkeypatch.setattr(events, "emit", fake_emit)

        def synth():
            return HandoffDoc(task_id="t9", agent_name="writer", summary="S.")

        wd = HandoffWatchdog(
            task_id="t9",
            agent_name="writer",
            handoff_dir=tmp_path,
            synthesizer=synth,
            threshold=0.5,
        )
        wd.check(tokens_used=800, tokens_max=1000)

        assert len(calls) == 1
        event_type, source, data, tags = calls[0]
        assert event_type == "handoff.triggered"
        assert source == "handoff_watchdog"
        assert data["task_id"] == "t9"
        assert data["agent_name"] == "writer"
        assert data["threshold"] == 0.5
        assert 0.79 <= data["pressure"] <= 0.81
        assert "handoff" in tags


class TestLoadHandoff:
    def test_missing_returns_none(self, tmp_path):
        assert load_handoff("t1", "writer", tmp_path) is None

    def test_roundtrip(self, tmp_path):
        def synth():
            return HandoffDoc(task_id="t1", agent_name="writer", summary="X.")

        wd = HandoffWatchdog(
            task_id="t1",
            agent_name="writer",
            handoff_dir=tmp_path,
            synthesizer=synth,
            threshold=0.5,
        )
        wd.check(tokens_used=700, tokens_max=1000)
        loaded = load_handoff("t1", "writer", tmp_path)
        assert loaded is not None
        assert "X." in loaded


class TestRulesSnapshotTs:
    def test_doc_renders_rules_ts(self):
        doc = HandoffDoc(
            task_id="t1",
            agent_name="writer",
            summary="s",
            rules_snapshot_ts="2026-04-21T12:00:00+00:00",
        )
        assert "_rules_ts_: 2026-04-21T12:00:00+00:00" in doc.render()

    def test_parse_extracts_ts(self):
        body = "# Handoff — t1\n_rules_ts_: 2026-04-21T12:00:00+00:00\nbody"
        assert parse_rules_snapshot_ts(body) == "2026-04-21T12:00:00+00:00"

    def test_parse_returns_none_when_missing(self):
        assert parse_rules_snapshot_ts("just body, no marker") is None

    def test_default_ts_auto_populates(self):
        doc = HandoffDoc(task_id="t", agent_name="a", summary="s")
        assert doc.rules_snapshot_ts
        assert "T" in doc.rules_snapshot_ts  # ISO format


class TestDefaultHandoffDir:
    def test_appends_handoffs_folder(self, tmp_path):
        assert default_handoff_dir(tmp_path) == tmp_path / "handoffs"

    def test_accepts_string(self, tmp_path):
        result = default_handoff_dir(str(tmp_path))
        assert result == tmp_path / "handoffs"


class TestPickLatestUnconsumed:
    def test_missing_dir_returns_none(self, tmp_path):
        assert pick_latest_unconsumed(tmp_path / "nope") is None

    def test_empty_dir_returns_none(self, tmp_path):
        assert pick_latest_unconsumed(tmp_path) is None

    def test_picks_most_recent(self, tmp_path):
        old = tmp_path / "a.handoff.md"
        new = tmp_path / "b.handoff.md"
        old.write_text("old", encoding="utf-8")
        new.write_text("new", encoding="utf-8")
        import os as _os
        import time as _time

        past = _time.time() - 60
        _os.utime(old, (past, past))
        assert pick_latest_unconsumed(tmp_path) == new

    def test_ignores_consumed_subdir(self, tmp_path):
        consumed_dir = tmp_path / "consumed"
        consumed_dir.mkdir()
        (consumed_dir / "c.handoff.md").write_text("c", encoding="utf-8")
        assert pick_latest_unconsumed(tmp_path) is None

    def test_ignores_non_handoff_files(self, tmp_path):
        (tmp_path / "notes.md").write_text("x", encoding="utf-8")
        assert pick_latest_unconsumed(tmp_path) is None


class TestConsumeHandoff:
    def test_moves_to_consumed_dir(self, tmp_path):
        src = tmp_path / "a.handoff.md"
        src.write_text("body", encoding="utf-8")
        consume_handoff(src)
        assert not src.exists()
        moved = tmp_path / "consumed" / "a.handoff.md"
        assert moved.exists()
        assert moved.read_text(encoding="utf-8") == "body"

    def test_silent_on_missing(self, tmp_path):
        consume_handoff(tmp_path / "ghost.handoff.md")
