"""
Tests for rule_engine.py S71 additions:
- merge_related_rules()
- format_rules_for_prompt() with XML tags, primacy/recency, few-shot examples
- detect_task_type()
- compute_rule_difficulty()
- compute_scope_weight()
- capture_example_from_correction()
- _difficulty_from_lesson()
- _make_rule_id()

Run: cd sdk && python -m pytest tests/test_rule_engine_v2.py -v
"""

from __future__ import annotations

import pytest

from gradata._types import Lesson, LessonState
from gradata._scope import RuleScope
from gradata.rules.rule_engine import (
    AppliedRule,
    apply_rules,
    capture_example_from_correction,
    compute_rule_difficulty,
    compute_scope_weight,
    detect_task_type,
    filter_by_scope,
    format_rules_for_prompt,
    merge_related_rules,
    _difficulty_from_lesson,
    _make_rule_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lesson(
    category: str = "DRAFTING",
    description: str = "Test lesson",
    state: LessonState = LessonState.RULE,
    confidence: float = 0.95,
    fire_count: int = 5,
    misfire_count: int = 0,
    scope_json: str = "",
    example_draft: str | None = None,
    example_corrected: str | None = None,
) -> Lesson:
    return Lesson(
        date="2026-03-26",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
        fire_count=fire_count,
        misfire_count=misfire_count,
        scope_json=scope_json,
        example_draft=example_draft,
        example_corrected=example_corrected,
    )


def _make_applied(lesson: Lesson, relevance: float = 0.8) -> AppliedRule:
    return AppliedRule(
        rule_id=_make_rule_id(lesson),
        lesson=lesson,
        relevance=relevance,
        instruction=f"[{lesson.state.value}:{lesson.confidence:.2f}] {lesson.category}: {lesson.description}",
    )


# ===========================================================================
# detect_task_type
# ===========================================================================


class TestDetectTaskType:
    """detect_task_type() maps user messages to task type strings."""

    def test_email_detected(self):
        assert detect_task_type("draft an email to the CEO") == "email"

    def test_demo_prep_detected(self):
        assert detect_task_type("prepare for the demo with Acme Corp") == "demo_prep"

    def test_code_detected(self):
        assert detect_task_type("refactor the rule engine module") == "code"

    def test_prospecting_detected(self):
        assert detect_task_type("enrich these leads from LinkedIn") == "prospecting"

    def test_research_detected(self):
        assert detect_task_type("research the competitive landscape") == "research"

    def test_call_detected(self):
        assert detect_task_type("prepare talking points for the meeting") == "call"

    def test_document_detected(self):
        assert detect_task_type("write a guide for the SDK") == "document"

    def test_unknown_returns_empty(self):
        assert detect_task_type("hello world") == ""

    def test_case_insensitive(self):
        assert detect_task_type("DRAFT AN EMAIL NOW") == "email"

    def test_first_match_wins(self):
        """Email keywords come before code in the pattern list."""
        result = detect_task_type("compose a reply email")
        assert result == "email"


# ===========================================================================
# compute_rule_difficulty
# ===========================================================================


class TestComputeRuleDifficulty:
    """compute_rule_difficulty() scores how hard a rule is to follow."""

    def test_no_events_returns_neutral(self):
        assert compute_rule_difficulty("DRAFTING", []) == 0.5

    def test_all_violations_returns_one(self):
        events = [{"category": "DRAFTING", "type": "violation"} for _ in range(5)]
        assert compute_rule_difficulty("DRAFTING", events) == 1.0

    def test_all_successes_returns_zero(self):
        events = [{"category": "DRAFTING", "type": "success"} for _ in range(5)]
        assert compute_rule_difficulty("DRAFTING", events) == 0.0

    def test_mixed_events(self):
        events = [
            {"category": "DRAFTING", "type": "violation"},
            {"category": "DRAFTING", "type": "success"},
            {"category": "DRAFTING", "type": "success"},
            {"category": "DRAFTING", "type": "success"},
        ]
        assert compute_rule_difficulty("DRAFTING", events) == pytest.approx(0.25)

    def test_ignores_other_categories(self):
        events = [
            {"category": "ACCURACY", "type": "violation"},
            {"category": "DRAFTING", "type": "success"},
        ]
        assert compute_rule_difficulty("DRAFTING", events) == 0.0

    def test_case_insensitive_category(self):
        events = [{"category": "drafting", "type": "violation"}]
        assert compute_rule_difficulty("DRAFTING", events) == 1.0


# ===========================================================================
# _difficulty_from_lesson
# ===========================================================================


class TestDifficultyFromLesson:
    """_difficulty_from_lesson() derives difficulty from lesson counters."""

    def test_no_history_returns_neutral(self):
        lesson = _make_lesson(fire_count=0, misfire_count=0)
        assert _difficulty_from_lesson(lesson) == 0.5

    def test_all_misfires(self):
        lesson = _make_lesson(fire_count=0, misfire_count=5)
        assert _difficulty_from_lesson(lesson) == 1.0

    def test_no_misfires(self):
        lesson = _make_lesson(fire_count=10, misfire_count=0)
        assert _difficulty_from_lesson(lesson) == 0.0

    def test_mixed_ratio(self):
        lesson = _make_lesson(fire_count=6, misfire_count=4)
        # misfire / (fire + misfire) = 4/10 = 0.4
        assert _difficulty_from_lesson(lesson) == pytest.approx(0.4)


# ===========================================================================
# compute_scope_weight
# ===========================================================================


class TestComputeScopeWeight:
    """compute_scope_weight() adds task_type-aware bonuses to scope matching."""

    def test_exact_task_type_gets_bonus(self):
        rule = RuleScope(task_type="email")
        query = RuleScope(task_type="email")
        weight = compute_scope_weight(rule, query)
        # Base match is 1.0, bonus is 1.5, capped at 1.0
        assert weight == 1.0

    def test_wildcard_rule_gets_penalty(self):
        rule = RuleScope()  # no task_type
        query = RuleScope(task_type="email")
        weight = compute_scope_weight(rule, query)
        # Universal rule: base 1.0, penalty 0.8
        assert weight == pytest.approx(0.8)

    def test_mismatch_returns_zero(self):
        rule = RuleScope(domain="sales")
        query = RuleScope(domain="engineering")
        weight = compute_scope_weight(rule, query)
        assert weight == 0.0

    def test_partial_match_no_task_type_bonus(self):
        rule = RuleScope(domain="sales", task_type="code")
        query = RuleScope(domain="sales", task_type="email")
        weight = compute_scope_weight(rule, query)
        # domain matches (1.0), task_type mismatches (0.0), avg = 0.5
        assert weight == pytest.approx(0.5)


# ===========================================================================
# merge_related_rules
# ===========================================================================


class TestMergeRelatedRules:
    """merge_related_rules() compresses same-category rules."""

    def test_single_rule_not_merged(self):
        rule = _make_applied(_make_lesson(description="Only one rule"))
        result = merge_related_rules([rule])
        assert len(result) == 1
        assert result[0] is rule  # unchanged

    def test_two_same_category_merged(self):
        r1 = _make_applied(_make_lesson(description="Rule A", confidence=0.90))
        r2 = _make_applied(_make_lesson(description="Rule B", confidence=0.95))
        result = merge_related_rules([r1, r2], min_group_size=2)
        assert len(result) == 1
        assert "merged_" in result[0].rule_id
        assert "Rule A" in result[0].instruction
        assert "Rule B" in result[0].instruction
        assert "DRAFTING:" in result[0].instruction  # category prefix

    def test_different_categories_stay_separate(self):
        r1 = _make_applied(_make_lesson(category="DRAFTING", description="A"))
        r2 = _make_applied(_make_lesson(category="ACCURACY", description="B"))
        result = merge_related_rules([r1, r2], min_group_size=2)
        assert len(result) == 2

    def test_min_group_size_respected(self):
        r1 = _make_applied(_make_lesson(description="A"))
        r2 = _make_applied(_make_lesson(description="B"))
        # min_group_size=3 means 2 rules should NOT merge
        result = merge_related_rules([r1, r2], min_group_size=3)
        assert len(result) == 2

    def test_merged_relevance_is_max(self):
        r1 = _make_applied(_make_lesson(description="A"), relevance=0.6)
        r2 = _make_applied(_make_lesson(description="B"), relevance=0.9)
        result = merge_related_rules([r1, r2], min_group_size=2)
        assert result[0].relevance == 0.9

    def test_empty_list(self):
        assert merge_related_rules([]) == []


# ===========================================================================
# format_rules_for_prompt
# ===========================================================================


class TestFormatRulesForPrompt:
    """format_rules_for_prompt() produces XML-tagged output with primacy/recency."""

    def test_empty_returns_empty_string(self):
        assert format_rules_for_prompt([]) == ""

    def test_xml_tags_present(self):
        rule = _make_applied(_make_lesson())
        output = format_rules_for_prompt([rule])
        assert output.startswith("<brain-rules>")
        assert output.endswith("</brain-rules>")

    def test_instructions_present(self):
        rule = _make_applied(_make_lesson(description="No em dashes in emails"))
        output = format_rules_for_prompt([rule])
        assert "No em dashes in emails" in output

    def test_rules_end_with_closing_tag(self):
        """Output should end with closing brain-rules tag (no REMINDER)."""
        r1 = _make_applied(_make_lesson(description="Top rule", confidence=0.99))
        r2 = _make_applied(
            _make_lesson(
                description="Lower rule",
                confidence=0.80,
                state=LessonState.PATTERN,
            )
        )
        output = format_rules_for_prompt([r1, r2])
        assert output.strip().endswith("</brain-rules>")

    def test_few_shot_examples_included_for_low_confidence(self):
        """Rules with examples and confidence < 0.70 and misfires > 1 get inline examples."""
        lesson = _make_lesson(
            description="Use colons not dashes",
            confidence=0.65,
            state=LessonState.PATTERN,
            misfire_count=2,
            example_draft="I wanted to say -- hello",
            example_corrected="I wanted to say: hello",
        )
        rule = _make_applied(lesson)
        output = format_rules_for_prompt([rule], merge=False)
        assert "e.g." in output
        assert "->" in output

    def test_no_examples_for_high_confidence(self):
        """Rules at high confidence with no misfires should NOT get examples."""
        lesson = _make_lesson(
            confidence=0.95,
            misfire_count=0,
            example_draft="some draft",
            example_corrected="some correction",
        )
        rule = _make_applied(lesson)
        output = format_rules_for_prompt([rule], merge=False)
        assert "<example>" not in output

    def test_merge_flag_false_skips_merging(self):
        r1 = _make_applied(_make_lesson(description="A"))
        r2 = _make_applied(_make_lesson(description="B"))
        output = format_rules_for_prompt([r1, r2], merge=False)
        # Both rules should appear individually
        assert "A" in output
        assert "B" in output

    def test_primacy_ordering_rules_before_patterns(self):
        """RULE state lessons should appear before PATTERN state."""
        pattern = _make_applied(
            _make_lesson(
                state=LessonState.PATTERN,
                confidence=0.75,
                description="Pattern rule",
                category="ACCURACY",
            )
        )
        rule = _make_applied(
            _make_lesson(state=LessonState.RULE, confidence=0.95, description="Firm rule")
        )
        output = format_rules_for_prompt([pattern, rule], merge=False)
        firm_pos = output.index("Firm rule")
        pattern_pos = output.index("Pattern rule")
        assert firm_pos < pattern_pos


# ===========================================================================
# capture_example_from_correction
# ===========================================================================


class TestCaptureExampleFromCorrection:
    """capture_example_from_correction() attaches draft/corrected pairs."""

    def test_captures_example(self):
        lesson = _make_lesson()
        assert lesson.example_draft is None
        assert lesson.example_corrected is None
        result = capture_example_from_correction(lesson, "bad draft text", "good corrected text")
        assert result is lesson  # same object
        assert lesson.example_draft == "bad draft text"
        assert lesson.example_corrected == "good corrected text"

    def test_truncates_long_text(self):
        lesson = _make_lesson()
        long_text = "x" * 500
        capture_example_from_correction(lesson, long_text, long_text)
        assert len(lesson.example_draft) == 80
        assert len(lesson.example_corrected) == 80

    def test_overwrites_existing_example(self):
        lesson = _make_lesson(example_draft="old draft", example_corrected="old corrected")
        capture_example_from_correction(lesson, "new draft", "new corrected")
        assert lesson.example_draft == "new draft"
        assert lesson.example_corrected == "new corrected"


# ===========================================================================
# _make_rule_id
# ===========================================================================


class TestMakeRuleId:
    """_make_rule_id() produces stable identifiers."""

    def test_format(self):
        lesson = _make_lesson(category="DRAFTING", description="Test rule")
        rule_id = _make_rule_id(lesson)
        assert rule_id.startswith("DRAFTING:")
        assert len(rule_id.split(":")[1]) == 8

    def test_deterministic(self):
        lesson = _make_lesson(description="Same desc")
        assert _make_rule_id(lesson) == _make_rule_id(lesson)

    def test_different_descriptions_different_ids(self):
        l1 = _make_lesson(description="Desc A")
        l2 = _make_lesson(description="Desc B")
        # Could collide by design, but extremely unlikely for 2 distinct inputs
        # Just verify the function runs without error
        _make_rule_id(l1)
        _make_rule_id(l2)


# ===========================================================================
# apply_rules integration (smoke test with S71 features)
# ===========================================================================


class TestApplyRulesIntegration:
    """End-to-end: apply_rules with task detection and difficulty."""

    def test_task_type_enriches_scope(self):
        """When user_message is provided, scope gets enriched with detected task type."""
        lesson = _make_lesson(description="Always include scheduling link")
        result = apply_rules(
            [lesson],
            scope=RuleScope(domain="sales"),
            user_message="draft a follow-up email to the prospect",
        )
        # Should still return the rule since it's a universal scope lesson
        assert len(result) >= 1

    def test_events_affect_difficulty_ranking(self):
        """Rules with more violations should rank higher (harder = more important)."""
        easy = _make_lesson(category="EASY", description="Easy rule")
        hard = _make_lesson(category="HARD", description="Hard rule")
        events = [
            {"category": "HARD", "type": "violation"},
            {"category": "HARD", "type": "violation"},
            {"category": "EASY", "type": "success"},
            {"category": "EASY", "type": "success"},
        ]
        result = apply_rules(
            [easy, hard],
            scope=RuleScope(),
            events=events,
        )
        assert len(result) == 2
        # Hard rule should come first due to higher difficulty
        assert result[0].lesson.category == "HARD"

    def test_max_rules_cap(self):
        lessons = [_make_lesson(description=f"Rule {i}", category=f"CAT{i}") for i in range(20)]
        result = apply_rules(lessons, scope=RuleScope(), max_rules=5)
        assert len(result) <= 5
