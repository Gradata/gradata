"""Tests for gradata.safety — PII/credential detection and redaction."""

from __future__ import annotations

import pytest

from gradata.safety import redact_pii, redact_pii_with_report


def _build(parts: list[str]) -> str:
    """Join parts at runtime to avoid static secret-pattern matches."""
    return "".join(parts)


# ── Unit: redact_pii ─────────────────────────────────────────────────


class TestRedactPii:
    """redact_pii replaces sensitive data with placeholders."""

    def test_email(self):
        assert redact_pii("contact alice@example.com now") == "contact [REDACTED_EMAIL] now"

    def test_phone_us(self):
        assert "[REDACTED_PHONE]" in redact_pii("Call me at (555) 123-4567")

    def test_phone_with_country_code(self):
        assert "[REDACTED_PHONE]" in redact_pii("Call +1-555-123-4567")

    def test_openai_key(self):
        # chr(115)+chr(107) = "sk", built to dodge static scanners
        fake = _build([chr(115), chr(107), "-", "proj-", "a" * 30])
        result = redact_pii(f"myval={fake}")
        assert "[REDACTED_OPENAI_KEY]" in result
        assert fake not in result

    def test_openai_key_classic(self):
        fake = _build([chr(115), chr(107), "-", "A" * 40])
        result = redact_pii(f"export VAR={fake}")
        assert "[REDACTED_OPENAI_KEY]" in result

    def test_github_pat(self):
        fake = _build(["gh", "p_", "X" * 36])
        result = redact_pii(f"val: {fake}")
        assert "[REDACTED_GITHUB_TOKEN]" in result
        assert fake not in result

    def test_slack_token_redacted(self):
        fake = _build(["xox", "b-", "1234567890-", "a" * 20])
        result = redact_pii(f"MYVAR={fake}")
        assert "[REDACTED_SLACK_TOKEN]" in result

    def test_aws_access_key(self):
        fake = _build(["AKI", "A", "B" * 16])
        result = redact_pii(f"val={fake}")
        assert "[REDACTED_AWS_KEY]" in result

    def test_google_key(self):
        fake = _build(["AIz", "a", "c" * 35])
        result = redact_pii(f"gval={fake}")
        assert "[REDACTED_GOOGLE_KEY]" in result

    def test_gitlab_pat(self):
        fake = _build(["glpa", "t-", "d" * 20])
        result = redact_pii(f"GL={fake}")
        assert "[REDACTED_GITLAB_TOKEN]" in result

    def test_credit_card(self):
        result = redact_pii("Card: 4111 1111 1111 1111")
        assert "[REDACTED_CC]" in result

    def test_ssn(self):
        result = redact_pii("SSN is 123-45-6789")
        assert "[REDACTED_SSN]" in result

    def test_preserves_normal_text(self):
        normal = "This is a perfectly normal sentence with no PII."
        assert redact_pii(normal) == normal

    def test_empty_string(self):
        assert redact_pii("") == ""

    def test_multiple_same_type(self):
        text = "a@b.com and c@d.com and e@f.com"
        result = redact_pii(text)
        assert result.count("[REDACTED_EMAIL]") == 3
        assert "@" not in result

    def test_multiple_different_types(self):
        fake = _build([chr(115), chr(107), "-", "x" * 30])
        text = f"val={fake} email=test@test.com ssn=123-45-6789"
        result = redact_pii(text)
        assert "[REDACTED_OPENAI_KEY]" in result
        assert "[REDACTED_EMAIL]" in result
        assert "[REDACTED_SSN]" in result


# ── Unit: redact_pii_with_report ─────────────────────────────────────


class TestRedactPiiWithReport:
    """redact_pii_with_report returns cleaned text plus a report dict."""

    def test_report_structure(self):
        _, report = redact_pii_with_report("user@example.com")
        assert "redactions_count" in report
        assert "types_found" in report
        assert "redacted" in report

    def test_report_count(self):
        text = "a@b.com and c@d.com"
        _, report = redact_pii_with_report(text)
        assert report["redactions_count"] == 2
        assert report["types_found"] == ["email"]
        assert report["redacted"] is True

    def test_report_no_pii(self):
        _, report = redact_pii_with_report("nothing sensitive here")
        assert report["redactions_count"] == 0
        assert report["types_found"] == []
        assert report["redacted"] is False

    def test_report_multiple_types(self):
        text = "email test@test.com ssn 123-45-6789"
        _cleaned, report = redact_pii_with_report(text)
        assert report["redactions_count"] == 2
        assert "email" in report["types_found"]
        assert "ssn" in report["types_found"]
        assert report["redacted"] is True

    def test_empty(self):
        cleaned, report = redact_pii_with_report("")
        assert cleaned == ""
        assert report["redacted"] is False


# ── Integration: brain.correct() with PII ────────────────────────────


class TestBrainCorrectPiiIntegration:
    """Verify that brain.correct() redacts PII before storage but
    extracts behavioral instructions from full text."""

    @pytest.fixture()
    def brain(self, tmp_path):
        from gradata.brain import Brain

        return Brain(brain_dir=str(tmp_path))

    def test_pii_redacted_in_stored_event(self, brain):
        """PII in draft/final should be redacted in the emitted event data."""
        draft = "Send report to alice@notify.com"
        final = "Send report to the client"
        result = brain.correct(draft, final)
        stored_draft = result.get("data", {}).get("draft_text", "")
        # The email in draft should be redacted
        assert "alice@notify.com" not in stored_draft
        assert "[REDACTED_EMAIL]" in stored_draft

    def test_behavioral_extraction_uses_full_text(self, brain):
        """Extraction should produce meaningful classification from unredacted text,
        and redacted input should produce weaker results."""
        draft = "Contact alice@notify.com for the credentials"
        final = "Contact the client for access credentials"
        result = brain.correct(draft, final)
        # Should still produce valid classifications from the full diff
        assert "classifications" in result
        severity = result.get("data", {}).get("severity", "unknown")
        assert severity != "unknown"
        # Control: pre-redacted draft should still classify but may differ
        redacted_draft = "Contact [REDACTED_EMAIL] for the credentials"
        result_redacted = brain.correct(redacted_draft, final)
        assert "classifications" in result_redacted

    def test_key_redacted_in_event(self, brain):
        """Credential patterns in draft text must not leak to storage."""
        fake = _build([chr(115), chr(107), "-", "proj-", "K" * 30])
        draft = f"Use credential {fake} to authenticate"
        final = "Use the provided credentials to authenticate"
        result = brain.correct(draft, final)
        stored_draft = result.get("data", {}).get("draft_text", "")
        assert fake not in stored_draft
        assert "[REDACTED_OPENAI_KEY]" in stored_draft
