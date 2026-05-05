"""
Tests for synthesize_meta_rules_agentic() — Feature 5 of the Gradata
Behavioral Engine. Covers all 10 specified test cases.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gradata._types import Lesson, LessonState
from gradata.enhancements.meta_rules import (
    MetaRule,
    SynthesisEvidence,
    _gather_correction_history,
    _gather_graduated_rules,
    _group_rules_by_category,
    _validate_citations,
    synthesize_meta_rules_agentic,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_lesson(
    category: str,
    description: str,
    confidence: float = 0.92,
    state: LessonState = LessonState.RULE,
) -> Lesson:
    """Build a minimal Lesson for testing."""
    return Lesson(
        date="2026-01-01",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
    )


def _make_rule_group(category: str, n: int = 3, confidence: float = 0.92) -> list[Lesson]:
    """Return n RULE-state lessons in the same category."""
    return [
        _make_lesson(category, f"Rule {i} for {category}", confidence=confidence) for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Test 1: Empty lessons returns empty list
# ---------------------------------------------------------------------------


def test_empty_lessons_returns_empty():
    result = synthesize_meta_rules_agentic(lessons=[])
    assert result == []


# ---------------------------------------------------------------------------
# Test 2: Too few graduated rules returns empty (evidence guardrail)
# ---------------------------------------------------------------------------


def test_too_few_graduated_rules_returns_empty():
    # Only 2 lessons qualify — need MIN_SOURCE_RULES (3)
    lessons = _make_rule_group("DRAFTING", n=2)
    result = synthesize_meta_rules_agentic(lessons=lessons, min_group_size=3)
    assert result == []


# ---------------------------------------------------------------------------
# Test 3: Rules below min_confidence are filtered out
# ---------------------------------------------------------------------------


def test_low_confidence_rules_filtered():
    # 3 RULE-state lessons but confidence < 0.90
    lessons = _make_rule_group("DRAFTING", n=3, confidence=0.85)
    result = synthesize_meta_rules_agentic(lessons=lessons, min_confidence=0.90)
    assert result == []


def test_mixed_confidence_only_high_qualify():
    # 2 high-confidence + 3 low-confidence — only 2 qualify, not enough for a group
    high = _make_rule_group("ACCURACY", n=2, confidence=0.95)
    low = _make_rule_group("ACCURACY", n=3, confidence=0.85)
    result = synthesize_meta_rules_agentic(
        lessons=high + low, min_confidence=0.90, min_group_size=3
    )
    assert result == []


# ---------------------------------------------------------------------------
# Test 4: Groups below min_group_size are skipped
# ---------------------------------------------------------------------------


def test_group_below_min_size_skipped():
    # One category has 3 qualifying rules, another only 2
    qualifying = _make_rule_group("PROCESS", n=3, confidence=0.92)
    too_small = _make_rule_group("TONE", n=2, confidence=0.92)
    result = synthesize_meta_rules_agentic(lessons=qualifying + too_small, min_group_size=3)
    # Only PROCESS should produce a meta-rule
    assert len(result) == 1
    assert result[0].source_categories == ["PROCESS"]


# ---------------------------------------------------------------------------
# Test 5: Successful synthesis with 3+ rules in same category produces MetaRule
# ---------------------------------------------------------------------------


def test_successful_synthesis_produces_meta_rule():
    lessons = _make_rule_group("DRAFTING", n=3, confidence=0.92)
    result = synthesize_meta_rules_agentic(lessons=lessons)

    assert len(result) == 1
    meta = result[0]
    assert isinstance(meta, MetaRule)
    assert meta.id.startswith("META-")
    assert meta.source == "deterministic"
    assert meta.confidence > 0.0
    assert len(meta.source_lesson_ids) == 3
    assert meta.source_categories == ["DRAFTING"]


# ---------------------------------------------------------------------------
# Test 6: Citation validation removes unknown rule IDs
# ---------------------------------------------------------------------------


def test_validate_citations_removes_unknown():
    available = {"abc123", "def456", "ghi789"}
    source_ids = ["abc123", "zzz999", "def456", "qqq000"]
    result = _validate_citations(source_ids, available)
    assert result == ["abc123", "def456"]


def test_validate_citations_all_valid():
    available = {"a", "b", "c"}
    assert _validate_citations(["a", "b", "c"], available) == ["a", "b", "c"]


def test_validate_citations_none_valid():
    available = {"x", "y"}
    assert _validate_citations(["a", "b", "c"], available) == []


# ---------------------------------------------------------------------------
# Test 7: Deduplication — existing meta-rule ID skipped
# ---------------------------------------------------------------------------


def test_deduplication_skips_existing_meta():
    lessons = _make_rule_group("ACCURACY", n=3, confidence=0.92)

    # Run once to get the real ID
    first_pass = synthesize_meta_rules_agentic(lessons=lessons)
    assert len(first_pass) == 1
    existing_id = first_pass[0].id

    # Fabricate a MetaRule with that ID as existing
    existing_meta = MetaRule(
        id=existing_id,
        principle="already exists",
        source_categories=["ACCURACY"],
        source_lesson_ids=first_pass[0].source_lesson_ids,
        confidence=0.92,
        created_session=0,
        last_validated_session=0,
    )

    second_pass = synthesize_meta_rules_agentic(
        lessons=lessons,
        existing_metas=[existing_meta],
    )
    assert second_pass == []


# ---------------------------------------------------------------------------
# Test 8: Max iterations cap is respected
# ---------------------------------------------------------------------------


def test_max_iterations_cap():
    # Create 5 categories with 3 rules each — would normally produce 5 meta-rules
    all_lessons: list[Lesson] = []
    for cat in ["CAT_A", "CAT_B", "CAT_C", "CAT_D", "CAT_E"]:
        all_lessons.extend(_make_rule_group(cat, n=3, confidence=0.92))

    # 3 forced phases use iterations 1-3, so with max_iterations=4,
    # only 1 free iteration is available (iteration 4 triggers the break
    # before the second category is processed — >=4 check fires after first)
    result = synthesize_meta_rules_agentic(lessons=all_lessons, max_iterations=4)
    # Should produce at most 1 meta-rule (first free iteration)
    assert len(result) <= 1


def test_max_iterations_zero_groups():
    # max_iterations=3 means all 3 forced phases exhaust the budget;
    # the free loop should not execute at all
    lessons = _make_rule_group("DRAFTING", n=3, confidence=0.92)
    result = synthesize_meta_rules_agentic(lessons=lessons, max_iterations=3)
    assert result == []


# ---------------------------------------------------------------------------
# Test 9: Multiple categories produce multiple meta-rules
# ---------------------------------------------------------------------------


def test_multiple_categories_produce_multiple_metas():
    lessons = (
        _make_rule_group("DRAFTING", n=3, confidence=0.92)
        + _make_rule_group("ACCURACY", n=4, confidence=0.95)
        + _make_rule_group("PROCESS", n=3, confidence=0.91)
    )
    result = synthesize_meta_rules_agentic(lessons=lessons)

    assert len(result) == 3
    cats = {m.source_categories[0] for m in result}
    assert cats == {"DRAFTING", "ACCURACY", "PROCESS"}


# ---------------------------------------------------------------------------
# Test 10: Principle text includes rule descriptions
# ---------------------------------------------------------------------------


def test_principle_includes_descriptions():
    lessons = [
        _make_lesson("TONE", "Use short sentences", confidence=0.92),
        _make_lesson("TONE", "Avoid em dashes", confidence=0.93),
        _make_lesson("TONE", "Lead with value", confidence=0.91),
    ]
    result = synthesize_meta_rules_agentic(lessons=lessons)

    assert len(result) == 1
    principle = result[0].principle
    assert "Use short sentences" in principle
    assert "Avoid em dashes" in principle
    assert "Lead with value" in principle


def test_principle_truncates_long_description_list():
    # More than 5 rules in a category — principle should note the overflow
    lessons = _make_rule_group("DRAFTING", n=8, confidence=0.92)
    result = synthesize_meta_rules_agentic(lessons=lessons)

    assert len(result) == 1
    assert "and 3 more" in result[0].principle


# ---------------------------------------------------------------------------
# Additional: helper unit tests
# ---------------------------------------------------------------------------


def test_gather_graduated_rules_filters_state_and_confidence():
    rule = _make_lesson("X", "A rule", confidence=0.95, state=LessonState.RULE)
    pattern = _make_lesson("X", "A pattern", confidence=0.95, state=LessonState.PATTERN)
    low_conf = _make_lesson("X", "Low conf rule", confidence=0.80, state=LessonState.RULE)

    result = _gather_graduated_rules([rule, pattern, low_conf], min_confidence=0.90)
    assert result == [rule]


def test_gather_correction_history_shape():
    lessons = _make_rule_group("PROCESS", n=2, confidence=0.92)
    history = _gather_correction_history(lessons)
    assert len(history) == 2
    for entry in history:
        assert "rule_id" in entry
        assert "category" in entry
        assert "confidence" in entry


def test_group_rules_by_category_respects_min_size():
    big = _make_rule_group("BIG", n=4, confidence=0.92)
    small = _make_rule_group("SMALL", n=2, confidence=0.92)
    groups = _group_rules_by_category(big + small, min_group_size=3)
    assert "BIG" in groups
    assert "SMALL" not in groups


def test_synthesis_evidence_defaults():
    ev = SynthesisEvidence()
    assert ev.graduated_rules == []
    assert ev.correction_history == []
    assert ev.existing_meta_rules == []
    assert ev.rule_ids_retrieved == set()
    assert ev.iteration == 0


def test_non_rule_state_lessons_excluded():
    """INSTINCT and PATTERN lessons must not contribute to synthesis."""
    instinct = _make_lesson(
        "DRAFTING", "Instinct lesson", confidence=0.92, state=LessonState.INSTINCT
    )
    pattern = _make_lesson("DRAFTING", "Pattern lesson", confidence=0.92, state=LessonState.PATTERN)
    # Add 3 genuine RULE-state so total would qualify if state check is broken
    rules = _make_rule_group("DRAFTING", n=3, confidence=0.92)

    result_with_noise = synthesize_meta_rules_agentic(lessons=[*rules, instinct, pattern])
    result_clean = synthesize_meta_rules_agentic(lessons=rules)

    # Both runs should produce exactly 1 meta-rule with the same 3 source IDs
    assert len(result_with_noise) == 1
    assert len(result_clean) == 1
    assert set(result_with_noise[0].source_lesson_ids) == set(result_clean[0].source_lesson_ids)


# ---------------------------------------------------------------------------
# LLM principle wiring
# ---------------------------------------------------------------------------


def test_llm_principle_used_when_synthesizer_returns_string(monkeypatch):
    """When LLM synthesis succeeds, principle uses LLM text and source=llm_synth."""
    import gradata.enhancements.meta_rules as mr

    monkeypatch.setattr(
        mr,
        "_try_llm_principle",
        lambda rules, category, creds=None: (
            "When drafting, lead with the benefit, not the feature."
        ),
    )
    lessons = _make_rule_group("DRAFTING", n=3, confidence=0.92)
    result = synthesize_meta_rules_agentic(lessons=lessons)

    assert len(result) == 1
    assert result[0].source == "llm_synth"
    assert result[0].principle == "When drafting, lead with the benefit, not the feature."


def test_llm_principle_falls_back_to_deterministic_on_none(monkeypatch):
    """When LLM returns None (no creds or failure), deterministic path runs."""
    import gradata.enhancements.meta_rules as mr

    monkeypatch.setattr(mr, "_try_llm_principle", lambda rules, category, creds=None: None)
    lessons = _make_rule_group("DRAFTING", n=3, confidence=0.92)
    result = synthesize_meta_rules_agentic(lessons=lessons)

    assert len(result) == 1
    assert result[0].source == "deterministic"
    assert "Across 3 corrections in DRAFTING" in result[0].principle


def test_try_llm_principle_returns_none_without_creds(monkeypatch):
    """_try_llm_principle degrades silently when no credentials configured."""
    import gradata.enhancements.meta_rules as mr

    monkeypatch.delenv("GRADATA_LLM_KEY", raising=False)
    monkeypatch.delenv("GRADATA_LLM_BASE", raising=False)
    monkeypatch.delenv("GRADATA_GEMMA_API_KEY", raising=False)
    monkeypatch.delenv("GRADATA_GEMMA_BASE", raising=False)

    rules = _make_rule_group("DRAFTING", n=3)
    assert mr._try_llm_principle(rules, "DRAFTING") is None
