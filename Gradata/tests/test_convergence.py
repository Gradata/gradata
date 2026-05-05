"""Tests for brain.convergence() metric."""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path

from gradata.brain import Brain


def _make_brain_with_corrections(
    num_sessions: int, corrections_per: list[int], categories: list[str] | None = None
) -> Brain:
    """Create a brain with simulated correction events across sessions."""
    d = tempfile.mkdtemp()
    (Path(d) / "lessons.md").write_text("", encoding="utf-8")
    brain = Brain(d)
    for session_num, count in enumerate(corrections_per, start=1):
        cat = (
            categories[session_num - 1] if categories and session_num <= len(categories) else "TEST"
        )
        for _ in range(count):
            with contextlib.suppress(Exception):
                brain.emit(
                    "CORRECTION",
                    "test",
                    {
                        "category": cat,
                        "severity": "minor",
                        "edit_distance": 0.1,
                        "summary": "test correction",
                    },
                    [f"category:{cat}"],
                    session_num,
                )
    return brain


# --- Basic structure tests ---


def test_convergence_returns_dict():
    brain = _make_brain_with_corrections(3, [5, 3, 1])
    result = brain.convergence()
    assert isinstance(result, dict)
    assert "sessions" in result
    assert "corrections_per_session" in result


def test_convergence_counts_match():
    brain = _make_brain_with_corrections(3, [5, 3, 1])
    result = brain.convergence()
    assert result["corrections_per_session"] == [5, 3, 1]


def test_convergence_empty_brain():
    d = tempfile.mkdtemp()
    (Path(d) / "lessons.md").write_text("", encoding="utf-8")
    brain = Brain(d)
    result = brain.convergence()
    assert result["corrections_per_session"] == []


# --- Mann-Kendall trend tests ---


def test_convergence_monotonic_decline_is_converging():
    """Strong monotonic decline should be detected by Mann-Kendall."""
    brain = _make_brain_with_corrections(7, [10, 9, 7, 5, 4, 2, 1])
    result = brain.convergence()
    assert result["trend"] == "converging"


def test_convergence_monotonic_increase_is_diverging():
    """Increasing corrections = diverging."""
    brain = _make_brain_with_corrections(7, [1, 2, 4, 5, 7, 9, 10])
    result = brain.convergence()
    assert result["trend"] == "diverging"


def test_convergence_flat_is_converged():
    """No trend = converged (already stable)."""
    brain = _make_brain_with_corrections(7, [3, 3, 3, 3, 3, 3, 3])
    result = brain.convergence()
    assert result["trend"] == "converged"


def test_convergence_noisy_decline_still_converging():
    """Noisy but overall declining should still detect trend."""
    brain = _make_brain_with_corrections(8, [10, 8, 9, 6, 7, 4, 3, 2])
    result = brain.convergence()
    assert result["trend"] == "converging"


def test_convergence_insufficient_data():
    """Need at least 3 sessions for trend detection."""
    brain = _make_brain_with_corrections(2, [5, 3])
    result = brain.convergence()
    assert result["trend"] == "insufficient_data"


# --- Mann-Kendall p-value ---


def test_convergence_includes_p_value():
    """Mann-Kendall should return a p-value for the trend."""
    brain = _make_brain_with_corrections(7, [10, 9, 7, 5, 4, 2, 1])
    result = brain.convergence()
    assert "p_value" in result
    assert result["p_value"] < 0.05  # strong monotonic trend


def test_convergence_flat_high_p_value():
    """Flat data should have high p-value (no significant trend)."""
    brain = _make_brain_with_corrections(7, [3, 3, 3, 3, 3, 3, 3])
    result = brain.convergence()
    assert result["p_value"] > 0.05


# --- Per-category convergence ---


def test_convergence_per_category():
    """Should return per-category breakdown."""
    d = tempfile.mkdtemp()
    (Path(d) / "lessons.md").write_text("", encoding="utf-8")
    brain = Brain(d)
    # Session 1: 3 TONE, 2 CODE corrections
    for _ in range(3):
        brain.emit(
            "CORRECTION", "test", {"category": "TONE", "severity": "minor"}, ["category:TONE"], 1
        )
    for _ in range(2):
        brain.emit(
            "CORRECTION", "test", {"category": "CODE", "severity": "minor"}, ["category:CODE"], 1
        )
    # Session 2: 1 TONE, 2 CODE
    brain.emit(
        "CORRECTION", "test", {"category": "TONE", "severity": "minor"}, ["category:TONE"], 2
    )
    for _ in range(2):
        brain.emit(
            "CORRECTION", "test", {"category": "CODE", "severity": "minor"}, ["category:CODE"], 2
        )
    # Session 3: 0 TONE, 1 CODE
    brain.emit(
        "CORRECTION", "test", {"category": "CODE", "severity": "minor"}, ["category:CODE"], 3
    )

    result = brain.convergence()
    assert "by_category" in result
    assert "TONE" in result["by_category"]
    assert "CODE" in result["by_category"]
    # TONE went 3→1→0 = converging
    assert result["by_category"]["TONE"]["corrections_per_session"] == [3, 1, 0]
