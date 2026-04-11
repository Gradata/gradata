"""Tests for score obfuscation — Security Task 1."""

from __future__ import annotations

import pytest

import time

from gradata.security.score_obfuscation import (
    _SCORE_PATTERN,
    constant_time_pad,
    obfuscate_instruction,
    truncate_score,
)


# ---------------------------------------------------------------------------
# truncate_score
# ---------------------------------------------------------------------------


class TestTruncateScore:
    """Verify tier label mapping for all confidence ranges."""

    def test_rule_tier_above_threshold(self) -> None:
        assert truncate_score(0.95) == "RULE"

    def test_rule_tier_at_boundary(self) -> None:
        assert truncate_score(0.90) == "RULE"

    def test_rule_tier_at_1(self) -> None:
        assert truncate_score(1.0) == "RULE"

    def test_pattern_tier_mid_range(self) -> None:
        assert truncate_score(0.75) == "PATTERN"

    def test_pattern_tier_at_boundary(self) -> None:
        assert truncate_score(0.60) == "PATTERN"

    def test_pattern_tier_just_below_rule(self) -> None:
        assert truncate_score(0.89) == "PATTERN"

    def test_instinct_tier_below_pattern(self) -> None:
        assert truncate_score(0.59) == "INSTINCT"

    def test_instinct_tier_at_zero(self) -> None:
        assert truncate_score(0.0) == "INSTINCT"

    def test_instinct_tier_low(self) -> None:
        assert truncate_score(0.40) == "INSTINCT"


# ---------------------------------------------------------------------------
# obfuscate_instruction
# ---------------------------------------------------------------------------


class TestObfuscateInstruction:
    """Verify float stripping from instruction strings."""

    def test_strips_rule_float(self) -> None:
        assert obfuscate_instruction("[RULE:0.95] DRAFTING: foo") == "[RULE] DRAFTING: foo"

    def test_strips_pattern_float(self) -> None:
        assert obfuscate_instruction("[PATTERN:0.72] CODE: bar") == "[PATTERN] CODE: bar"

    def test_strips_instinct_float(self) -> None:
        assert obfuscate_instruction("[INSTINCT:0.40] MISC: baz") == "[INSTINCT] MISC: baz"

    def test_passthrough_no_brackets(self) -> None:
        text = "Just a plain instruction with no brackets"
        assert obfuscate_instruction(text) == text

    def test_passthrough_empty_string(self) -> None:
        assert obfuscate_instruction("") == ""

    def test_multiple_scores_in_one_string(self) -> None:
        text = "[RULE:0.95] foo [PATTERN:0.60] bar"
        assert obfuscate_instruction(text) == "[RULE] foo [PATTERN] bar"

    def test_preserves_surrounding_text(self) -> None:
        text = "prefix [RULE:0.91] middle [PATTERN:0.65] suffix"
        assert obfuscate_instruction(text) == "prefix [RULE] middle [PATTERN] suffix"

    def test_does_not_strip_unknown_labels(self) -> None:
        text = "[UNKNOWN:0.50] something"
        assert obfuscate_instruction(text) == "[UNKNOWN:0.50] something"


# ---------------------------------------------------------------------------
# _SCORE_PATTERN regex
# ---------------------------------------------------------------------------


class TestScorePattern:
    """Verify the regex matches expected formats."""

    def test_matches_rule(self) -> None:
        assert _SCORE_PATTERN.search("[RULE:0.95]") is not None

    def test_matches_pattern(self) -> None:
        assert _SCORE_PATTERN.search("[PATTERN:0.60]") is not None

    def test_matches_instinct(self) -> None:
        assert _SCORE_PATTERN.search("[INSTINCT:0.40]") is not None

    def test_no_match_without_float(self) -> None:
        assert _SCORE_PATTERN.search("[RULE]") is None

    def test_no_match_lowercase(self) -> None:
        assert _SCORE_PATTERN.search("[rule:0.95]") is None


# ---------------------------------------------------------------------------
# Integration: format_rules_for_prompt output
# ---------------------------------------------------------------------------


class TestFormatRulesNoRawFloats:
    """Verify that format_rules_for_prompt output contains no raw floats."""

    def test_no_raw_floats_in_prompt(self) -> None:
        """After the rule_engine change, format_rules_for_prompt should
        emit tier labels without confidence floats in the instruction field."""
        from gradata._types import Lesson, LessonState
        from gradata.rules.rule_engine import apply_rules, format_rules_for_prompt
        from gradata._scope import RuleScope

        lesson = Lesson(
            date="2026-04-07",
            category="DRAFTING",
            description="Always include pricing",
            state=LessonState.RULE,
            confidence=0.95,
        )
        scope = RuleScope()
        applied = apply_rules([lesson], scope)
        prompt = format_rules_for_prompt(applied)

        # Should NOT contain patterns like :0.95] — raw floats after colon
        assert _SCORE_PATTERN.search(prompt) is None, f"Raw float leaked into prompt: {prompt}"
        # Should contain the category (tier labels removed for conciseness)
        assert "DRAFTING:" in prompt


# ---------------------------------------------------------------------------
# constant_time_pad
# ---------------------------------------------------------------------------


class TestConstantTimePad:
    """Verify timing-attack defense via constant_time_pad."""

    def test_padded_takes_at_least_min_ms(self) -> None:
        """Padded function should take at least min_ms milliseconds."""
        min_ms = 30.0
        start = time.perf_counter()
        constant_time_pad(lambda: 42, min_ms=min_ms, jitter_ms=0.0)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms >= min_ms * 0.95, (
            f"Expected >= {min_ms * 0.95:.1f}ms, got {elapsed_ms:.1f}ms"
        )

    def test_returns_function_result(self) -> None:
        """Should return whatever fn() returns."""
        result = constant_time_pad(lambda: "hello", min_ms=5.0, jitter_ms=0.0)
        assert result == "hello"

    def test_returns_none_from_void_fn(self) -> None:
        result = constant_time_pad(lambda: None, min_ms=5.0, jitter_ms=0.0)
        assert result is None

    def test_jitter_adds_variance(self) -> None:
        """With jitter, not all durations should be identical."""
        durations: list[float] = []
        for _ in range(10):
            start = time.perf_counter()
            constant_time_pad(lambda: 1, min_ms=5.0, jitter_ms=10.0)
            durations.append((time.perf_counter() - start) * 1000)
        # With 10ms jitter range over 10 runs, we expect some variance
        assert max(durations) - min(durations) > 0.5, (
            f"Expected timing variance from jitter, got spread "
            f"{max(durations) - min(durations):.2f}ms"
        )
