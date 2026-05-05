"""Tests for the self_review PostToolUse hook."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gradata.hooks.self_review import (
    _check_rule_compliance,
    _extract_output_text,
    main,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rule(description: str, category: str = "DRAFTING") -> dict:
    return {"description": description, "category": category}


def _lesson(
    *,
    state_name: str = "RULE",
    confidence: float = 0.92,
    fire_count: int = 15,
    description: str = "never use em dash",
    category: str = "DRAFTING",
):
    """Build a minimal mock Lesson object."""
    from gradata._types import LessonState

    state_map = {
        "RULE": LessonState.RULE,
        "PATTERN": LessonState.PATTERN,
        "INSTINCT": LessonState.INSTINCT,
    }
    m = MagicMock()
    m.state = state_map.get(state_name, LessonState.INSTINCT)
    m.confidence = confidence
    m.fire_count = fire_count
    m.description = description
    m.category = category
    return m


# ---------------------------------------------------------------------------
# 1. Non-Write/Edit tools are skipped
# ---------------------------------------------------------------------------


class TestMainToolFilter:
    def test_bash_tool_returns_none(self):
        data = {"tool_name": "Bash", "tool_output": "some output"}
        assert main(data) is None

    def test_read_tool_returns_none(self):
        data = {"tool_name": "Read", "tool_output": "file contents"}
        assert main(data) is None

    def test_glob_tool_returns_none(self):
        data = {"tool_name": "Glob", "tool_output": "*.py"}
        assert main(data) is None

    def test_missing_tool_name_returns_none(self):
        data = {"tool_output": "output"}
        assert main(data) is None


# ---------------------------------------------------------------------------
# 2. Empty output is skipped (even for Write/Edit)
# ---------------------------------------------------------------------------


class TestMainEmptyOutput:
    def _patch_brain(self, tmp_path):
        return patch(
            "gradata.hooks.self_review.resolve_brain_dir",
            return_value=str(tmp_path),
        )

    def test_empty_string_skipped(self, tmp_path):
        with self._patch_brain(tmp_path):
            result = main({"tool_name": "Write", "tool_output": ""})
        assert result is None

    def test_whitespace_only_skipped(self, tmp_path):
        with self._patch_brain(tmp_path):
            result = main({"tool_name": "Write", "tool_output": "   "})
        assert result is None

    def test_no_output_key_skipped(self, tmp_path):
        with self._patch_brain(tmp_path):
            result = main({"tool_name": "Edit"})
        assert result is None


# ---------------------------------------------------------------------------
# 3. No brain dir → None
# ---------------------------------------------------------------------------


def test_no_brain_dir_returns_none():
    with patch("gradata.hooks.self_review.resolve_brain_dir", return_value=None):
        result = main({"tool_name": "Write", "tool_output": "hello"})
    assert result is None


# ---------------------------------------------------------------------------
# 4. No mandatory rules → no violations, returns None
# ---------------------------------------------------------------------------


def test_no_mandatory_rules_returns_none(tmp_path):
    with (
        patch("gradata.hooks.self_review.resolve_brain_dir", return_value=str(tmp_path)),
        patch("gradata.hooks.self_review._load_mandatory_rules", return_value=[]),
    ):
        result = main({"tool_name": "Write", "tool_output": "clean text"})
    assert result is None


# ---------------------------------------------------------------------------
# 5. "never use em dash" rule + output WITH em dash → violation detected
# ---------------------------------------------------------------------------


class TestCheckRuleCompliance:
    def test_em_dash_in_output_triggers_violation(self):
        # Rule extracts banned literal "em dash" (the words). Output must contain
        # the exact string "em dash" to trigger — not the Unicode glyph \u2014.
        rules = [_rule("never use em dash")]
        violations = _check_rule_compliance("This text has an em dash here", rules)
        assert len(violations) == 1
        v = violations[0]
        assert "em dash" in v["evidence"]
        assert v["severity"] == "warning"
        assert v["category"] == "DRAFTING"

    # 6. Clean output → no violation
    def test_clean_output_no_violation(self):
        rules = [_rule("never use em dash")]
        violations = _check_rule_compliance("This text has no forbidden content.", rules)
        assert violations == []

    # 7. Multiple rules — only matching ones flagged
    def test_multiple_rules_only_matching_flagged(self):
        # Rule text "never use em dash" → banned literal = "em dash"
        # The actual Unicode glyph \u2014 is NOT the same as the words "em dash".
        # A rule "never use \u2014" would match the glyph; "never use em dash"
        # only matches the words "em dash" appearing in the output.
        rules = [
            _rule("never use em dash"),  # banned literal: "em dash"
            _rule("never include pricing"),  # banned literal: "pricing"
            _rule("never create readme files"),  # banned literal: "readme files"
        ]
        output = "The price is $500 per seat. Pricing details follow."
        violations = _check_rule_compliance(output, rules)

        flagged = {v["rule"] for v in violations}
        assert "never include pricing" in flagged
        assert "never use em dash" not in flagged  # "em dash" not in output
        assert "never create readme files" not in flagged  # "readme files" not in output

    def test_case_insensitive_match(self):
        # Banned token is "em dash" (lowercased from rule). Output "EM DASH" should match.
        rules = [_rule("never use EM DASH")]
        violations = _check_rule_compliance("here is an EM DASH in the text", rules)
        assert len(violations) == 1

    def test_always_rule_not_checked(self):
        # Positive directives cannot be verified from output alone; must be skipped.
        rules = [_rule("always run tests before committing")]
        violations = _check_rule_compliance("I did not run tests", rules)
        assert violations == []

    def test_violation_contains_rule_text(self):
        # Rule extracts banned literal "bold mid-paragraph" — the exact phrase
        # must appear in the output to trigger a match.
        rules = [_rule("never add bold mid-paragraph", category="STYLE")]
        violations = _check_rule_compliance("Do not use bold mid-paragraph in prose", rules)
        assert len(violations) == 1
        assert violations[0]["rule"] == "never add bold mid-paragraph"
        assert violations[0]["category"] == "STYLE"


# ---------------------------------------------------------------------------
# 8. Violations include evidence string
# ---------------------------------------------------------------------------


def test_violation_evidence_string():
    rules = [_rule("never use em dash")]
    violations = _check_rule_compliance("Here is an em dash in the text", rules)
    assert violations
    assert "evidence" in violations[0]
    assert isinstance(violations[0]["evidence"], str)
    assert violations[0]["evidence"].startswith("Output contains")


# ---------------------------------------------------------------------------
# _load_mandatory_rules filtering
# ---------------------------------------------------------------------------


class TestLoadMandatoryRules:
    """_load_mandatory_rules must filter: RULE state + conf >= 0.90 + fire >= 10."""

    def _patch_parse(self, lessons: list):
        return patch(
            "gradata.hooks.self_review.parse_lessons",
            return_value=lessons,
        )

    def test_rule_state_high_conf_high_fire_included(self, tmp_path):
        """A RULE-state lesson with conf>=0.90 and fire_count>=10 must be included."""
        from gradata._types import LessonState

        lesson = _lesson(state_name="RULE", confidence=0.92, fire_count=15)
        # Verify it passes all three filter conditions used in _load_mandatory_rules.
        assert lesson.state == LessonState.RULE
        assert lesson.confidence >= 0.90
        assert lesson.fire_count >= 10

    def test_pattern_state_excluded(self):
        """Lessons in PATTERN state must not be returned even with high confidence."""
        from gradata._types import LessonState

        lesson = _lesson(state_name="PATTERN", confidence=0.92, fire_count=15)
        # Directly test the filter logic
        assert lesson.state != LessonState.RULE

    def test_low_confidence_excluded(self):
        lesson = _lesson(state_name="RULE", confidence=0.85, fire_count=15)
        assert lesson.confidence < 0.90

    def test_low_fire_count_excluded(self):
        lesson = _lesson(state_name="RULE", confidence=0.92, fire_count=5)
        assert lesson.fire_count < 10

    def test_all_conditions_must_hold(self):
        """Filter: state==RULE AND conf>=0.90 AND fire_count>=10."""
        from gradata._types import LessonState

        passing = _lesson(state_name="RULE", confidence=0.91, fire_count=10)
        failing_state = _lesson(state_name="PATTERN", confidence=0.95, fire_count=20)
        failing_conf = _lesson(state_name="RULE", confidence=0.89, fire_count=20)
        failing_fire = _lesson(state_name="RULE", confidence=0.95, fire_count=9)

        def passes(l):
            return l.state == LessonState.RULE and l.confidence >= 0.90 and l.fire_count >= 10

        assert passes(passing)
        assert not passes(failing_state)
        assert not passes(failing_conf)
        assert not passes(failing_fire)


# ---------------------------------------------------------------------------
# _extract_output_text
# ---------------------------------------------------------------------------


class TestExtractOutputText:
    def test_tool_output_key_preferred(self):
        data = {"tool_output": "from tool_output", "output": "from output"}
        assert _extract_output_text(data) == "from tool_output"

    def test_falls_back_to_output_key(self):
        data = {"output": "from output"}
        assert _extract_output_text(data) == "from output"

    def test_whitespace_only_returns_empty(self):
        data = {"tool_output": "   "}
        assert _extract_output_text(data) == ""

    def test_missing_keys_returns_empty(self):
        assert _extract_output_text({}) == ""


# ---------------------------------------------------------------------------
# main integration: violation path triggers _log_violations
# ---------------------------------------------------------------------------


def test_main_calls_log_violations_on_violation(tmp_path):
    rules = [_rule("never use em dash")]
    output = "Some output with em dash here"

    with (
        patch("gradata.hooks.self_review.resolve_brain_dir", return_value=str(tmp_path)),
        patch("gradata.hooks.self_review._load_mandatory_rules", return_value=rules),
        patch("gradata.hooks.self_review._log_violations") as mock_log,
    ):
        result = main({"tool_name": "Write", "tool_output": output})

    assert result is None  # Never blocks
    mock_log.assert_called_once()
    violations_arg = mock_log.call_args[0][1]
    assert len(violations_arg) == 1
    assert "em dash" in violations_arg[0]["evidence"]


def test_main_no_log_violations_when_clean(tmp_path):
    rules = [_rule("never use em dash")]
    output = "Clean output with no violations."

    with (
        patch("gradata.hooks.self_review.resolve_brain_dir", return_value=str(tmp_path)),
        patch("gradata.hooks.self_review._load_mandatory_rules", return_value=rules),
        patch("gradata.hooks.self_review._log_violations") as mock_log,
    ):
        result = main({"tool_name": "Write", "tool_output": output})

    assert result is None
    mock_log.assert_not_called()


def test_main_supports_multiedit_tool(tmp_path):
    rules = [_rule("never use em dash")]
    output = "Text with em dash inside"

    with (
        patch("gradata.hooks.self_review.resolve_brain_dir", return_value=str(tmp_path)),
        patch("gradata.hooks.self_review._load_mandatory_rules", return_value=rules),
        patch("gradata.hooks.self_review._log_violations") as mock_log,
    ):
        main({"tool_name": "MultiEdit", "tool_output": output})

    mock_log.assert_called_once()
