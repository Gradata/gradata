"""Tests for gradata.detection.addition_pattern — Signal 4."""

from __future__ import annotations

import pytest

from gradata.detection.addition_pattern import (
    AdditionTracker,
    classify_addition,
    is_addition,
)


# ── is_addition ───────────────────────────────────────────────────────────


class TestIsAddition:
    def test_pure_addition_suffix(self):
        old = "def foo():"
        new = "def foo():\n    return 42  # added"
        assert is_addition(old, new) is True

    def test_pure_addition_prefix(self):
        old = "print('hello')"
        new = "import os\nimport sys\nprint('hello')"
        assert is_addition(old, new) is True

    def test_replacement_not_addition(self):
        old = "def foo(): pass"
        new = "def bar(): return 1"
        assert is_addition(old, new) is False

    def test_too_short_addition(self):
        old = "hello"
        new = "hello!!!"
        assert is_addition(old, new, min_added_chars=10) is False

    def test_major_rewrite_not_addition(self):
        old = "The quick brown fox jumps over the lazy dog."
        new = "A fast red cat leaps across the sleeping puppy."
        assert is_addition(old, new) is False

    def test_empty_old_nonempty_new(self):
        assert is_addition("", "import os\nimport sys") is True

    def test_empty_old_short_new(self):
        assert is_addition("", "hi") is False

    def test_both_empty(self):
        assert is_addition("", "") is False


# ── classify_addition ─────────────────────────────────────────────────────


class TestClassifyAddition:
    def test_python_type_annotation(self):
        old = "x = 5"
        new = "x: int = 5"
        cat, stype = classify_addition(old, new, ".py")
        assert cat == "python"
        assert stype == "type_annotation"

    def test_python_import(self):
        old = "x = 1"
        new = "import os\nx = 1"
        cat, stype = classify_addition(old, new, ".py")
        assert cat == "python"
        assert stype == "import"

    def test_markdown_link(self):
        old = "See the docs."
        new = "See the docs. [link](https://example.com)"
        cat, stype = classify_addition(old, new, ".md")
        assert cat == "markdown"
        assert stype == "link"

    def test_js_comment(self):
        old = "const x = 1;"
        new = "// added a comment\nconst x = 1;"
        cat, stype = classify_addition(old, new, ".js")
        assert cat == "javascript"
        assert stype == "comment"

    def test_unknown_ext_falls_back(self):
        old = "data"
        new = "data plus more stuff"
        cat, stype = classify_addition(old, new, ".xyz")
        assert cat == "xyz"
        assert stype == "other"

    def test_python_docstring(self):
        old = "def foo():\n    pass"
        new = 'def foo():\n    """Do something."""\n    pass'
        cat, stype = classify_addition(old, new, ".py")
        assert cat == "python"
        assert stype == "docstring"

    def test_markdown_heading(self):
        old = "content here"
        new = "# Title\ncontent here"
        cat, stype = classify_addition(old, new, ".md")
        assert cat == "markdown"
        assert stype == "heading"


# ── AdditionTracker ───────────────────────────────────────────────────────


class TestAdditionTracker:
    def test_no_lesson_before_threshold(self):
        tracker = AdditionTracker(threshold=3)
        fp = ("python", "import")
        assert tracker.record(fp, "s1") is None
        assert tracker.record(fp, "s1") is None

    def test_lesson_at_threshold(self):
        tracker = AdditionTracker(threshold=3)
        fp = ("python", "import")
        tracker.record(fp, "s1")
        tracker.record(fp, "s1")
        lesson = tracker.record(fp, "s1")
        assert lesson is not None
        assert lesson["category"] == "python"
        assert lesson["detection"] == "addition_pattern"
        assert lesson["fingerprint"] == "PYTHON:import"
        assert "import" in lesson["description"]
        assert "python" in lesson["description"]

    def test_different_patterns_dont_combine(self):
        tracker = AdditionTracker(threshold=3)
        tracker.record(("python", "import"), "s1")
        tracker.record(("python", "import"), "s1")
        # Different fingerprint
        tracker.record(("python", "type_annotation"), "s1")
        # Third import should trigger
        lesson = tracker.record(("python", "import"), "s1")
        assert lesson is not None
        assert lesson["fingerprint"] == "PYTHON:import"

    def test_cross_session_threshold(self):
        tracker = AdditionTracker(threshold=3, cross_session_threshold=2)
        fp = ("markdown", "link")
        # One in session A
        assert tracker.record(fp, "session-a") is None
        # One in session B — crosses 2 sessions with 2 occurrences
        lesson = tracker.record(fp, "session-b")
        assert lesson is not None
        assert lesson["category"] == "markdown"
        assert lesson["fingerprint"] == "MARKDOWN:link"

    def test_counter_resets_after_lesson(self):
        tracker = AdditionTracker(threshold=3)
        fp = ("python", "import")
        tracker.record(fp, "s1")
        tracker.record(fp, "s1")
        lesson = tracker.record(fp, "s1")
        assert lesson is not None
        # Counter should be reset — next two should NOT trigger
        assert tracker.record(fp, "s1") is None
        assert tracker.record(fp, "s1") is None
