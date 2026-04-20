"""Tests for the dual-layer intent classifier."""

from gradata.detection.intent_classifier import CorrectionIntent, classify_intent


class TestIntentClassifier:
    def test_factual_correction_date(self):
        result = classify_intent("The date should be 2026-04-10, not 2026-03-10")
        assert result.intent == "factual_correction"
        assert result.confidence >= 0.8

    def test_factual_correction_url(self):
        result = classify_intent("Use https://example.com instead")
        assert result.intent == "factual_correction"

    def test_factual_correction_percentage(self):
        result = classify_intent("It's 15.5% not 20%")
        assert result.intent == "factual_correction"

    def test_compliance_gdpr(self):
        result = classify_intent("We need GDPR compliance here")
        assert result.intent == "compliance"

    def test_compliance_legal(self):
        result = classify_intent("Add a privacy disclaimer")
        assert result.intent == "compliance"

    def test_tone_shift(self):
        result = classify_intent("Make it more professional")
        assert result.intent == "tone_shift"

    def test_tone_too_casual(self):
        result = classify_intent("Too casual for this audience")
        assert result.intent == "tone_shift"

    def test_conciseness(self):
        result = classify_intent("This is too verbose, shorten it")
        assert result.intent == "conciseness"

    def test_completeness(self):
        result = classify_intent("You're missing the error handling section")
        assert result.intent == "completeness"

    def test_clarity_hedge(self):
        result = classify_intent("Perhaps this could be clearer")
        assert result.intent == "clarity"

    def test_formatting_list(self):
        result = classify_intent("1. First item\n2. Second item")
        assert result.intent == "formatting"

    def test_preference_short(self):
        result = classify_intent("Use blue instead")
        assert result.intent == "preference"

    def test_unknown_long_text(self):
        result = classify_intent(
            "I think there are some general issues with the overall approach "
            "that we should discuss in more detail at some point in the future"
        )
        assert result.intent == "unknown"

    def test_returns_dataclass(self):
        result = classify_intent("Fix the date to 2026-01-01")
        assert isinstance(result, CorrectionIntent)
        assert isinstance(result.evidence, str)
        assert 0.0 <= result.confidence <= 1.0

    def test_original_text_used_for_compliance(self):
        result = classify_intent(
            "Fix this section",
            original_text="The GDPR requirements state that...",
        )
        assert result.intent == "compliance"
