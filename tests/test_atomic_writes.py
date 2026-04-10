"""Tests for atomic file operations — persistence and data integrity."""
from tests.conftest import init_brain


class TestAtomicWrites:
    def test_rapid_sequential_corrections_no_corruption(self, tmp_path):
        brain = init_brain(tmp_path)
        for t in range(3):
            for i in range(5):
                brain.correct(draft=f"t{t}-draft-{i}", final=f"t{t}-final-{i}", category="TEST")
        events = brain.query_events(event_type="CORRECTION")
        assert len(events) >= 15

    def test_single_correction_persisted(self, tmp_path):
        brain = init_brain(tmp_path)
        brain.correct(draft="good", final="better", category="TEST")
        events = brain.query_events(event_type="CORRECTION")
        assert len(events) >= 1

    def test_lessons_file_not_truncated(self, tmp_path):
        brain = init_brain(tmp_path)
        for i in range(10):
            brain.correct(draft=f"draft {i}", final=f"final {i}", category="TONE")
        lessons_path = tmp_path / "brain" / "lessons.md"
        assert lessons_path.exists(), "lessons.md should be created after 10 corrections"
        assert len(lessons_path.read_text()) > 0
