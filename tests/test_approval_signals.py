"""Tests for approval signal detection in implicit_feedback hook."""

from gradata.hooks.implicit_feedback import _detect_signals


class TestApprovalSignals:
    def test_looks_good(self):
        signals = _detect_signals("Looks good, ship it.")
        types = [s["type"] for s in signals]
        assert "approval" in types

    def test_perfect(self):
        signals = _detect_signals("Perfect, that's what I needed.")
        types = [s["type"] for s in signals]
        assert "approval" in types

    def test_exactly(self):
        signals = _detect_signals("Yes, exactly what I wanted.")
        types = [s["type"] for s in signals]
        assert "approval" in types

    def test_thats_correct(self):
        signals = _detect_signals("That's correct.")
        types = [s["type"] for s in signals]
        assert "approval" in types

    def test_nailed_it(self):
        signals = _detect_signals("You nailed it!")
        types = [s["type"] for s in signals]
        assert "approval" in types

    def test_ship_it(self):
        signals = _detect_signals("Ship it!")
        types = [s["type"] for s in signals]
        assert "approval" in types

    def test_no_false_positive_on_neutral(self):
        signals = _detect_signals("Can you update the database schema?")
        types = [s["type"] for s in signals]
        assert "approval" not in types

    def test_negation_not_approval(self):
        signals = _detect_signals("No, that's wrong.")
        types = [s["type"] for s in signals]
        assert "negation" in types
        assert "approval" not in types
