"""Tests for constitutional rule formatting (experimental).

Covers format_rule_constitutional() and format_rules_styled() from rule_engine.
"""

from __future__ import annotations

import pytest

from gradata._types import CorrectionType, Lesson, LessonState
from gradata.rules.rule_engine import (
    AppliedRule,
    format_rule_constitutional,
    format_rules_styled,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lesson(
    category: str = "TONE",
    description: str = "Be concise",
    state: LessonState = LessonState.RULE,
    confidence: float = 0.95,
) -> Lesson:
    return Lesson(
        date="2026-04-10",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
    )


def _make_applied(
    category: str = "TONE",
    description: str = "Be concise",
    state: LessonState = LessonState.RULE,
    confidence: float = 0.95,
) -> AppliedRule:
    lesson = _make_lesson(category, description, state, confidence)
    return AppliedRule(
        rule_id=f"{category}:test",
        lesson=lesson,
        relevance=0.9,
        instruction=f"[RULE] {category}: {description}",
    )


# ---------------------------------------------------------------------------
# format_rule_constitutional
# ---------------------------------------------------------------------------


class TestFormatRuleConstitutional:
    def test_basic_transformation(self):
        result = format_rule_constitutional("TONE", "Be concise and direct")
        assert "<principle>" in result
        assert "</principle>" in result
        assert "value" in result.lower()
        assert "concise" in result.lower()

    def test_strips_always_prefix(self):
        result = format_rule_constitutional("ACCURACY", "Always cite sources")
        assert "Always" not in result
        assert "cite sources" in result.lower()

    def test_strips_never_prefix(self):
        result = format_rule_constitutional("FORMAT", "Never use em dashes")
        assert "Never" not in result
        assert "em dashes" in result.lower()

    def test_strips_dont_prefix(self):
        result = format_rule_constitutional("TONE", "Don't be verbose")
        assert "Don't" not in result
        assert "be verbose" in result.lower()

    def test_strips_do_not_prefix(self):
        result = format_rule_constitutional("ACCURACY", "Do not fabricate data")
        assert "Do not" not in result
        assert "fabricate data" in result.lower()

    def test_strips_be_prefix(self):
        result = format_rule_constitutional("TONE", "Be warm and friendly")
        assert result.startswith("<principle>")
        assert "warm and friendly" in result.lower()

    def test_strips_use_prefix(self):
        result = format_rule_constitutional("FORMAT", "Use bullet points")
        assert "Use " not in result.split("—")[1]
        assert "bullet points" in result.lower()

    def test_strips_avoid_prefix(self):
        result = format_rule_constitutional("DRAFTING", "Avoid passive voice")
        assert "Avoid " not in result.split("—")[1]
        assert "passive voice" in result.lower()

    def test_no_prefix_preserved(self):
        result = format_rule_constitutional("ACCURACY", "Check facts before publishing")
        assert "check facts before publishing" in result.lower()

    def test_category_tone(self):
        result = format_rule_constitutional("TONE", "Be warm")
        assert "communication style" in result

    def test_category_accuracy(self):
        result = format_rule_constitutional("ACCURACY", "Check facts")
        assert "accuracy and precision" in result

    def test_category_structure(self):
        result = format_rule_constitutional("STRUCTURE", "Use headers")
        assert "clear organization" in result

    def test_category_drafting(self):
        result = format_rule_constitutional("DRAFTING", "Be polished")
        assert "polished writing" in result

    def test_category_format(self):
        result = format_rule_constitutional("FORMAT", "Use markdown")
        assert "the user's formatting preferences" in result

    def test_category_security(self):
        result = format_rule_constitutional("SECURITY", "Never expose secrets")
        assert "security and safety" in result

    def test_unknown_category_defaults_to_quality(self):
        result = format_rule_constitutional("UNKNOWN", "Do something")
        assert "quality" in result

    def test_case_insensitive_category(self):
        result = format_rule_constitutional("tone", "Be warm")
        assert "communication style" in result

    def test_description_lowercased(self):
        result = format_rule_constitutional("TONE", "Always Use Proper Nouns")
        # After stripping "Always ", remainder is lowercased
        assert "use proper nouns" in result

    def test_whitespace_stripped(self):
        result = format_rule_constitutional("TONE", "  Be concise  ")
        assert "<principle>" in result
        assert "concise" in result.lower()

    def test_only_first_prefix_stripped(self):
        # "Always avoid X" -> strips "Always ", not "Avoid "
        result = format_rule_constitutional("TONE", "Always avoid jargon")
        assert "Always" not in result
        assert "avoid jargon" in result.lower()


# ---------------------------------------------------------------------------
# format_rules_styled
# ---------------------------------------------------------------------------


class TestFormatRulesStyled:
    def test_empty_rules(self):
        assert format_rules_styled([]) == ""

    def test_imperative_default(self):
        rules = [
            _make_applied("TONE", "Be concise"),
            _make_applied("ACCURACY", "Always cite sources"),
        ]
        result = format_rules_styled(rules)
        assert "[RULE] TONE: Be concise" in result
        assert "[RULE] ACCURACY: Always cite sources" in result
        assert "<principle>" not in result

    def test_imperative_explicit(self):
        rules = [_make_applied("TONE", "Be concise")]
        result = format_rules_styled(rules, format_style="imperative")
        assert "[RULE] TONE: Be concise" in result

    def test_constitutional_format(self):
        rules = [
            _make_applied("TONE", "Be concise"),
            _make_applied("ACCURACY", "Always cite sources"),
        ]
        result = format_rules_styled(rules, format_style="constitutional")
        assert "<principle>" in result
        assert "communication style" in result
        assert "accuracy and precision" in result
        assert "[RULE]" not in result

    def test_constitutional_strips_prefixes(self):
        rules = [_make_applied("FORMAT", "Never use em dashes")]
        result = format_rules_styled(rules, format_style="constitutional")
        assert "Never" not in result
        assert "em dashes" in result.lower()

    def test_constitutional_multiple_rules_newline_separated(self):
        rules = [
            _make_applied("TONE", "Be concise"),
            _make_applied("ACCURACY", "Check facts"),
        ]
        result = format_rules_styled(rules, format_style="constitutional")
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert all(line.startswith("<principle>") for line in lines)

    def test_unknown_style_falls_back_to_imperative(self):
        rules = [_make_applied("TONE", "Be concise")]
        result = format_rules_styled(rules, format_style="unknown_style")
        # Falls through to else branch (imperative)
        assert "[RULE] TONE: Be concise" in result

    def test_does_not_change_default_format(self):
        """Verify that omitting format_style gives imperative (not constitutional)."""
        rules = [_make_applied("TONE", "Be concise")]
        result = format_rules_styled(rules)
        assert "<principle>" not in result
        assert "[RULE]" in result
