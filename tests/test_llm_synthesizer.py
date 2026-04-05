"""Tests for LLM-enhanced principle synthesis."""

import json
from unittest.mock import MagicMock, patch

import pytest

from gradata._types import Lesson, LessonState
from gradata.enhancements.llm_synthesizer import synthesise_principle_llm


def _make_lesson(desc: str, category: str = "CONTENT") -> Lesson:
    return Lesson(
        date="2026-04-03",
        description=desc,
        category=category,
        state=LessonState.RULE,
        confidence=0.90,
        fire_count=5,
    )


class TestSynthesiseLLMOffline:
    """Tests for offline/fallback behavior."""

    def test_no_api_key_returns_none(self):
        lessons = [_make_lesson("cut: following. added: infrastructure")]
        assert synthesise_principle_llm(lessons, "content", api_key=None) is None

    def test_empty_api_key_returns_none(self):
        lessons = [_make_lesson("cut: following")]
        assert synthesise_principle_llm(lessons, "content", api_key="") is None

    def test_empty_lessons_returns_none(self):
        assert synthesise_principle_llm([], "content", api_key="sk-test") is None

    def test_lessons_with_no_descriptions_returns_none(self):
        lessons = [_make_lesson("")]
        assert synthesise_principle_llm(lessons, "content", api_key="sk-test") is None


class TestSynthesiseLLMMocked:
    """Tests with mocked HTTP responses."""

    def _mock_response(self, content: str):
        """Create a mock urllib response."""
        body = json.dumps({
            "choices": [{"message": {"content": content}}]
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    @patch("gradata.enhancements.llm_synthesizer.urllib.request.urlopen")
    def test_successful_synthesis(self, mock_urlopen):
        principle = "When writing sales emails, use specific technical terms instead of generic follow-ups."
        mock_urlopen.return_value = self._mock_response(principle)

        lessons = [
            _make_lesson("cut: following, checking in. added: infrastructure"),
            _make_lesson("cut: perhaps. added: modernization"),
            _make_lesson("cut: might. added: specific timeline"),
        ]
        result = synthesise_principle_llm(
            lessons, "content", api_key="sk-test", api_base="https://api.example.com/v1",
        )
        assert result == principle

    def test_no_api_base_returns_none(self):
        """When no api_base is configured, synthesis is skipped."""
        lessons = [_make_lesson("cut: x. added: y")]
        result = synthesise_principle_llm(lessons, "content", api_key="sk-test", api_base="")
        assert result is None

    @patch("gradata.enhancements.llm_synthesizer.urllib.request.urlopen")
    def test_too_short_response_returns_none(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response("Short.")
        lessons = [_make_lesson("cut: x. added: y")]
        result = synthesise_principle_llm(
            lessons, "content", api_key="sk-test", api_base="https://api.example.com/v1",
        )
        assert result is None

    @patch("gradata.enhancements.llm_synthesizer.urllib.request.urlopen")
    def test_network_error_returns_none(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        lessons = [_make_lesson("cut: x. added: y")]
        result = synthesise_principle_llm(
            lessons, "content", api_key="sk-test", api_base="https://api.example.com/v1",
        )
        assert result is None

    @patch("gradata.enhancements.llm_synthesizer.urllib.request.urlopen")
    def test_bad_json_returns_none(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        lessons = [_make_lesson("cut: x. added: y")]
        result = synthesise_principle_llm(
            lessons, "content", api_key="sk-test", api_base="https://api.example.com/v1",
        )
        assert result is None


class TestMetaRulesLLMIntegration:
    """Test that merge_into_meta falls back correctly."""

    def test_merge_without_api_key_uses_regex(self):
        from gradata.enhancements.meta_rules import merge_into_meta
        lessons = [
            _make_lesson("cut: following, checking. added: infrastructure", "CONTENT"),
            _make_lesson("cut: following, perhaps. added: modernization", "CONTENT"),
            _make_lesson("cut: following, maybe. added: specific", "CONTENT"),
        ]
        meta = merge_into_meta(lessons, theme_override="content", session=1)
        # Should use regex synthesis (no api_key), producing word-list style
        assert meta.principle
        assert meta.id.startswith("META-")

    @patch("gradata.enhancements.llm_synthesizer.synthesise_principle_llm", return_value=None)
    def test_merge_with_llm_failure_falls_back(self, mock_llm):
        from gradata.enhancements.meta_rules import merge_into_meta
        lessons = [
            _make_lesson("cut: x. added: y", "TONE"),
            _make_lesson("cut: a. added: b", "TONE"),
            _make_lesson("cut: c. added: d", "TONE"),
        ]
        meta = merge_into_meta(lessons, theme_override="tone", session=1, api_key="sk-test")
        # LLM returned None, should fall back to regex
        assert meta.principle
        mock_llm.assert_called_once()
