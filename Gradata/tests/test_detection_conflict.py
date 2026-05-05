"""Tests for gradata.detection.correction_conflict — Signal 6."""

from __future__ import annotations

from gradata.detection.correction_conflict import (
    ConflictTracker,
    detect_conflict,
    extract_diff_tokens,
)
from gradata.detection.correction_conflict import (
    tokenize as cc_tokenize,
)

# ── cc_tokenize ──────────────────────────────────────────────────────────────


class TestTokenize:
    def test_basic(self):
        result = cc_tokenize("Hello World")
        assert result == {"hello", "world"}

    def test_empty_string(self):
        assert cc_tokenize("") == set()

    def test_strips_punctuation(self):
        result = cc_tokenize("hello, world! foo.")
        assert result == {"hello", "world", "foo"}

    def test_deduplicates(self):
        result = cc_tokenize("the the the")
        assert result == {"the"}


# ── extract_diff_tokens ───────────────────────────────────────────────────


class TestExtractDiffTokens:
    def test_added_tokens(self):
        added, removed = extract_diff_tokens("hello world", "hello world foo bar")
        assert added == {"foo", "bar"}
        assert removed == set()

    def test_removed_tokens(self):
        added, removed = extract_diff_tokens("hello world foo", "hello world")
        assert added == set()
        assert removed == {"foo"}

    def test_both(self):
        added, removed = extract_diff_tokens("hello old", "hello new")
        assert added == {"new"}
        assert removed == {"old"}


# ── detect_conflict ───────────────────────────────────────────────────────


class TestDetectConflict:
    def test_conflict_detected(self):
        # Original added {"foo", "bar", "baz"}, new removes {"foo", "bar"}
        original_added = {"foo", "bar", "baz"}
        new_removed = {"foo", "bar"}
        assert detect_conflict(original_added, new_removed, threshold=0.3) is True

    def test_no_conflict(self):
        original_added = {"foo", "bar", "baz"}
        new_removed = {"qux", "quux"}
        assert detect_conflict(original_added, new_removed) is False

    def test_empty_original_added(self):
        assert detect_conflict(set(), {"foo"}) is False

    def test_empty_new_removed(self):
        assert detect_conflict({"foo"}, set()) is False

    def test_both_empty(self):
        assert detect_conflict(set(), set()) is False

    def test_threshold_boundary(self):
        # 1 overlap out of 3 = 0.333... >= 0.3
        assert detect_conflict({"a", "b", "c"}, {"a"}, threshold=0.3) is True
        # 1 overlap out of 4 = 0.25 < 0.3
        assert detect_conflict({"a", "b", "c", "d"}, {"a"}, threshold=0.3) is False


# ── ConflictTracker ───────────────────────────────────────────────────────


class TestConflictTracker:
    def test_first_conflict_returns_none(self):
        tracker = ConflictTracker()
        assert tracker.record_conflict("R1") is None

    def test_second_returns_demote(self):
        tracker = ConflictTracker()
        tracker.record_conflict("R1")
        assert tracker.record_conflict("R1") == "demote"

    def test_third_returns_kill(self):
        tracker = ConflictTracker()
        tracker.record_conflict("R1")
        tracker.record_conflict("R1")
        assert tracker.record_conflict("R1") == "kill"

    def test_fourth_still_kill(self):
        tracker = ConflictTracker()
        for _ in range(3):
            tracker.record_conflict("R1")
        assert tracker.record_conflict("R1") == "kill"

    def test_different_rules_independent(self):
        tracker = ConflictTracker()
        tracker.record_conflict("R1")
        tracker.record_conflict("R1")  # demote
        assert tracker.record_conflict("R2") is None  # first for R2
        assert tracker.get_count("R1") == 2
        assert tracker.get_count("R2") == 1

    def test_get_count(self):
        tracker = ConflictTracker()
        assert tracker.get_count("R1") == 0
        tracker.record_conflict("R1")
        assert tracker.get_count("R1") == 1

    def test_custom_thresholds(self):
        tracker = ConflictTracker(demote_threshold=3, kill_threshold=5)
        assert tracker.record_conflict("R1") is None  # 1
        assert tracker.record_conflict("R1") is None  # 2
        assert tracker.record_conflict("R1") == "demote"  # 3
        assert tracker.record_conflict("R1") == "demote"  # 4
        assert tracker.record_conflict("R1") == "kill"  # 5
