"""Tests for agent graduation — compounding behavioral adaptation for agents."""

import pytest

from gradata.enhancements.graduation.agent_graduation import (
    GATE_DEMOTION_THRESHOLD,
    GATE_MIN_OUTPUTS_AUTO,
    GATE_MIN_OUTPUTS_PREVIEW,
    AgentGraduationTracker,
    compile_deterministic_rule,
)
from gradata.enhancements.self_improvement import LessonState


@pytest.fixture
def tracker(tmp_path):
    """Create a fresh tracker with temp brain directory."""
    return AgentGraduationTracker(tmp_path)


class TestAgentProfile:
    def test_new_agent_starts_at_confirm(self, tracker):
        gate = tracker.get_approval_gate("research")
        assert gate == "confirm"

    def test_fda_rate_zero_with_no_outputs(self, tracker):
        profile = tracker._load_profile("research")
        assert profile.fda_rate == 0.0

    def test_record_approved_increments(self, tracker):
        profile = tracker.record_outcome("research", "test output", "approved")
        assert profile.total_outputs == 1
        assert profile.approved_unchanged == 1
        assert profile.fda_rate == 1.0

    def test_record_edited_increments(self, tracker):
        profile = tracker.record_outcome(
            "research", "test output", "edited", edits="Fixed the intro"
        )
        assert profile.total_outputs == 1
        assert profile.approved_edited == 1
        assert profile.fda_rate == 0.0  # edited != FDA

    def test_record_rejected_increments(self, tracker):
        profile = tracker.record_outcome("research", "test output", "rejected")
        assert profile.total_outputs == 1
        assert profile.rejected == 1
        assert profile.consecutive_rejections == 1

    def test_consecutive_rejections_reset_on_approve(self, tracker):
        tracker.record_outcome("research", "bad", "rejected")
        tracker.record_outcome("research", "bad", "rejected")
        profile = tracker.record_outcome("research", "good", "approved")
        assert profile.consecutive_rejections == 0


class TestApprovalGateGraduation:
    def test_gate_stays_confirm_with_few_outputs(self, tracker):
        for _ in range(5):
            tracker.record_outcome("research", "output", "approved")
        assert tracker.get_approval_gate("research") == "confirm"

    def test_gate_graduates_to_preview(self, tracker):
        """After enough approved outputs, gate should graduate."""
        for i in range(GATE_MIN_OUTPUTS_PREVIEW + 1):
            tracker.record_outcome("research", f"output {i}", "approved")
        assert tracker.get_approval_gate("research") == "preview"

    def test_gate_graduates_to_auto(self, tracker):
        """After sustained high FDA, gate should reach auto."""
        for i in range(GATE_MIN_OUTPUTS_AUTO + 1):
            tracker.record_outcome("research", f"output {i}", "approved")
        assert tracker.get_approval_gate("research") == "auto"

    def test_gate_demotes_on_consecutive_rejections(self, tracker):
        # First get to preview
        for i in range(GATE_MIN_OUTPUTS_PREVIEW + 1):
            tracker.record_outcome("research", f"output {i}", "approved")
        assert tracker.get_approval_gate("research") == "preview"

        # Then get rejected consecutively
        for _ in range(GATE_DEMOTION_THRESHOLD):
            tracker.record_outcome("research", "bad output", "rejected")
        assert tracker.get_approval_gate("research") == "confirm"

    def test_new_agent_type_always_starts_confirm(self, tracker):
        # Even after research is at auto
        for i in range(GATE_MIN_OUTPUTS_AUTO + 1):
            tracker.record_outcome("research", f"output {i}", "approved")
        assert tracker.get_approval_gate("research") == "auto"
        assert tracker.get_approval_gate("writer") == "confirm"


class TestAgentLessonGraduation:
    def test_edit_creates_instinct_lesson(self, tracker):
        tracker.record_outcome(
            "research", "test output", "edited", edits="Should cite primary sources, not blog posts"
        )
        profile = tracker._load_profile("research")
        assert len(profile.lessons) == 1
        assert profile.lessons[0].state == LessonState.INSTINCT

    def test_lesson_confidence_increases_on_approval(self, tracker):
        # Create a lesson via edit
        tracker.record_outcome("research", "output 1", "edited", edits="Need primary sources")
        initial_confidence = tracker._load_profile("research").lessons[0].confidence

        # Approve several times (lesson survives)
        for i in range(5):
            tracker.record_outcome("research", f"output {i + 2}", "approved")

        final_confidence = tracker._load_profile("research").lessons[0].confidence
        assert final_confidence > initial_confidence

    def test_lesson_graduates_to_pattern(self, tracker):
        # Lesson starts at confidence 0.30, plus SURVIVAL_BONUS on the edit.
        tracker.record_outcome("research", "output", "edited", edits="Always cite 3+ sources")
        # ACCEPTANCE_BONUS=0.20 and 8 approvals push confidence well past both
        # PATTERN (0.60) and RULE (0.90) thresholds, with fire_count past the
        # RULE minimum. Final graduated state is RULE (stricter than PATTERN).
        for i in range(8):
            tracker.record_outcome("research", f"output {i}", "approved")

        profile = tracker._load_profile("research")
        assert any(l.state in (LessonState.PATTERN, LessonState.RULE) for l in profile.lessons), (
            "lesson should have graduated out of INSTINCT"
        )

    def test_rejection_decreases_confidence(self, tracker):
        tracker.record_outcome("research", "output", "edited", edits="Bad pattern")
        initial = tracker._load_profile("research").lessons[0].confidence

        tracker.record_outcome("research", "output", "rejected")
        final = tracker._load_profile("research").lessons[0].confidence
        assert final < initial


class TestDistillation:
    def test_distill_empty_with_no_patterns(self, tracker):
        tracker.record_outcome("research", "output", "approved")
        distilled = tracker.distill_upward()
        assert distilled == []

    def test_distill_returns_graduated_lessons(self, tracker):
        # Create and graduate a lesson
        tracker.record_outcome("research", "output", "edited", edits="Always verify sources")
        # Push it to PATTERN level
        for i in range(20):
            tracker.record_outcome("research", f"output {i}", "approved")

        distilled = tracker.distill_upward()
        assert len(distilled) >= 1
        assert distilled[0]["source"] == "agent:research"
        assert distilled[0]["state"] in ("PATTERN", "RULE")


class TestPersistence:
    def test_profile_persists_across_instances(self, tmp_path):
        tracker1 = AgentGraduationTracker(tmp_path)
        tracker1.record_outcome("research", "output", "approved")

        tracker2 = AgentGraduationTracker(tmp_path)
        profile = tracker2._load_profile("research")
        assert profile.total_outputs == 1

    def test_outcomes_log_is_append_only(self, tracker):
        tracker.record_outcome("research", "output 1", "approved")
        tracker.record_outcome("research", "output 2", "edited", edits="fix")

        outcomes_path = tracker._agent_dir("research") / "outcomes.jsonl"
        lines = outcomes_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

    def test_lessons_file_created(self, tracker):
        tracker.record_outcome("research", "output", "edited", edits="Need better sources")
        lessons_path = tracker._agent_dir("research") / "lessons.md"
        assert lessons_path.exists()
        content = lessons_path.read_text(encoding="utf-8")
        assert "Need better sources" in content


class TestAgentRules:
    def test_get_rules_empty_for_new_agent(self, tracker):
        rules = tracker.get_agent_rules("research")
        assert rules == []

    def test_get_context_empty_for_new_agent(self, tracker):
        ctx = tracker.get_agent_context("research")
        assert ctx == ""

    def test_get_context_includes_graduated_rules(self, tracker):
        # Build up a graduated lesson
        tracker.record_outcome("research", "output", "edited", edits="Always cite sources")
        for i in range(20):
            tracker.record_outcome("research", f"output {i}", "approved")

        ctx = tracker.get_agent_context("research")
        assert "Agent Training Context" in ctx
        assert "research" in ctx


class TestDashboard:
    def test_dashboard_empty(self, tracker):
        result = tracker.format_dashboard()
        assert "No agent profiles" in result

    def test_dashboard_shows_agents(self, tracker):
        tracker.record_outcome("research", "output", "approved")
        tracker.record_outcome("writer", "output", "edited", edits="fix tone")

        result = tracker.format_dashboard()
        assert "research" in result
        assert "writer" in result
        assert "FDA" in result


class TestMultipleAgentTypes:
    def test_separate_profiles_per_type(self, tracker):
        tracker.record_outcome("research", "output", "approved")
        tracker.record_outcome("writer", "output", "rejected")

        research = tracker._load_profile("research")
        writer = tracker._load_profile("writer")

        assert research.fda_rate == 1.0
        assert writer.fda_rate == 0.0
        assert research.approval_gate == "confirm"
        assert writer.approval_gate == "confirm"

    def test_all_profiles_listed(self, tracker):
        tracker.record_outcome("research", "output", "approved")
        tracker.record_outcome("writer", "output", "approved")
        tracker.record_outcome("critic", "output", "approved")

        profiles = tracker.get_all_profiles()
        assert len(profiles) == 3
        types = {p.agent_type for p in profiles}
        assert types == {"research", "writer", "critic"}


class TestDeterministicRules:
    """Tests for deterministic rule enforcement from graduated patterns."""

    def test_compile_positioning_rule(self):
        """POSITIONING rule with 'agency pricing' should compile to regex guard."""
        from gradata.enhancements.self_improvement import Lesson

        lesson = Lesson(
            date="2026-03-25",
            state=LessonState.RULE,
            confidence=0.95,
            category="POSITIONING",
            description="Never use 'agency pricing' — it implies expensive retainers",
            fire_count=10,
        )
        rule = compile_deterministic_rule(lesson)
        assert rule is not None
        assert rule.pattern is not None
        # Should catch "agency pricing" in output
        result = rule.check("Our agency pricing starts at $5K/month")
        assert not result["passed"]
        # Should pass clean output
        result = rule.check("Fixed monthly subscription, cancel anytime")
        assert result["passed"]

    def test_compile_non_enforceable_returns_none(self):
        """DRAFTING rules can't be enforced deterministically."""
        from gradata.enhancements.self_improvement import Lesson

        lesson = Lesson(
            date="2026-03-25",
            state=LessonState.RULE,
            confidence=0.95,
            category="DRAFTING",
            description="Lead with empathy in follow-up emails",
            fire_count=10,
        )
        rule = compile_deterministic_rule(lesson)
        assert rule is None

    def test_compile_requires_rule_tier(self):
        """Only RULE-tier lessons can be compiled."""
        from gradata.enhancements.self_improvement import Lesson

        lesson = Lesson(
            date="2026-03-25",
            state=LessonState.PATTERN,
            confidence=0.75,
            category="POSITIONING",
            description="Never use 'agency pricing'",
            fire_count=5,
        )
        rule = compile_deterministic_rule(lesson)
        assert rule is None

    def test_data_integrity_rule(self):
        """DATA_INTEGRITY rule compiles and has owner_only check."""
        from gradata.enhancements.self_improvement import Lesson

        lesson = Lesson(
            date="2026-03-25",
            state=LessonState.RULE,
            confidence=0.95,
            category="DATA_INTEGRITY",
            description="owner_only — never include other users' data",
            fire_count=10,
        )
        rule = compile_deterministic_rule(lesson)
        assert rule is not None
        # The placeholder regex matches "EXCLUDED_NAMES_PLACEHOLDER" — users configure real names
        result = rule.check("EXCLUDED_NAMES_PLACEHOLDER's campaign sent 84K emails")
        assert not result["passed"]
        result = rule.check("My pipeline has 12 active prospects")
        assert result["passed"]

    def test_pricing_rule(self):
        """PRICING rule blocks starter tier multi-account claims."""
        from gradata.enhancements.self_improvement import Lesson

        lesson = Lesson(
            date="2026-03-25",
            state=LessonState.RULE,
            confidence=0.95,
            category="PRICING",
            description="Starter tier multi-brand not supported, only one account",
            fire_count=10,
        )
        rule = compile_deterministic_rule(lesson)
        assert rule is not None
        result = rule.check("With Starter you can connect two accounts")
        assert not result["passed"]

    def test_enforce_rules_on_tracker(self, tracker):
        """enforce_rules() returns violations for non-compliant output."""
        # Manually create a profile with a RULE lesson
        profile = tracker._load_profile("writer")
        from gradata.enhancements.self_improvement import Lesson

        profile.lessons.append(
            Lesson(
                date="2026-03-25",
                state=LessonState.RULE,
                confidence=0.95,
                category="POSITIONING",
                description="Never use 'agency pricing' — it implies expensive retainers",
                fire_count=10,
            )
        )
        tracker._save_profile(profile)

        result = tracker.enforce_rules("writer", "Check out our agency pricing model")
        assert not result.passed
        assert len(result.violations) == 1
        assert result.violations[0]["category"] == "POSITIONING"

    def test_enforce_rules_clean_output(self, tracker):
        """enforce_rules() passes clean output."""
        profile = tracker._load_profile("writer")
        from gradata.enhancements.self_improvement import Lesson

        profile.lessons.append(
            Lesson(
                date="2026-03-25",
                state=LessonState.RULE,
                confidence=0.95,
                category="POSITIONING",
                description="Never use 'agency pricing'",
                fire_count=10,
            )
        )
        tracker._save_profile(profile)

        result = tracker.enforce_rules("writer", "Flat monthly rate, cancel anytime")
        assert result.passed
        assert len(result.violations) == 0

    def test_enforce_rules_no_rules(self, tracker):
        """enforce_rules() with no RULE-tier lessons returns passed."""
        tracker.record_outcome("research", "output", "approved")
        result = tracker.enforce_rules("research", "any output here")
        assert result.passed
        assert result.rules_checked == 0


# ---------------------------------------------------------------------------
# Regression: Bug H2 — fire_count incremented for all lessons on any approval
# ---------------------------------------------------------------------------


class TestAgentFireCountGate:
    """Regression for H2: agent _update_lesson_confidence must gate fire_count
    on category relevance, mirroring the main pipeline's was_injected guard.

    Bug: every "approved" outcome incremented fire_count for ALL lessons,
    regardless of whether the lesson's category matched the corrected category.
    This silently fast-tracked lessons toward RULE promotion without evidence.

    Fix: fire_count is only incremented when lesson.category matches
    edit_category (or when edit_category is empty, for backward compat).
    """

    def test_approval_only_increments_matching_category(self, tracker):
        """Approving a TONE edit must not increment fire_count for DRAFTING lessons."""
        from gradata.enhancements.self_improvement import INITIAL_CONFIDENCE, Lesson

        profile = tracker._load_profile("writer")
        tone_lesson = Lesson(
            date="2026-04-01",
            state=LessonState.INSTINCT,
            confidence=INITIAL_CONFIDENCE,
            category="TONE",
            description="Use warm language",
            fire_count=0,
        )
        drafting_lesson = Lesson(
            date="2026-04-01",
            state=LessonState.INSTINCT,
            confidence=INITIAL_CONFIDENCE,
            category="DRAFTING",
            description="Keep sentences short",
            fire_count=0,
        )
        profile.lessons = [tone_lesson, drafting_lesson]
        tracker._save_profile(profile)

        # Record an approved outcome with edit_category="TONE"
        tracker.record_outcome(
            "writer",
            "sample output",
            "approved",
            edit_category="TONE",
            session=1,
        )

        profile = tracker._load_profile("writer")
        tone_lesson_after = next(l for l in profile.lessons if l.category == "TONE")
        drafting_lesson_after = next(l for l in profile.lessons if l.category == "DRAFTING")

        assert tone_lesson_after.fire_count == 1, (
            f"TONE lesson should have fire_count=1, got {tone_lesson_after.fire_count}"
        )
        assert drafting_lesson_after.fire_count == 0, (
            f"DRAFTING lesson should not have been incremented (fire_count="
            f"{drafting_lesson_after.fire_count}); approval was for TONE category"
        )

    def test_approval_without_edit_category_increments_all(self, tracker):
        """Backward compat: no edit_category increments all lessons (legacy behaviour)."""
        from gradata.enhancements.self_improvement import INITIAL_CONFIDENCE, Lesson

        profile = tracker._load_profile("writer")
        profile.lessons = [
            Lesson(
                date="2026-04-01",
                state=LessonState.INSTINCT,
                confidence=INITIAL_CONFIDENCE,
                category="TONE",
                description="lesson A",
                fire_count=0,
            ),
            Lesson(
                date="2026-04-01",
                state=LessonState.INSTINCT,
                confidence=INITIAL_CONFIDENCE,
                category="DRAFTING",
                description="lesson B",
                fire_count=0,
            ),
        ]
        tracker._save_profile(profile)

        # No edit_category — legacy path must increment all
        tracker.record_outcome("writer", "output", "approved", session=1)

        profile = tracker._load_profile("writer")
        for lesson in profile.lessons:
            assert lesson.fire_count == 1, (
                f"Legacy path: all lessons should have fire_count=1, "
                f"{lesson.category} got {lesson.fire_count}"
            )
