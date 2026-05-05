"""Tests for llm_synthesize_rules() in meta_rules.py."""

from __future__ import annotations

from unittest.mock import patch

from gradata._types import Lesson, LessonState
from gradata.enhancements.meta_rules import llm_synthesize_rules

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Fake credentials so _resolve_llm_credentials passes the early check
_FAKE_CREDS = ("fake-key", "https://fake.api", "test-model")


def _make_lesson(
    category: str = "TONE",
    description: str = "Keep it casual",
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


def _fake_llm_response(directives: list[dict]) -> str:
    """Return JSON string the LLM would produce."""
    import json

    return json.dumps(directives)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLLMSynthesis:
    """Test suite for llm_synthesize_rules."""

    def test_filters_to_rule_state_only(self):
        """Only RULE lessons passed to synthesis, not PATTERN/INSTINCT."""
        lessons = [
            _make_lesson(state=LessonState.RULE, category="TONE", description="Be casual"),
            _make_lesson(state=LessonState.PATTERN, category="TONE", description="Be warm"),
            _make_lesson(state=LessonState.INSTINCT, category="TONE", description="Be fun"),
        ]

        mock_response = _fake_llm_response(
            [{"directive": "Use a warm casual tone", "confidence": 0.9}]
        )

        with (
            patch(
                "gradata.enhancements.meta_rules._resolve_llm_credentials",
                return_value=_FAKE_CREDS,
            ),
            patch(
                "gradata.enhancements.meta_rules._call_llm_for_synthesis",
                return_value=mock_response,
            ),
        ):
            result = llm_synthesize_rules(lessons, provider="anthropic", max_calls=1)

        assert isinstance(result, list)
        # Only 1 RULE lesson ("Be casual") should be in source_lessons
        for item in result:
            for src in item["source_lessons"]:
                assert src == "Be casual"

    def test_groups_by_category(self):
        """TONE rules grouped together, ACCURACY separately."""
        lessons = [
            _make_lesson(state=LessonState.RULE, category="TONE", description="Be casual"),
            _make_lesson(state=LessonState.RULE, category="TONE", description="Be warm"),
            _make_lesson(state=LessonState.RULE, category="ACCURACY", description="Verify data"),
        ]

        call_categories: list[str] = []

        def fake_call(category: str, descriptions: list[str], **kwargs) -> str:
            call_categories.append(category)
            return _fake_llm_response(
                [{"directive": f"Directive for {category}", "confidence": 0.85}]
            )

        with (
            patch(
                "gradata.enhancements.meta_rules._resolve_llm_credentials",
                return_value=_FAKE_CREDS,
            ),
            patch(
                "gradata.enhancements.meta_rules._call_llm_for_synthesis",
                side_effect=fake_call,
            ),
        ):
            result = llm_synthesize_rules(lessons, provider="anthropic", max_calls=5)

        assert "TONE" in call_categories
        assert "ACCURACY" in call_categories
        assert len(result) >= 2

    def test_returns_empty_on_no_api_key(self):
        """Graceful fallback when no credentials are available."""
        lessons = [
            _make_lesson(state=LessonState.RULE, category="TONE", description="Be casual"),
        ]

        # Return empty credentials
        with patch(
            "gradata.enhancements.meta_rules._resolve_llm_credentials",
            return_value=("", "", ""),
        ):
            result = llm_synthesize_rules(lessons, provider="anthropic", max_calls=1)

        assert result == []

    def test_max_calls_respected(self):
        """With max_calls=1, only one category group synthesized."""
        lessons = [
            _make_lesson(state=LessonState.RULE, category="TONE", description="Be casual"),
            _make_lesson(state=LessonState.RULE, category="TONE", description="Be warm"),
            _make_lesson(state=LessonState.RULE, category="ACCURACY", description="Verify data"),
            _make_lesson(state=LessonState.RULE, category="PROCESS", description="Check twice"),
        ]

        call_count = 0

        def fake_call(category: str, descriptions: list[str], **kwargs) -> str:
            nonlocal call_count
            call_count += 1
            return _fake_llm_response(
                [{"directive": f"Directive for {category}", "confidence": 0.85}]
            )

        with (
            patch(
                "gradata.enhancements.meta_rules._resolve_llm_credentials",
                return_value=_FAKE_CREDS,
            ),
            patch(
                "gradata.enhancements.meta_rules._call_llm_for_synthesis",
                side_effect=fake_call,
            ),
        ):
            llm_synthesize_rules(lessons, provider="anthropic", max_calls=1)

        assert call_count == 1

    def test_output_format(self):
        """Returns list of dicts with directive, source_lessons, confidence."""
        lessons = [
            _make_lesson(state=LessonState.RULE, category="TONE", description="Be casual"),
            _make_lesson(state=LessonState.RULE, category="TONE", description="Be warm"),
        ]

        mock_response = _fake_llm_response(
            [{"directive": "Always use a warm casual tone", "confidence": 0.9}]
        )

        with (
            patch(
                "gradata.enhancements.meta_rules._resolve_llm_credentials",
                return_value=_FAKE_CREDS,
            ),
            patch(
                "gradata.enhancements.meta_rules._call_llm_for_synthesis",
                return_value=mock_response,
            ),
        ):
            result = llm_synthesize_rules(lessons, provider="anthropic", max_calls=1)

        assert len(result) >= 1
        item = result[0]
        assert "directive" in item
        assert "source_lessons" in item
        assert "confidence" in item
        assert isinstance(item["directive"], str)
        assert isinstance(item["source_lessons"], list)
        assert isinstance(item["confidence"], float)

    def test_empty_lessons_returns_empty(self):
        """No lessons means no synthesis."""
        result = llm_synthesize_rules([], provider="anthropic", max_calls=1)
        assert result == []

    def test_no_rule_lessons_returns_empty(self):
        """All INSTINCT/PATTERN lessons means no synthesis."""
        lessons = [
            _make_lesson(state=LessonState.INSTINCT, category="TONE", description="Be casual"),
            _make_lesson(state=LessonState.PATTERN, category="TONE", description="Be warm"),
        ]
        result = llm_synthesize_rules(lessons, provider="anthropic", max_calls=1)
        assert result == []

    def test_llm_call_failure_returns_empty(self):
        """If LLM call raises, returns empty list gracefully."""
        lessons = [
            _make_lesson(state=LessonState.RULE, category="TONE", description="Be casual"),
        ]

        def failing_call(*args, **kwargs):
            raise RuntimeError("API down")

        with (
            patch(
                "gradata.enhancements.meta_rules._resolve_llm_credentials",
                return_value=_FAKE_CREDS,
            ),
            patch(
                "gradata.enhancements.meta_rules._call_llm_for_synthesis",
                side_effect=failing_call,
            ),
        ):
            result = llm_synthesize_rules(lessons, provider="anthropic", max_calls=1)

        assert result == []

    def test_max_lessons_caps_input(self):
        """Only max_lessons lessons per category are sent."""
        lessons = [
            _make_lesson(state=LessonState.RULE, category="TONE", description=f"Rule {i}")
            for i in range(20)
        ]

        captured_descriptions: list[list[str]] = []

        def fake_call(category: str, descriptions: list[str], **kwargs) -> str:
            captured_descriptions.append(descriptions)
            return _fake_llm_response([{"directive": "Combined directive", "confidence": 0.85}])

        with (
            patch(
                "gradata.enhancements.meta_rules._resolve_llm_credentials",
                return_value=_FAKE_CREDS,
            ),
            patch(
                "gradata.enhancements.meta_rules._call_llm_for_synthesis",
                side_effect=fake_call,
            ),
        ):
            llm_synthesize_rules(lessons, provider="anthropic", max_lessons=5, max_calls=1)

        assert len(captured_descriptions) == 1
        assert len(captured_descriptions[0]) <= 5
