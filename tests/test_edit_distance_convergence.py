"""Tests for edit distance convergence tracking."""
from __future__ import annotations

import tempfile
from pathlib import Path

from gradata.brain import Brain


def _make_brain(corrections: list[tuple[int, float]]) -> Brain:
    """Create a brain with correction events containing edit_distance.

    Args:
        corrections: list of (session, edit_distance) tuples.
    """
    d = tempfile.mkdtemp()
    (Path(d) / "lessons.md").write_text("", encoding="utf-8")
    brain = Brain(d)
    for session, ed in corrections:
        brain.emit("CORRECTION", "test", {
            "category": "TEST", "severity": "minor",
            "edit_distance": ed, "summary": "test correction",
        }, [f"category:TEST"], session)
    return brain


def test_convergence_includes_edit_distance_fields():
    """convergence() returns edit distance fields even when empty."""
    d = tempfile.mkdtemp()
    (Path(d) / "lessons.md").write_text("", encoding="utf-8")
    brain = Brain(d)
    result = brain.convergence()
    assert "edit_distance_per_session" in result
    assert "edit_distance_trend" in result
    assert isinstance(result["edit_distance_per_session"], list)


def test_edit_distance_trend_improving():
    """Declining edit distances across sessions show 'improving' trend."""
    # 5 sessions with declining average edit distance
    corrections = [
        (1, 0.8), (1, 0.7),
        (2, 0.6), (2, 0.65),
        (3, 0.5), (3, 0.45),
        (4, 0.35), (4, 0.3),
        (5, 0.2), (5, 0.15),
    ]
    brain = _make_brain(corrections)
    result = brain.convergence()
    assert len(result["edit_distance_per_session"]) == 5
    assert result["edit_distance_trend"] == "improving"


def test_edit_distance_trend_worsening():
    """Increasing edit distances show 'worsening' trend."""
    corrections = [
        (1, 0.1), (1, 0.15),
        (2, 0.3), (2, 0.25),
        (3, 0.4), (3, 0.45),
        (4, 0.6), (4, 0.55),
        (5, 0.7), (5, 0.75),
    ]
    brain = _make_brain(corrections)
    result = brain.convergence()
    assert result["edit_distance_trend"] == "worsening"


def test_edit_distance_empty_brain():
    """Empty brain returns empty edit distance data."""
    d = tempfile.mkdtemp()
    (Path(d) / "lessons.md").write_text("", encoding="utf-8")
    brain = Brain(d)
    result = brain.convergence()
    assert result["edit_distance_per_session"] == []
    assert result["edit_distance_trend"] == "insufficient_data"


def test_edit_distance_insufficient_sessions():
    """Fewer than 3 sessions returns insufficient_data trend."""
    corrections = [(1, 0.5), (2, 0.3)]
    brain = _make_brain(corrections)
    result = brain.convergence()
    assert len(result["edit_distance_per_session"]) == 2
    assert result["edit_distance_trend"] == "insufficient_data"


def test_edit_distance_values_are_rounded():
    """Edit distance values are rounded to 4 decimal places."""
    corrections = [
        (1, 0.123456789),
        (2, 0.987654321),
        (3, 0.555555555),
    ]
    brain = _make_brain(corrections)
    result = brain.convergence()
    for val in result["edit_distance_per_session"]:
        # Check that the value has at most 4 decimal places
        assert val == round(val, 4)
