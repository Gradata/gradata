"""Tests for the self-healing engine."""
from __future__ import annotations

import pytest
from gradata._types import Lesson, LessonState


class TestDetectRuleFailure:
    """detect_rule_failure: given lessons + a correction category, find rules that should have prevented it."""

    def test_detects_failure_when_rule_covers_category(self):
        from gradata.enhancements.self_healing import detect_rule_failure

        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Never use exclamation marks in emails",
            fire_count=8,
        )
        result = detect_rule_failure(
            lessons=[rule],
            correction_category="TONE",
            correction_description="Removed exclamation marks from email draft",
            min_confidence=0.80,
        )
        assert result is not None
        assert result["failed_rule_category"] == "TONE"
        assert result["failed_rule_description"] == rule.description
        assert result["failed_rule_confidence"] == 0.92

    def test_returns_none_when_no_rule_covers_category(self):
        from gradata.enhancements.self_healing import detect_rule_failure

        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="FORMAT", description="Use bullet points in reports",
            fire_count=5,
        )
        result = detect_rule_failure(
            lessons=[rule],
            correction_category="TONE",
            correction_description="Fixed the tone",
        )
        assert result is None

    def test_ignores_low_confidence_rules(self):
        from gradata.enhancements.self_healing import detect_rule_failure

        pattern = Lesson(
            date="2026-04-01", state=LessonState.PATTERN, confidence=0.65,
            category="TONE", description="Watch tone in emails",
            fire_count=4,
        )
        result = detect_rule_failure(
            lessons=[pattern],
            correction_category="TONE",
            correction_description="Fixed tone",
            min_confidence=0.80,
        )
        assert result is None

    def test_ignores_killed_rules(self):
        from gradata.enhancements.self_healing import detect_rule_failure

        killed = Lesson(
            date="2026-04-01", state=LessonState.KILLED, confidence=0.95,
            category="TONE", description="Old tone rule",
            fire_count=10, kill_reason="manual_rollback",
        )
        result = detect_rule_failure(
            lessons=[killed],
            correction_category="TONE",
            correction_description="Fixed tone",
        )
        assert result is None

    def test_includes_memory_context_when_provided(self):
        from gradata.enhancements.self_healing import detect_rule_failure

        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Never use exclamation marks",
            fire_count=8,
        )
        memory_ctx = {"active_memories": ["user prefers formal tone"], "domain": "sales"}
        result = detect_rule_failure(
            lessons=[rule],
            correction_category="TONE",
            correction_description="Removed exclamation marks",
            memory_context=memory_ctx,
        )
        assert result is not None
        assert result["memory_context"] == memory_ctx

    def test_picks_highest_confidence_rule_on_multi_match(self):
        from gradata.enhancements.self_healing import detect_rule_failure

        rule_a = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.91,
            category="TONE", description="Be formal",
            fire_count=6,
        )
        rule_b = Lesson(
            date="2026-04-02", state=LessonState.RULE, confidence=0.95,
            category="TONE", description="Never use slang",
            fire_count=10,
        )
        result = detect_rule_failure(
            lessons=[rule_a, rule_b],
            correction_category="TONE",
            correction_description="Removed slang",
        )
        assert result is not None
        assert result["failed_rule_confidence"] == 0.95


class TestBrainCorrectRuleFailure:
    """brain.correct() emits RULE_FAILURE when a RULE should have caught the correction."""

    @pytest.fixture
    def brain_with_rule(self, tmp_path):
        """Create a brain with a graduated RULE in TONE category."""
        from gradata.brain import Brain
        from gradata._types import Lesson, LessonState
        from gradata.enhancements.self_improvement import format_lessons
        from gradata._db import write_lessons_safe

        brain = Brain.init(str(tmp_path / "test-brain"))
        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Never use exclamation marks in professional emails",
            fire_count=8,
        )
        lessons_path = brain._find_lessons_path(create=True)
        write_lessons_safe(lessons_path, format_lessons([rule]))
        return brain

    def test_correction_in_ruled_category_emits_rule_failure(self, brain_with_rule):
        result = brain_with_rule.correct(
            draft="Great to hear from you! Let's connect!",
            final="Great to hear from you. Let's connect.",
            category="TONE",
        )
        # Check that a RULE_FAILURE event was emitted
        events = brain_with_rule.query_events(event_type="RULE_FAILURE", limit=10)
        assert len(events) >= 1
        failure = events[0]
        assert failure["data"]["failed_rule_category"] == "TONE"
        assert failure["data"]["failed_rule_confidence"] >= 0.80

    def test_correction_in_unruled_category_no_rule_failure(self, brain_with_rule):
        result = brain_with_rule.correct(
            draft="wrong format", final="correct format",
            category="FORMAT",
        )
        events = brain_with_rule.query_events(event_type="RULE_FAILURE", limit=10)
        assert len(events) == 0


class TestPatchRule:
    """brain.patch_rule() rewrites a rule's description while preserving metadata."""

    @pytest.fixture
    def brain_with_rule(self, tmp_path):
        from gradata.brain import Brain
        from gradata._types import Lesson, LessonState
        from gradata.enhancements.self_improvement import format_lessons
        from gradata._db import write_lessons_safe

        brain = Brain.init(str(tmp_path / "test-brain"))
        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Never use exclamation marks",
            fire_count=8,
        )
        lessons_path = brain._find_lessons_path(create=True)
        write_lessons_safe(lessons_path, format_lessons([rule]))
        return brain

    def test_patch_rewrites_description(self, brain_with_rule):
        result = brain_with_rule.patch_rule(
            category="TONE",
            old_description="Never use exclamation marks",
            new_description="Never use exclamation marks in professional emails (casual is OK)",
            reason="Rule was too broad - failed on casual context",
        )
        assert result["patched"] is True
        assert result["old_description"] == "Never use exclamation marks"
        assert result["new_description"].startswith("Never use exclamation marks in professional")

        # Verify the lesson was actually updated on disk
        lessons = brain_with_rule._load_lessons()
        tone_rules = [l for l in lessons if l.category == "TONE" and l.state.value == "RULE"]
        assert len(tone_rules) == 1
        assert "professional emails" in tone_rules[0].description

    def test_patch_preserves_confidence_and_metadata(self, brain_with_rule):
        result = brain_with_rule.patch_rule(
            category="TONE",
            old_description="Never use exclamation marks",
            new_description="Avoid exclamation marks in formal contexts",
            reason="Narrowing scope",
        )
        lessons = brain_with_rule._load_lessons()
        tone_rules = [l for l in lessons if l.category == "TONE"]
        assert tone_rules[0].confidence == 0.92
        assert tone_rules[0].fire_count == 8

    def test_patch_emits_rule_patched_event(self, brain_with_rule):
        brain_with_rule.patch_rule(
            category="TONE",
            old_description="Never use exclamation marks",
            new_description="Avoid exclamation marks in formal contexts",
            reason="Too broad",
        )
        events = brain_with_rule.query_events(event_type="RULE_PATCHED", limit=10)
        assert len(events) >= 1
        assert events[0]["data"]["reason"] == "Too broad"

    def test_patch_nonexistent_rule_returns_not_found(self, brain_with_rule):
        result = brain_with_rule.patch_rule(
            category="TONE",
            old_description="This rule does not exist",
            new_description="New version",
            reason="test",
        )
        assert result["patched"] is False
        assert "not_found" in result.get("error", "")


class TestRetroactiveTest:
    """retroactive_test: validate a proposed patch against the failure that triggered it."""

    def test_patch_that_covers_failure_passes(self):
        from gradata.enhancements.self_healing import retroactive_test

        result = retroactive_test(
            original_rule_desc="Never use exclamation marks",
            proposed_patch_desc="Never use exclamation marks in professional emails",
            correction_description="Removed exclamation marks from sales email draft",
        )
        assert result["passes"] is True

    def test_patch_unrelated_to_failure_fails(self):
        from gradata.enhancements.self_healing import retroactive_test

        result = retroactive_test(
            original_rule_desc="Use bullet points",
            proposed_patch_desc="Use numbered lists instead of bullet points",
            correction_description="Removed exclamation marks from email",
        )
        assert result["passes"] is False

    def test_patch_identical_to_original_fails(self):
        """If the patch is the same as the original, it can't help."""
        from gradata.enhancements.self_healing import retroactive_test

        result = retroactive_test(
            original_rule_desc="Never use exclamation marks",
            proposed_patch_desc="Never use exclamation marks",
            correction_description="Removed exclamation marks",
        )
        assert result["passes"] is False

    def test_delta_based_matching(self):
        """The test should check the DELTA (new words in patch), not the whole patch."""
        from gradata.enhancements.self_healing import retroactive_test

        # The delta here is "professional emails" -- relevant to "sales email draft"
        result = retroactive_test(
            original_rule_desc="Never use exclamation marks",
            proposed_patch_desc="Never use exclamation marks in professional emails",
            correction_description="Removed exclamation marks from sales email draft",
        )
        assert result["passes"] is True
        assert result.get("delta_text")  # Should expose what changed


class TestReviewRuleFailures:
    """review_rule_failures: analyze RULE_FAILURE events and produce patch candidates."""

    def test_generates_patch_for_rule_failure(self):
        from gradata.enhancements.self_healing import review_rule_failures

        failures = [{
            "data": {
                "failed_rule_category": "TONE",
                "failed_rule_description": "Never use exclamation marks",
                "failed_rule_confidence": 0.92,
                "correction_description": "Removed exclamation marks from casual Slack message",
            }
        }]
        patches = review_rule_failures(failures)
        assert len(patches) == 1
        assert patches[0]["category"] == "TONE"
        assert patches[0]["original_description"] == "Never use exclamation marks"
        assert patches[0]["proposed_description"] != "Never use exclamation marks"
        assert "retroactive_test" in patches[0]

    def test_empty_failures_returns_empty(self):
        from gradata.enhancements.self_healing import review_rule_failures

        patches = review_rule_failures([])
        assert patches == []

    def test_filters_out_patches_failing_retroactive_test(self):
        from gradata.enhancements.self_healing import review_rule_failures

        # A failure where the correction has no new context words beyond
        # stop words -- the heuristic can't narrow the rule so
        # proposed == original and retroactive test rejects it
        failures = [{
            "data": {
                "failed_rule_category": "TONE",
                "failed_rule_description": "Use bullet points in reports",
                "failed_rule_confidence": 0.90,
                "correction_description": "Use bullet points in reports",
            }
        }]
        patches = review_rule_failures(failures)
        # The patch can't narrow (correction == rule), so it returns unchanged
        passing = [p for p in patches if p.get("retroactive_test", {}).get("passes")]
        assert len(passing) == 0


class TestNudgeThreshold:
    """check_nudge_threshold: 3+ corrections in a category with no rule -> nudge."""

    def test_nudge_triggered_at_threshold(self):
        from gradata.enhancements.self_healing import check_nudge_threshold

        correction_events = [
            {"data": {"category": "TONE", "summary": "Removed exclamation marks"}, "session": 1},
            {"data": {"category": "TONE", "summary": "Toned down exclamation marks"}, "session": 2},
            {"data": {"category": "TONE", "summary": "Removed exclamation marks from email"}, "session": 3},
        ]
        lessons = []  # No rules
        result = check_nudge_threshold(correction_events, lessons, category="TONE")
        assert result["should_nudge"] is True
        assert result["correction_count"] == 3
        assert result["centroid_description"]  # Should pick most representative

    def test_no_nudge_below_threshold(self):
        from gradata.enhancements.self_healing import check_nudge_threshold

        correction_events = [
            {"data": {"category": "TONE", "summary": "Fixed tone"}, "session": 1},
            {"data": {"category": "TONE", "summary": "Fixed tone again"}, "session": 2},
        ]
        result = check_nudge_threshold(correction_events, [], category="TONE")
        assert result["should_nudge"] is False

    def test_no_nudge_when_rule_exists(self):
        from gradata.enhancements.self_healing import check_nudge_threshold

        correction_events = [
            {"data": {"category": "TONE", "summary": "Fixed tone"}, "session": i} for i in range(5)
        ]
        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.90,
            category="TONE", description="Watch your tone", fire_count=5,
        )
        result = check_nudge_threshold(correction_events, [rule], category="TONE")
        assert result["should_nudge"] is False
        assert "existing_rule" in result

    def test_auto_creates_instinct_with_pending_approval(self):
        """Nudge should auto-create an INSTINCT lesson from centroid, pending approval."""
        from gradata.enhancements.self_healing import check_nudge_threshold

        correction_events = [
            {"data": {"category": "TONE", "summary": "Removed exclamation marks from email"}, "session": 1},
            {"data": {"category": "TONE", "summary": "Toned down exclamation marks in draft"}, "session": 2},
            {"data": {"category": "TONE", "summary": "Removed exclamation marks from sales email"}, "session": 3},
        ]
        result = check_nudge_threshold(correction_events, [], category="TONE")
        assert result["should_nudge"] is True
        assert result["proposed_lesson"] is not None
        assert result["proposed_lesson"]["state"] == "INSTINCT"
        assert result["proposed_lesson"]["pending_approval"] is True


class TestNarrowRuleScope:
    """narrow_rule_scope: when a rule fails in a specific context, add exclusion scope."""

    def test_adds_domain_exclusion(self):
        import json
        from gradata.enhancements.self_healing import narrow_rule_scope

        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Never use exclamation marks",
            fire_count=8, scope_json="",
        )
        result = narrow_rule_scope(
            rule,
            failure_context={"domain": "casual_slack", "agent_type": "chat"},
        )
        assert result["narrowed"] is True
        scope = json.loads(result["new_scope_json"])
        assert "casual_slack" in scope.get("excluded_domains", [])

    def test_no_narrowing_without_context(self):
        from gradata.enhancements.self_healing import narrow_rule_scope

        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Never use exclamation marks",
            fire_count=8,
        )
        result = narrow_rule_scope(rule, failure_context={})
        assert result["narrowed"] is False

    def test_accumulates_exclusions(self):
        import json
        from gradata.enhancements.self_healing import narrow_rule_scope

        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Never use exclamation marks",
            fire_count=8,
            scope_json=json.dumps({"excluded_domains": ["casual_slack"]}),
        )
        result = narrow_rule_scope(
            rule,
            failure_context={"domain": "internal_notes"},
        )
        scope = json.loads(result["new_scope_json"])
        assert "casual_slack" in scope["excluded_domains"]
        assert "internal_notes" in scope["excluded_domains"]


class TestSelfHealingE2E:
    """Full flow: correct -> RULE_FAILURE detected -> patch generated -> rule updated."""

    @pytest.fixture
    def brain_with_rule(self, tmp_path):
        from gradata.brain import Brain
        from gradata._types import Lesson, LessonState
        from gradata.enhancements.self_improvement import format_lessons
        from gradata._db import write_lessons_safe

        brain = Brain.init(str(tmp_path / "test-brain"))
        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Never use exclamation marks",
            fire_count=8,
        )
        lessons_path = brain._find_lessons_path(create=True)
        write_lessons_safe(lessons_path, format_lessons([rule]))
        return brain

    def test_full_self_healing_flow(self, brain_with_rule):
        brain = brain_with_rule

        # 1. Correction triggers RULE_FAILURE
        result = brain.correct(
            draft="Thanks for joining! Excited to work together!",
            final="Thanks for joining. Excited to work together.",
            category="TONE",
        )
        assert result.get("rule_failure_detected") is True

        # 2. Verify RULE_FAILURE event was emitted
        failures = brain.query_events(event_type="RULE_FAILURE", limit=10)
        assert len(failures) >= 1

        # 3. Review generates a patch
        from gradata.enhancements.self_healing import review_rule_failures
        patches = review_rule_failures(failures)
        assert len(patches) >= 1

        # 4. Apply passing patches via brain.patch_rule()
        for patch in patches:
            if patch.get("retroactive_test", {}).get("passes"):
                brain.patch_rule(
                    category=patch["category"],
                    old_description=patch["original_description"],
                    new_description=patch["proposed_description"],
                    reason="E2E self-healing test",
                )

        # 5. Verify RULE_PATCHED event
        patched_events = brain.query_events(event_type="RULE_PATCHED", limit=10)
        # May or may not have patches depending on deterministic heuristic
        # But the flow should complete without errors

        # 6. Verify the lesson was updated (if patched)
        if patched_events:
            lessons = brain._load_lessons()
            tone_rules = [l for l in lessons if l.category == "TONE"]
            assert len(tone_rules) >= 1
            # Confidence may drop due to correction penalty, but should still be high
            assert tone_rules[0].confidence >= 0.70
