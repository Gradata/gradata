"""Tests for judgment decay and rules distillation."""
import pytest
from gradata.enhancements.judgment_decay import (
    compute_decay,
    compute_batch_decay,
    DecayResult,
    DECAY_PER_IDLE_SESSION,
    CONFIDENCE_FLOOR,
    REINFORCEMENT_BONUS,
    UNTESTABLE_THRESHOLD,
    INSTINCT_CEILING,
    PATTERN_CEILING,
    is_category_testable,
    CATEGORY_SESSION_TYPES,
)
from gradata.enhancements.rules_distillation import (
    find_distillation_candidates,
    format_proposals,
    LessonEntry,
    DistillationProposal,
)
from gradata.enhancements.self_improvement import Lesson, LessonState


# ---------------------------------------------------------------------------
# Judgment Decay Tests
# ---------------------------------------------------------------------------

class TestComputeDecay:
    def _make_lesson(self, state=LessonState.PATTERN, confidence=0.70, category="TEST"):
        return Lesson(
            date="2026-03-25",
            state=state,
            confidence=confidence,
            category=category,
            description="Test lesson",
            fire_count=5,
        )

    def test_rule_tier_immune(self):
        lesson = self._make_lesson(state=LessonState.RULE, confidence=0.95)
        result = compute_decay(lesson, sessions_since_applied=10,
                               was_applied_this_session=False, total_idle_sessions=10)
        assert result.action == "skipped"
        assert result.new_confidence == 0.95

    def test_applied_this_session_reinforced(self):
        lesson = self._make_lesson(confidence=0.70)
        result = compute_decay(lesson, sessions_since_applied=0,
                               was_applied_this_session=True, total_idle_sessions=0)
        assert result.action == "reinforced"
        assert result.new_confidence == 0.70 + REINFORCEMENT_BONUS

    def test_reinforcement_capped_at_ceiling(self):
        lesson = self._make_lesson(state=LessonState.INSTINCT, confidence=0.58)
        result = compute_decay(lesson, sessions_since_applied=0,
                               was_applied_this_session=True, total_idle_sessions=0)
        assert result.new_confidence <= INSTINCT_CEILING

    def test_pattern_reinforcement_capped(self):
        lesson = self._make_lesson(state=LessonState.PATTERN, confidence=0.88)
        result = compute_decay(lesson, sessions_since_applied=0,
                               was_applied_this_session=True, total_idle_sessions=0)
        assert result.new_confidence <= PATTERN_CEILING

    def test_idle_sessions_cause_decay(self):
        lesson = self._make_lesson(confidence=0.70)
        result = compute_decay(lesson, sessions_since_applied=5,
                               was_applied_this_session=False, total_idle_sessions=5)
        expected = round(0.70 - (DECAY_PER_IDLE_SESSION * 5), 2)
        assert result.action == "decayed"
        assert result.new_confidence == expected

    def test_decay_has_floor(self):
        lesson = self._make_lesson(confidence=0.15)
        result = compute_decay(lesson, sessions_since_applied=100,
                               was_applied_this_session=False, total_idle_sessions=15)
        assert result.new_confidence >= CONFIDENCE_FLOOR

    def test_untestable_after_threshold(self):
        lesson = self._make_lesson(confidence=0.50)
        result = compute_decay(lesson, sessions_since_applied=25,
                               was_applied_this_session=False,
                               total_idle_sessions=UNTESTABLE_THRESHOLD)
        assert result.action == "archived"
        assert result.new_confidence == 0.0

    def test_no_change_when_no_idle(self):
        lesson = self._make_lesson(confidence=0.70)
        result = compute_decay(lesson, sessions_since_applied=0,
                               was_applied_this_session=False, total_idle_sessions=0)
        assert result.action == "skipped"
        assert result.new_confidence == 0.70


class TestSessionTypeAwareDecay:
    """Tests for session-type-aware decay — the core fix for Oliver's concern
    that sales lessons shouldn't decay during system sessions."""

    def _make_lesson(self, state=LessonState.PATTERN, confidence=0.70, category="TEST"):
        return Lesson(
            date="2026-03-25",
            state=state,
            confidence=confidence,
            category=category,
            description="Test lesson",
            fire_count=5,
        )

    def test_drafting_skipped_in_system_session(self):
        """DRAFTING lesson should NOT decay during a system session."""
        lesson = self._make_lesson(category="DRAFTING", confidence=0.70)
        result = compute_decay(lesson, sessions_since_applied=10,
                               was_applied_this_session=False, total_idle_sessions=10,
                               session_type="system")
        assert result.action == "skipped"
        assert result.new_confidence == 0.70
        assert "not testable" in result.reason

    def test_drafting_decays_in_sales_session(self):
        """DRAFTING lesson SHOULD decay during a sales session if idle."""
        lesson = self._make_lesson(category="DRAFTING", confidence=0.70)
        result = compute_decay(lesson, sessions_since_applied=5,
                               was_applied_this_session=False, total_idle_sessions=5,
                               session_type="sales")
        assert result.action == "decayed"
        assert result.new_confidence < 0.70

    def test_architecture_skipped_in_sales_session(self):
        """ARCHITECTURE lesson should NOT decay during a sales session."""
        lesson = self._make_lesson(category="ARCHITECTURE", confidence=0.70)
        result = compute_decay(lesson, sessions_since_applied=5,
                               was_applied_this_session=False, total_idle_sessions=5,
                               session_type="sales")
        assert result.action == "skipped"
        assert result.new_confidence == 0.70

    def test_architecture_decays_in_system_session(self):
        """ARCHITECTURE lesson SHOULD decay during a system session if idle."""
        lesson = self._make_lesson(category="ARCHITECTURE", confidence=0.70)
        result = compute_decay(lesson, sessions_since_applied=5,
                               was_applied_this_session=False, total_idle_sessions=5,
                               session_type="system")
        assert result.action == "decayed"

    def test_accuracy_decays_in_any_session(self):
        """ACCURACY is universal — decays in both sales and system sessions."""
        lesson = self._make_lesson(category="ACCURACY", confidence=0.70)
        for st in ("sales", "system", "pipeline", "mixed"):
            result = compute_decay(lesson, sessions_since_applied=5,
                                   was_applied_this_session=False, total_idle_sessions=5,
                                   session_type=st)
            assert result.action == "decayed", f"Should decay in {st}"

    def test_none_session_type_decays_everything(self):
        """Backward compat: session_type=None means all categories testable."""
        lesson = self._make_lesson(category="DRAFTING", confidence=0.70)
        result = compute_decay(lesson, sessions_since_applied=5,
                               was_applied_this_session=False, total_idle_sessions=5,
                               session_type=None)
        assert result.action == "decayed"

    def test_unknown_category_decays_everywhere(self):
        """Unknown categories default to universal (safe fallback)."""
        lesson = self._make_lesson(category="SOME_NEW_CATEGORY", confidence=0.70)
        result = compute_decay(lesson, sessions_since_applied=5,
                               was_applied_this_session=False, total_idle_sessions=5,
                               session_type="system")
        assert result.action == "decayed"

    def test_reinforcement_still_works_in_testable_session(self):
        """Applied lessons still get reinforced in their testable session type."""
        lesson = self._make_lesson(category="DRAFTING", confidence=0.70)
        result = compute_decay(lesson, sessions_since_applied=0,
                               was_applied_this_session=True, total_idle_sessions=0,
                               session_type="sales")
        assert result.action == "reinforced"

    def test_reinforcement_skipped_in_non_testable_session(self):
        """Even reinforcement is skipped if session type doesn't match —
        prevents gaming by applying a sales lesson in a system session."""
        lesson = self._make_lesson(category="DRAFTING", confidence=0.70)
        result = compute_decay(lesson, sessions_since_applied=0,
                               was_applied_this_session=True, total_idle_sessions=0,
                               session_type="system")
        assert result.action == "skipped"
        assert result.new_confidence == 0.70


class TestIsTestable:
    def test_sales_categories_testable_in_sales(self):
        for cat in ("DRAFTING", "POSITIONING", "PRICING", "DEMO_PREP", "COMMUNICATION"):
            assert is_category_testable(cat, "sales")

    def test_sales_categories_not_testable_in_system(self):
        for cat in ("DRAFTING", "POSITIONING", "PRICING", "DEMO_PREP"):
            assert not is_category_testable(cat, "system")

    def test_architecture_testable_in_system(self):
        assert is_category_testable("ARCHITECTURE", "system")

    def test_architecture_not_testable_in_sales(self):
        assert not is_category_testable("ARCHITECTURE", "sales")

    def test_universal_categories_always_testable(self):
        for cat in ("ACCURACY", "PROCESS", "THOROUGHNESS"):
            for st in ("sales", "system", "pipeline", "mixed"):
                assert is_category_testable(cat, st)

    def test_none_session_type_always_true(self):
        assert is_category_testable("DRAFTING", None)
        assert is_category_testable("ARCHITECTURE", None)

    def test_case_insensitive(self):
        assert is_category_testable("drafting", "sales")
        assert is_category_testable("DRAFTING", "Sales")


class TestBatchDecay:
    def test_batch_processes_all_lessons(self):
        lessons = [
            Lesson("2026-03-25", LessonState.PATTERN, 0.70, "A", "desc a", fire_count=5),
            Lesson("2026-03-25", LessonState.INSTINCT, 0.40, "B", "desc b", fire_count=2),
            Lesson("2026-03-25", LessonState.RULE, 0.95, "C", "desc c", fire_count=10),
        ]
        app_data = {
            "A": {"last_applied_session": 58, "applied_this_session": False, "total_idle_sessions": 4},
            "B": {"last_applied_session": 60, "applied_this_session": True, "total_idle_sessions": 0},
            "C": {"last_applied_session": 62, "applied_this_session": True, "total_idle_sessions": 0},
        }
        results = compute_batch_decay(lessons, app_data, current_session=62)
        assert len(results) == 3
        assert results[0].action == "decayed"    # A: 4 idle sessions
        assert results[1].action == "reinforced"  # B: applied this session
        assert results[2].action == "skipped"     # C: RULE tier

    def test_batch_with_session_type_filters(self):
        """Batch decay respects session_type — sales lessons skip in system sessions."""
        lessons = [
            Lesson("2026-03-25", LessonState.PATTERN, 0.70, "DRAFTING", "sales lesson", fire_count=5),
            Lesson("2026-03-25", LessonState.PATTERN, 0.70, "ARCHITECTURE", "system lesson", fire_count=5),
            Lesson("2026-03-25", LessonState.PATTERN, 0.70, "ACCURACY", "universal lesson", fire_count=5),
        ]
        app_data = {
            "DRAFTING": {"last_applied_session": 50, "applied_this_session": False, "total_idle_sessions": 12},
            "ARCHITECTURE": {"last_applied_session": 50, "applied_this_session": False, "total_idle_sessions": 12},
            "ACCURACY": {"last_applied_session": 50, "applied_this_session": False, "total_idle_sessions": 12},
        }
        results = compute_batch_decay(lessons, app_data, current_session=62, session_type="system")
        assert results[0].action == "skipped"    # DRAFTING: not testable in system
        assert results[1].action == "decayed"    # ARCHITECTURE: testable in system
        assert results[2].action == "decayed"    # ACCURACY: universal


# ---------------------------------------------------------------------------
# Rules Distillation Tests
# ---------------------------------------------------------------------------

class TestDistillation:
    def _entries(self, category, count, source="lessons.md"):
        return [
            LessonEntry(
                date=f"2026-03-{i+1:02d}",
                status="PATTERN:0.80",
                category=category,
                description=f"Lesson {i+1} about {category.lower()}",
                source=source,
            )
            for i in range(count)
        ]

    def test_no_candidates_below_threshold(self):
        entries = self._entries("DRAFTING", 2)
        proposals = find_distillation_candidates(entries, min_count=3)
        assert len(proposals) == 0

    def test_finds_candidates_at_threshold(self):
        entries = self._entries("DRAFTING", 3)
        proposals = find_distillation_candidates(entries, min_count=3)
        assert len(proposals) == 1
        assert proposals[0].category == "DRAFTING"
        assert proposals[0].count == 3
        assert proposals[0].action == "PROPOSE"

    def test_multiple_categories(self):
        entries = self._entries("DRAFTING", 5) + self._entries("ACCURACY", 4)
        proposals = find_distillation_candidates(entries, min_count=3)
        assert len(proposals) == 2
        assert proposals[0].count == 5  # DRAFTING first (higher count)

    def test_coverage_detection(self):
        entries = self._entries("DRAFTING", 3)
        existing = {"GLOBAL_RULE_1": "always review drafting output carefully lesson about drafting"}
        proposals = find_distillation_candidates(entries, existing_rules=existing, min_count=3)
        assert len(proposals) == 1
        assert proposals[0].already_covered_by is not None
        assert proposals[0].action == "ALREADY_COVERED"

    def test_mixed_sources(self):
        entries = (
            self._entries("PROCESS", 2, source="lessons.md") +
            self._entries("PROCESS", 2, source="events.jsonl")
        )
        proposals = find_distillation_candidates(entries, min_count=3)
        assert len(proposals) == 1
        assert set(proposals[0].evidence_sources) == {"lessons.md", "events.jsonl"}

    def test_format_proposals_empty(self):
        result = format_proposals([])
        assert "No distillation candidates" in result

    def test_format_proposals_with_data(self):
        entries = self._entries("DRAFTING", 4)
        proposals = find_distillation_candidates(entries, min_count=3)
        result = format_proposals(proposals)
        assert "DRAFTING" in result
        assert "PROPOSE" in result
