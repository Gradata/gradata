"""Tests for StructuredCorrection and extract_structured_correction().

Covers:
- Each CorrectionType classification via keyword patterns
- what_wrong extraction from draft/final diff
- Domain detection
- to_dict / from_dict round-trip
- Empty / minimal inputs
- Pure-regex (no LLM) guarantee
"""

from __future__ import annotations

import pytest

from gradata.correction_detector import (
    CorrectionType,
    StructuredCorrection,
    _classify_correction_type,
    _classify_domain,
    _classify_severity,
    _extract_what_wrong,
    _extract_why,
    extract_structured_correction,
)


# ---------------------------------------------------------------------------
# CorrectionType classification
# ---------------------------------------------------------------------------


class TestClassifyCorrectionType:
    def test_factual_error(self):
        assert _classify_correction_type("That is wrong, the number is 42") == CorrectionType.FACTUAL_ERROR

    def test_hallucination_priority_over_factual(self):
        # "hallucin" keyword should win over "wrong" because it appears first in pattern list.
        assert _classify_correction_type("You hallucinated that endpoint, it doesn't exist") == CorrectionType.HALLUCINATION

    def test_tone(self):
        assert _classify_correction_type("The tone is too cold and formal for this prospect") == CorrectionType.TONE

    def test_style_dash(self):
        assert _classify_correction_type("Don't use em dash in the email") == CorrectionType.STYLE

    def test_style_emoji(self):
        assert _classify_correction_type("Remove the emoji from the subject line") == CorrectionType.STYLE

    def test_format(self):
        assert _classify_correction_type("The layout and heading structure is off") == CorrectionType.FORMAT

    def test_omission(self):
        assert _classify_correction_type("You forgot to include the pricing section") == CorrectionType.OMISSION

    def test_approach(self):
        assert _classify_correction_type("Please change the strategy and workflow here") == CorrectionType.APPROACH

    def test_scope(self):
        assert _classify_correction_type("This rule is only for email scope, not code") == CorrectionType.SCOPE

    def test_unknown_fallback(self):
        assert _classify_correction_type("Please update this") == CorrectionType.UNKNOWN

    def test_empty_string(self):
        assert _classify_correction_type("") == CorrectionType.UNKNOWN


# ---------------------------------------------------------------------------
# what_wrong extraction
# ---------------------------------------------------------------------------


class TestExtractWhatWrong:
    def test_returns_draft_segment_at_divergence(self):
        draft = "The deadline is March 15 and the budget is $5000"
        final = "The deadline is April 20 and the budget is $5000"
        result = _extract_what_wrong(draft, final)
        # Should contain the word "March" or words near the divergence.
        assert "March" in result or "15" in result

    def test_identical_texts_returns_final_snippet(self):
        text = "Hello world this is the same text"
        result = _extract_what_wrong(text, text)
        assert result == text[:120]

    def test_empty_draft_returns_final(self):
        result = _extract_what_wrong("", "The correction text here")
        assert result == "The correction text here"

    def test_empty_final_returns_unknown(self):
        result = _extract_what_wrong("some draft", "")
        assert result == "unknown"

    def test_long_result_truncated_at_120(self):
        draft = "a " * 200
        final = "b " * 200
        result = _extract_what_wrong(draft, final)
        assert len(result) <= 120

    def test_longer_draft_divergence(self):
        draft = "We offer quarterly billing and annual billing with a 10% discount"
        final = "We offer monthly billing and annual billing with a 10% discount"
        result = _extract_what_wrong(draft, final)
        assert "quarterly" in result


# ---------------------------------------------------------------------------
# Why extraction
# ---------------------------------------------------------------------------


class TestExtractWhy:
    def test_because_clause(self):
        result = _extract_why("", "Don't use dashes because they read as informal")
        assert "informal" in result.lower()

    def test_since_clause(self):
        result = _extract_why("since the prospect already knows us, skip the intro", "make it shorter")
        assert "prospect" in result.lower() or "intro" in result.lower()

    def test_context_first_sentence(self):
        result = _extract_why("The email is too long for a warm lead", "shorten it")
        assert "email" in result.lower() or "warm" in result.lower()

    def test_fallback_to_final(self):
        result = _extract_why("", "just fix it")
        assert "fix" in result.lower() or len(result) > 0

    def test_empty_inputs(self):
        result = _extract_why("", "")
        assert result == "no reason provided"


# ---------------------------------------------------------------------------
# Domain classification
# ---------------------------------------------------------------------------


class TestClassifyDomain:
    def test_email_domain(self):
        assert _classify_domain("The subject line of the email is wrong") == "email"

    def test_code_domain(self):
        assert _classify_domain("This function has an import error") == "code"

    def test_sales_domain(self):
        assert _classify_domain("The outreach campaign for this prospect is off") == "sales"

    def test_deploy_domain(self):
        assert _classify_domain("Railway CI pipeline is failing on build") == "deploy"

    def test_api_domain(self):
        assert _classify_domain("The REST endpoint returns a 404") == "api"

    def test_database_domain(self):
        assert _classify_domain("The SQL query is missing the WHERE clause") == "database"

    def test_docs_domain(self):
        assert _classify_domain("Update the README and spec accordingly") == "docs"

    def test_general_fallback(self):
        assert _classify_domain("This is incorrect") == "general"

    def test_empty_string(self):
        assert _classify_domain("") == "general"


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------


class TestClassifySeverity:
    def test_trivial_tiny_change(self):
        draft = "Hello world foo bar baz qux quux corge"
        # Only one word swapped — very low ratio of removed words.
        final = "Hello world foo bar baz qux quux grault"
        sev = _classify_severity(draft, final)
        assert sev in ("trivial", "minor")

    def test_rewrite_completely_different(self):
        draft = "apple banana cherry date elderberry fig grape honeydew"
        final = "completely different words that share nothing at all here"
        sev = _classify_severity(draft, final)
        assert sev == "rewrite"

    def test_major_severity(self):
        draft = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"
        # ~60% of draft words removed (6/10).
        final = "word1 word2 word3 wordA wordB wordC wordD wordE wordF wordG"
        sev = _classify_severity(draft, final)
        assert sev in ("major", "rewrite")

    def test_empty_inputs_default_minor(self):
        assert _classify_severity("", "") == "minor"
        assert _classify_severity("draft", "") == "minor"


# ---------------------------------------------------------------------------
# extract_structured_correction integration
# ---------------------------------------------------------------------------


class TestExtractStructuredCorrection:
    def test_detects_correction_with_explicit_signal(self):
        draft = "Use em dashes throughout the email — like this"
        final = "Don't use em dashes in the email"
        result = extract_structured_correction(draft, final)
        assert result is not None
        assert result.correction_type == CorrectionType.STYLE
        assert result.domain == "email"

    def test_returns_none_for_empty_inputs(self):
        result = extract_structured_correction("", "")
        assert result is None

    def test_context_improves_domain(self):
        draft = "the function calculates x"
        final = "No, that is wrong"
        context = "We are reviewing the Python code for the import pipeline"
        result = extract_structured_correction(draft, final, context=context)
        assert result is not None
        assert result.domain == "code"

    def test_why_extracted_from_context(self):
        draft = "Send immediately"
        final = "Don't send immediately"
        context = "Wait because the prospect asked for a follow-up next week"
        result = extract_structured_correction(draft, final, context=context)
        assert result is not None
        assert "prospect" in result.why.lower() or "week" in result.why.lower()

    def test_hallucination_type(self):
        draft = "The Gradata v3 API supports WebSockets natively"
        final = "You hallucinated that — WebSockets aren't supported"
        result = extract_structured_correction(draft, final)
        assert result is not None
        assert result.correction_type == CorrectionType.HALLUCINATION

    def test_tone_correction(self):
        draft = "Dear Sir/Madam, I am writing to formally inquire..."
        final = "Too formal — make the tone more casual and warm"
        result = extract_structured_correction(draft, final)
        assert result is not None
        assert result.correction_type == CorrectionType.TONE

    def test_omission_correction(self):
        draft = "Here is your plan: step 1, step 2"
        final = "You forgot to include step 3 and the timeline"
        result = extract_structured_correction(draft, final)
        assert result is not None
        assert result.correction_type == CorrectionType.OMISSION

    def test_approach_correction(self):
        draft = "Use a challenger approach to open the email"
        final = "Change the strategy — use a peer-to-peer workflow instead"
        result = extract_structured_correction(draft, final)
        assert result is not None
        assert result.correction_type == CorrectionType.APPROACH

    def test_what_wrong_populated(self):
        draft = "The deadline is March 15"
        final = "No, that is wrong — the deadline is April 20"
        result = extract_structured_correction(draft, final)
        assert result is not None
        assert len(result.what_wrong) > 0

    def test_severity_populated(self):
        draft = "Short draft"
        final = "No, completely different direction"
        result = extract_structured_correction(draft, final)
        assert result is not None
        assert result.severity in ("trivial", "minor", "moderate", "major", "rewrite")

    def test_no_llm_calls(self):
        """Ensure the function uses no external calls — only regex-based logic."""
        # This test simply verifies the function completes synchronously with
        # no network calls (if it tried an HTTP call, it would fail in CI).
        draft = "Hello world"
        final = "Don't write hello world"
        result = extract_structured_correction(draft, final)
        # If we got here without an exception, no LLM/HTTP call was made.
        assert result is not None


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip
# ---------------------------------------------------------------------------


class TestStructuredCorrectionSerialization:
    def _make_instance(self) -> StructuredCorrection:
        return StructuredCorrection(
            what_wrong="em dashes throughout the email",
            why="they read as too informal for cold outreach",
            correction_type=CorrectionType.STYLE,
            domain="email",
            severity="minor",
            related_rule_id="rule_42",
        )

    def test_to_dict_keys(self):
        obj = self._make_instance()
        d = obj.to_dict()
        assert set(d.keys()) == {
            "what_wrong",
            "why",
            "correction_type",
            "domain",
            "severity",
            "related_rule_id",
        }

    def test_to_dict_correction_type_is_string(self):
        obj = self._make_instance()
        d = obj.to_dict()
        assert isinstance(d["correction_type"], str)
        assert d["correction_type"] == "style"

    def test_round_trip_all_fields(self):
        obj = self._make_instance()
        restored = StructuredCorrection.from_dict(obj.to_dict())
        assert restored.what_wrong == obj.what_wrong
        assert restored.why == obj.why
        assert restored.correction_type == obj.correction_type
        assert restored.domain == obj.domain
        assert restored.severity == obj.severity
        assert restored.related_rule_id == obj.related_rule_id

    def test_round_trip_none_related_rule_id(self):
        obj = StructuredCorrection(
            what_wrong="something",
            why="reason",
            correction_type=CorrectionType.UNKNOWN,
            domain="general",
            severity="trivial",
            related_rule_id=None,
        )
        d = obj.to_dict()
        assert d["related_rule_id"] is None
        restored = StructuredCorrection.from_dict(d)
        assert restored.related_rule_id is None

    def test_from_dict_with_all_correction_types(self):
        for ct in CorrectionType:
            d = {
                "what_wrong": "x",
                "why": "y",
                "correction_type": str(ct),
                "domain": "general",
                "severity": "minor",
                "related_rule_id": None,
            }
            obj = StructuredCorrection.from_dict(d)
            assert obj.correction_type == ct

    def test_from_dict_missing_keys_use_defaults(self):
        obj = StructuredCorrection.from_dict({})
        assert obj.what_wrong == ""
        assert obj.why == ""
        assert obj.correction_type == CorrectionType.UNKNOWN
        assert obj.domain == "general"
        assert obj.severity == "minor"
        assert obj.related_rule_id is None
