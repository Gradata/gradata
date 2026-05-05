"""Tests for correction-of-correction scenarios."""

from tests.conftest import init_brain


class TestCascadingCorrections:
    def test_correction_then_correction_of_correction(self, tmp_path):
        brain = init_brain(tmp_path)
        brain.correct(draft="Hi there", final="Hello", category="TONE")
        brain.correct(draft="Hello", final="Good morning", category="TONE")
        events = brain.query_events(event_type="CORRECTION")
        assert len(events) >= 2

    def test_contradictory_corrections_tracked(self, tmp_path):
        brain = init_brain(tmp_path)
        brain.correct(draft="Use formal", final="Use casual", category="TONE")
        brain.correct(draft="Use casual", final="Use formal", category="TONE")
        events = brain.query_events(event_type="CORRECTION")
        assert len(events) >= 2
