"""Tests for graceful degradation under failure conditions."""

from tests.conftest import init_brain


class TestGracefulDegradation:
    def test_apply_rules_with_no_lessons(self, tmp_path):
        brain = init_brain(tmp_path)
        assert isinstance(brain.apply_brain_rules("write an email"), str)

    def test_prove_with_no_data(self, tmp_path):
        brain = init_brain(tmp_path)
        assert isinstance(brain.prove(), dict)

    def test_manifest_with_no_sessions(self, tmp_path):
        brain = init_brain(tmp_path)
        assert isinstance(brain.manifest(), dict)

    def test_correct_with_empty_draft(self, tmp_path):
        brain = init_brain(tmp_path)
        brain.correct(draft="", final="something", category="TEST")
        events = brain.query_events(event_type="CORRECTION")
        assert len(events) >= 1, "Empty draft correction should still be recorded"

    def test_brain_init_creates_db(self, tmp_path):
        init_brain(tmp_path)
        assert (tmp_path / "brain" / "system.db").exists()

    def test_search_with_no_index(self, tmp_path):
        brain = init_brain(tmp_path)
        results = brain.search("anything")
        assert isinstance(results, list)
