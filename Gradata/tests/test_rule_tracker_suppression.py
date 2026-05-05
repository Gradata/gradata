"""Tests for rule suppression tracking."""

from unittest.mock import patch

from gradata.rules.rule_tracker import VALID_SUPPRESSION_REASONS, log_suppression

_EMIT_PATH = "gradata._events.emit"


class TestLogSuppression:
    def test_emits_rule_suppression_event(self):
        with patch(_EMIT_PATH) as mock_emit:
            log_suppression(rule_id="TONE:abc123", reason="relevance_threshold", relevance=0.25)
            mock_emit.assert_called_once()
            args = mock_emit.call_args[0]
            assert args[0] == "RULE_SUPPRESSION"

    def test_data_contains_rule_id_and_reason(self):
        with patch(_EMIT_PATH) as mock_emit:
            log_suppression(rule_id="TONE:abc123", reason="domain_disabled", relevance=0.0)
            mock_emit.call_args[1]
            # emit is called with keyword args from log_suppression
            call_args = mock_emit.call_args
            # Get data from positional or keyword args
            data = call_args[1].get("data", call_args[0][2] if len(call_args[0]) > 2 else None)
            assert data["rule_id"] == "TONE:abc123"
            assert data["reason"] == "domain_disabled"
            assert data["relevance"] == 0.0
            assert data["competing_rules"] == []

    def test_competing_rules_passed_through(self):
        with patch(_EMIT_PATH) as mock_emit:
            log_suppression(
                rule_id="TONE:abc123",
                reason="conflict",
                relevance=0.5,
                competing_rule_ids=["STYLE:def456"],
            )
            call_args = mock_emit.call_args
            data = call_args[1].get("data", call_args[0][2] if len(call_args[0]) > 2 else None)
            assert data["competing_rules"] == ["STYLE:def456"]

    def test_tags_include_rule_and_reason(self):
        with patch(_EMIT_PATH) as mock_emit:
            log_suppression(rule_id="TONE:abc123", reason="assumption_invalid", relevance=0.3)
            call_args = mock_emit.call_args
            tags = call_args[1].get("tags", call_args[0][3] if len(call_args[0]) > 3 else None)
            assert "rule:TONE:abc123" in tags
            assert "suppression:assumption_invalid" in tags

    def test_relevance_rounded(self):
        with patch(_EMIT_PATH) as mock_emit:
            log_suppression(rule_id="X:1", reason="relevance_threshold", relevance=0.123456789)
            call_args = mock_emit.call_args
            data = call_args[1].get("data", call_args[0][2] if len(call_args[0]) > 2 else None)
            assert data["relevance"] == 0.1235

    def test_valid_suppression_reasons_complete(self):
        assert "relevance_threshold" in VALID_SUPPRESSION_REASONS
        assert "domain_disabled" in VALID_SUPPRESSION_REASONS
        assert "conflict" in VALID_SUPPRESSION_REASONS
        assert "assumption_invalid" in VALID_SUPPRESSION_REASONS
        assert len(VALID_SUPPRESSION_REASONS) == 4
