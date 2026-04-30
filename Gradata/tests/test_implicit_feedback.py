"""Unit tests for _detect_signals in implicit_feedback hook.

Covers text-speak / shorthand inputs that were false-negatives before
the regex expansion in this session (apostrophe-less contractions,
"r" for "are", trailing ".." challenge markers, etc.).
"""

import logging
from unittest.mock import patch

import pytest

from gradata.exceptions import BrainNotConfiguredError
from gradata.hooks import implicit_feedback
from gradata.hooks.implicit_feedback import _detect_signals, main


def _signal_types(text: str) -> set[str]:
    """Return the set of signal-type strings detected in *text*."""
    return {s["type"] for s in _detect_signals(text)}


# ---------------------------------------------------------------------------
# Reminder signals
# ---------------------------------------------------------------------------


class TestReminderSignals:
    def test_why_r_you_not_asking_council_again(self):
        types = _signal_types("Why r you not asking council again..")
        assert "reminder" in types, f"Expected 'reminder' in {types}"

    def test_why_r_you_not_asking_council_again_challenge(self):
        types = _signal_types("Why r you not asking council again..")
        assert "challenge" in types, f"Expected 'challenge' in {types}"

    def test_again_you_skipped_the_council(self):
        types = _signal_types("Again, you skipped the council")
        assert "reminder" in types, f"Expected 'reminder' in {types}"


# ---------------------------------------------------------------------------
# Negation signals
# ---------------------------------------------------------------------------


class TestNegationSignals:
    def test_why_flag_negation(self):
        types = _signal_types("Why flag.. we don't skip we do work")
        assert "negation" in types, f"Expected 'negation' in {types}"

    def test_why_flag_challenge(self):
        types = _signal_types("Why flag.. we don't skip we do work")
        assert "challenge" in types, f"Expected 'challenge' in {types}"

    def test_dont_do_that(self):
        types = _signal_types("dont do that")
        assert "negation" in types, f"Expected 'negation' in {types}"


# ---------------------------------------------------------------------------
# Challenge signals
# ---------------------------------------------------------------------------


class TestChallengeSignals:
    def test_why_not_just_use_the_thing(self):
        types = _signal_types("Why not just use the thing")
        assert "challenge" in types, f"Expected 'challenge' in {types}"

    def test_you_missed_the_point(self):
        types = _signal_types("you missed the point")
        assert "challenge" in types, f"Expected 'challenge' in {types}"


# ---------------------------------------------------------------------------
# Approval signals
# ---------------------------------------------------------------------------


class TestApprovalSignals:
    def test_ship_it(self):
        types = _signal_types("ship it")
        assert "approval" in types, f"Expected 'approval' in {types}"

    def test_looks_good_to_me(self):
        types = _signal_types("looks good to me")
        assert "approval" in types, f"Expected 'approval' in {types}"


# ---------------------------------------------------------------------------
# Sanity: empty / very short input returns no signals
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_string_returns_no_signals(self):
        assert _detect_signals("") == []

    def test_short_unrelated_string(self):
        assert _detect_signals("ok") == []


# ---------------------------------------------------------------------------
# main() path — silent-drop guard when BRAIN_DIR is unresolved
# ---------------------------------------------------------------------------


class TestMainNoBrainDir:
    """When resolve_brain_dir() returns None, main() must still detect signals
    and raise instead of dropping them silently.
    """

    def test_main_raises_when_brain_dir_none(self):
        data = {"prompt": "Why r you not asking council again.."}
        with patch.object(implicit_feedback, "resolve_brain_dir", return_value=None):
            with pytest.raises(BrainNotConfiguredError):
                main(data)

    def test_main_no_log_when_no_signals(self, caplog):
        caplog.set_level(logging.DEBUG, logger="gradata.hooks.implicit_feedback")
        data = {"prompt": "hello there, just a regular message"}
        with patch.object(implicit_feedback, "resolve_brain_dir", return_value=None):
            result = main(data)
        assert result is None
        assert not any("BRAIN_DIR unresolved" in r.message for r in caplog.records)

    def test_main_no_crash_on_short_message(self):
        with patch.object(implicit_feedback, "resolve_brain_dir", return_value=None):
            assert main({"prompt": "ok"}) is None
