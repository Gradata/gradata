"""Tests for gradata.contrib.patterns.handoff."""

from __future__ import annotations

import pytest

from gradata.contrib.patterns.handoff import (
    HandoffDoc,
    HandoffWatchdog,
    _read_threshold,
    load_handoff,
    measure_pressure,
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
