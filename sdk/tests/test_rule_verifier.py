"""
Tests for enhancements/rule_verifier.py (S71 module, zero prior coverage).

Covers:
- auto_detect_verification() pattern matching
- verify_rules() violation detection
- log_verification() + get_verification_stats() SQLite persistence
- RuleVerification dataclass

Run: cd sdk && python -m pytest tests/test_rule_verifier.py -v
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from gradata.enhancements.rule_verifier import (
    RuleVerification,
    auto_detect_verification,
    ensure_table,
    get_verification_stats,
    log_verification,
    verify_rules,
)


# ===========================================================================
# auto_detect_verification
# ===========================================================================

class TestAutoDetectVerification:
    """auto_detect_verification() scans rule descriptions for checkable patterns."""

    def test_em_dash_rule(self):
        checks = auto_detect_verification("Never use em dashes in emails")
        assert len(checks) >= 1
        # Should detect em dash pattern as should_be_absent=True
        regex, absent, desc = checks[0]
        assert absent is True
        assert "em dash" in desc

    def test_pricing_rule(self):
        checks = auto_detect_verification("Do not include pricing or dollar amounts")
        assert len(checks) >= 1
        regexes_absent = [(r, a) for r, a, _ in checks]
        assert any(a is True for _, a in regexes_absent)

    def test_calendly_rule(self):
        checks = auto_detect_verification("Always hyperlink Calendly link")
        assert len(checks) >= 1
        # Calendly should be should_be_absent=False (must be present)
        regex, absent, desc = checks[0]
        assert absent is False
        assert "Calendly" in desc

    def test_bold_rule(self):
        checks = auto_detect_verification("No bold mid-paragraph text")
        assert len(checks) >= 1
        regex, absent, desc = checks[0]
        assert absent is True

    def test_no_match_returns_empty(self):
        checks = auto_detect_verification("Use a professional tone in all emails")
        assert len(checks) == 0

    def test_multiple_patterns_in_one_rule(self):
        """A rule mentioning both em dashes and pricing should return multiple checks."""
        checks = auto_detect_verification("Never use em dashes or include dollar amounts")
        assert len(checks) >= 2

    def test_annual_pricing_detection(self):
        checks = auto_detect_verification("Do not reference annual pricing in emails")
        keywords = [desc for _, _, desc in checks]
        assert any("annual" in d for d in keywords)


# ===========================================================================
# verify_rules
# ===========================================================================

class TestVerifyRules:
    """verify_rules() checks AI output against applied rules."""

    def test_clean_output_passes(self):
        rules = [{"category": "DRAFTING", "description": "Never use em dashes"}]
        output = "This is a clean sentence with no dashes."
        results = verify_rules(output, rules)
        assert len(results) >= 1
        assert all(r.passed for r in results)

    def test_em_dash_violation_detected(self):
        rules = [{"category": "DRAFTING", "description": "Never use em dashes"}]
        output = "This has an em dash \u2014 right here."
        results = verify_rules(output, rules)
        violations = [r for r in results if not r.passed]
        assert len(violations) >= 1
        assert violations[0].rule_category == "DRAFTING"
        assert "em dash" in violations[0].violation_detail

    def test_double_dash_also_caught(self):
        rules = [{"category": "DRAFTING", "description": "Never use em dashes"}]
        output = "This has a double dash -- right here."
        results = verify_rules(output, rules)
        violations = [r for r in results if not r.passed]
        assert len(violations) >= 1

    def test_pricing_violation(self):
        rules = [{"category": "PRICING", "description": "Do not include dollar pricing"}]
        output = "Our starter plan is $60/month."
        results = verify_rules(output, rules)
        violations = [r for r in results if not r.passed]
        assert len(violations) >= 1

    def test_missing_calendly_violation(self):
        rules = [{"category": "DRAFTING", "description": "Always include Calendly hyperlink"}]
        output = "Let me know if you want to chat."
        results = verify_rules(output, rules)
        violations = [r for r in results if not r.passed]
        assert len(violations) >= 1
        assert "Calendly" in violations[0].violation_detail

    def test_calendly_present_passes(self):
        rules = [{"category": "DRAFTING", "description": "Always include Calendly link"}]
        output = "Book a time here: calendly.com/oliver-spritesai/30min"
        results = verify_rules(output, rules)
        assert all(r.passed for r in results)

    def test_non_checkable_rules_skipped(self):
        rules = [{"category": "TONE", "description": "Be professional and direct"}]
        results = verify_rules("Any output.", rules)
        assert len(results) == 0  # no checkable patterns

    def test_output_snippet_captured(self):
        rules = [{"category": "DRAFTING", "description": "Never use em dashes"}]
        output = "Start " + "x" * 50 + " \u2014 " + "y" * 50 + " end."
        results = verify_rules(output, rules)
        violations = [r for r in results if not r.passed]
        assert len(violations) >= 1
        assert len(violations[0].output_snippet) <= 200

    def test_description_truncated(self):
        long_desc = "x" * 300
        rules = [{"category": "DRAFTING", "description": f"Never use em dashes. {long_desc}"}]
        results = verify_rules("text \u2014 here", rules)
        for r in results:
            assert len(r.rule_description) <= 200

    def test_context_parameter_accepted(self):
        """Context param should be accepted even if not currently used."""
        rules = [{"category": "DRAFTING", "description": "Never use em dashes"}]
        results = verify_rules("clean text", rules, context={"task_type": "email"})
        assert isinstance(results, list)

    def test_multiple_rules_checked(self):
        rules = [
            {"category": "DRAFTING", "description": "Never use em dashes"},
            {"category": "PRICING", "description": "Do not include dollar amounts"},
        ]
        output = "Text with \u2014 dash and $100 price."
        results = verify_rules(output, rules)
        violations = [r for r in results if not r.passed]
        assert len(violations) >= 2

    def test_bold_violation(self):
        rules = [{"category": "DRAFTING", "description": "No bold formatting in emails"}]
        output = "This has **bold text** in it."
        results = verify_rules(output, rules)
        violations = [r for r in results if not r.passed]
        assert len(violations) >= 1


# ===========================================================================
# RuleVerification dataclass
# ===========================================================================

class TestRuleVerification:
    def test_defaults(self):
        rv = RuleVerification(
            rule_category="TEST", rule_description="desc", passed=True
        )
        assert rv.violation_detail == ""
        assert rv.output_snippet == ""

    def test_all_fields(self):
        rv = RuleVerification(
            rule_category="DRAFTING",
            rule_description="No em dashes",
            passed=False,
            violation_detail="contains em dash",
            output_snippet="text \u2014 here",
        )
        assert not rv.passed
        assert rv.violation_detail == "contains em dash"


# ===========================================================================
# SQLite persistence
# ===========================================================================

class TestVerificationPersistence:
    """log_verification() and get_verification_stats() SQLite roundtrip."""

    def test_log_and_retrieve_stats(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            results = [
                RuleVerification("DRAFTING", "No em dashes", True),
                RuleVerification("DRAFTING", "No em dashes", False, "violation", "snippet"),
                RuleVerification("PRICING", "No dollar amounts", False, "violation", "snippet"),
            ]
            log_verification(session=71, results=results, db_path=db_path)
            stats = get_verification_stats(db_path)

            assert stats["total_checks"] == 3
            assert stats["passed"] == 1
            assert stats["pass_rate"] == pytest.approx(1 / 3)
            assert "DRAFTING" in stats["violations_by_category"]
            assert "PRICING" in stats["violations_by_category"]
            assert stats["violations_by_category"]["DRAFTING"] == 1
            assert stats["violations_by_category"]["PRICING"] == 1
        finally:
            import gc; gc.collect()  # release SQLite connections on Windows
            db_path.unlink(missing_ok=True)

    def test_empty_db_stats(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            ensure_table(db_path)
            stats = get_verification_stats(db_path)
            assert stats["total_checks"] == 0
            assert stats["pass_rate"] == 1.0
            assert stats["violations_by_category"] == {}
        finally:
            import gc; gc.collect()
            db_path.unlink(missing_ok=True)

    def test_multiple_sessions(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            r1 = [RuleVerification("DRAFTING", "Rule A", True)]
            r2 = [RuleVerification("DRAFTING", "Rule A", False, "v", "s")]
            log_verification(session=70, results=r1, db_path=db_path)
            log_verification(session=71, results=r2, db_path=db_path)
            stats = get_verification_stats(db_path)
            assert stats["total_checks"] == 2
            assert stats["passed"] == 1
        finally:
            import gc; gc.collect()
            db_path.unlink(missing_ok=True)
