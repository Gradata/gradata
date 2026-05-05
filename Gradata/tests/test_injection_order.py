"""Tests for bucketed shuffle injection order — Security Task 4."""

from __future__ import annotations

import re

from gradata._types import Lesson, LessonState
from gradata.rules.rule_engine import AppliedRule, _make_rule_id, format_rules_for_prompt
from gradata.security.score_obfuscation import truncate_score


def _make_applied(category: str, state: LessonState, confidence: float) -> AppliedRule:
    """Helper to build an AppliedRule for testing."""
    lesson = Lesson(
        date="2026-04-07",
        category=category,
        description=f"{category} rule at {confidence}",
        state=state,
        confidence=confidence,
    )
    tier = truncate_score(confidence)
    return AppliedRule(
        rule_id=_make_rule_id(lesson),
        lesson=lesson,
        relevance=0.9,
        instruction=f"[{tier}] {category}: {lesson.description}",
    )


# ---------------------------------------------------------------------------
# Tier ordering
# ---------------------------------------------------------------------------


class TestTierOrdering:
    """RULE tier before PATTERN, PATTERN before INSTINCT."""

    def test_rule_before_pattern(self) -> None:
        rules = [
            _make_applied("PATTERN_CAT", LessonState.PATTERN, 0.75),
            _make_applied("RULE_CAT", LessonState.RULE, 0.95),
        ]
        prompt = format_rules_for_prompt(rules, merge=False, shuffle_seed=42)
        rule_pos = prompt.index("[RULE]")
        pattern_pos = prompt.index("[PATTERN]")
        assert rule_pos < pattern_pos

    def test_pattern_before_instinct(self) -> None:
        rules = [
            _make_applied("INSTINCT_CAT", LessonState.INSTINCT, 0.40),
            _make_applied("PATTERN_CAT", LessonState.PATTERN, 0.70),
        ]
        prompt = format_rules_for_prompt(rules, merge=False, shuffle_seed=42)
        pattern_pos = prompt.index("[PATTERN]")
        instinct_pos = prompt.index("[INSTINCT]")
        assert pattern_pos < instinct_pos

    def test_all_three_tiers_ordered(self) -> None:
        rules = [
            _make_applied("I", LessonState.INSTINCT, 0.35),
            _make_applied("P", LessonState.PATTERN, 0.65),
            _make_applied("R", LessonState.RULE, 0.92),
        ]
        prompt = format_rules_for_prompt(rules, merge=False, shuffle_seed=1)
        rule_pos = prompt.index("[RULE]")
        pattern_pos = prompt.index("[PATTERN]")
        instinct_pos = prompt.index("[INSTINCT]")
        assert rule_pos < pattern_pos < instinct_pos


# ---------------------------------------------------------------------------
# Within-tier shuffle varies with seed
# ---------------------------------------------------------------------------


class TestWithinTierShuffle:
    """Within-tier order should vary across different seeds."""

    def test_different_seeds_different_order(self) -> None:
        rules = [_make_applied(f"R{i}", LessonState.RULE, 0.90 + i * 0.01) for i in range(5)]
        orders: set[tuple[str, ...]] = set()
        for seed in range(20):
            prompt = format_rules_for_prompt(
                list(rules),
                merge=False,
                shuffle_seed=seed,
            )
            # Extract rule categories in order from the prompt
            cats = re.findall(r"\[RULE\] (R\d):", prompt)
            orders.add(tuple(cats))
        # With 5 items and 20 seeds, we should see more than one ordering
        assert len(orders) > 1, "Expected different orderings across seeds"

    def test_same_seed_same_order(self) -> None:
        rules = [_make_applied(f"R{i}", LessonState.RULE, 0.90 + i * 0.01) for i in range(5)]
        prompt1 = format_rules_for_prompt(list(rules), merge=False, shuffle_seed=99)
        prompt2 = format_rules_for_prompt(list(rules), merge=False, shuffle_seed=99)
        assert prompt1 == prompt2


# ---------------------------------------------------------------------------
# All rules present after shuffle
# ---------------------------------------------------------------------------


class TestAllRulesPresent:
    """Every rule must appear in the output regardless of shuffle."""

    def test_all_rules_present(self) -> None:
        cats = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO"]
        rules = [_make_applied(c, LessonState.RULE, 0.95) for c in cats]
        prompt = format_rules_for_prompt(rules, merge=False, shuffle_seed=7)
        for cat in cats:
            assert cat in prompt, f"Missing rule category {cat} in output"

    def test_mixed_tiers_all_present(self) -> None:
        rules = [
            _make_applied("R1", LessonState.RULE, 0.95),
            _make_applied("R2", LessonState.RULE, 0.92),
            _make_applied("P1", LessonState.PATTERN, 0.75),
            _make_applied("P2", LessonState.PATTERN, 0.68),
            _make_applied("I1", LessonState.INSTINCT, 0.40),
        ]
        prompt = format_rules_for_prompt(rules, merge=False, shuffle_seed=3)
        for r in rules:
            assert r.lesson.category in prompt

    def test_empty_rules_returns_empty(self) -> None:
        assert format_rules_for_prompt([], shuffle_seed=42) == ""
