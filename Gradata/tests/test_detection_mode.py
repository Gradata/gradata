"""Tests for the mode classifier (Signal 5)."""

from __future__ import annotations

import pytest

from gradata.detection.mode_classifier import MODE_CATEGORY_MAP, classify_mode


class TestClassifyMode:
    """Core mode detection tests."""

    def test_code_implement(self) -> None:
        mode, conf = classify_mode("implement a function that sorts a list")
        assert mode == "code"
        assert conf > 0.0

    def test_code_fix_bug(self) -> None:
        mode, conf = classify_mode("fix the bug in src/main.py")
        assert mode == "code"
        assert conf > 0.0

    def test_email_draft_followup(self) -> None:
        mode, conf = classify_mode("draft a follow-up email to the prospect")
        assert mode == "email"
        assert conf > 0.0

    def test_email_reply(self) -> None:
        mode, conf = classify_mode("reply to the thread about pricing")
        assert mode == "email"
        assert conf > 0.0

    def test_config_env_settings(self) -> None:
        mode, conf = classify_mode("update the .env settings for production")
        assert mode == "config"
        assert conf > 0.0

    def test_documentation_readme(self) -> None:
        mode, conf = classify_mode("update the README with installation instructions")
        assert mode == "documentation"
        assert conf > 0.0

    def test_documentation_explain(self) -> None:
        mode, conf = classify_mode("explain how the authentication module works")
        assert mode == "documentation"
        assert conf > 0.0

    def test_chat_default(self) -> None:
        mode, _conf = classify_mode("hello, how are you?")
        assert mode == "chat"

    def test_empty_string(self) -> None:
        mode, conf = classify_mode("")
        assert mode == "chat"
        assert conf == pytest.approx(0.0)

    def test_whitespace_only(self) -> None:
        mode, conf = classify_mode("   ")
        assert mode == "chat"
        assert conf == pytest.approx(0.0)


class TestConfidenceScaling:
    """Confidence increases with more keyword matches."""

    def test_more_keywords_higher_confidence(self) -> None:
        _, conf_one = classify_mode("implement something")
        _, conf_many = classify_mode("implement a function to fix the bug and refactor the class")
        assert conf_many > conf_one

    def test_confidence_capped_at_one(self) -> None:
        # Stuff every code keyword in
        prompt = (
            "implement fix refactor debug test function class method "
            "src/main.py TypeError API endpoint REST"
        )
        _, conf = classify_mode(prompt)
        assert conf == pytest.approx(1.0)


class TestModeCategoryMap:
    """Verify MODE_CATEGORY_MAP structure."""

    def test_all_modes_present(self) -> None:
        expected = {"code", "email", "config", "documentation", "chat"}
        assert set(MODE_CATEGORY_MAP.keys()) == expected

    def test_chat_has_empty_categories(self) -> None:
        assert MODE_CATEGORY_MAP["chat"] == set()

    def test_code_categories(self) -> None:
        assert "CODE" in MODE_CATEGORY_MAP["code"]
        assert "TESTING" in MODE_CATEGORY_MAP["code"]
