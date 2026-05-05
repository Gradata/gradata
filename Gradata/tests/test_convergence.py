"""Tests for brain.convergence() metric."""

from __future__ import annotations

import contextlib
import importlib
import os
from pathlib import Path

import gradata._paths as _p
from gradata.brain import Brain


def _make_brain_with_corrections(
    tmp_path: Path,
    _num_sessions: int,
    corrections_per: list[int],
    categories: list[str] | None = None,
) -> Brain:
    """Create a brain with simulated correction events across sessions."""
    d = tmp_path / "brain"
    os.environ["BRAIN_DIR"] = str(d)
    importlib.reload(_p)
    brain = Brain.init(d, domain="test", interactive=False)
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


def test_convergence_returns_dict(tmp_path):
    brain = _make_brain_with_corrections(tmp_path, 3, [5, 3, 1])
    result = brain.convergence()
    assert isinstance(result, dict)
    assert "sessions" in result
    assert "corrections_per_session" in result


def test_convergence_counts_match(tmp_path):
    brain = _make_brain_with_corrections(tmp_path, 3, [5, 3, 1])
    result = brain.convergence()
    assert result["corrections_per_session"] == [5, 3, 1]


def test_convergence_empty_brain(tmp_path):
    brain = _make_brain_with_corrections(tmp_path, 0, [])
    result = brain.convergence()
    assert result["corrections_per_session"] == []


# --- Mann-Kendall trend tests ---


def test_convergence_monotonic_decline_is_converging(tmp_path):
    """Strong monotonic decline should be detected by Mann-Kendall."""
    brain = _make_brain_with_corrections(tmp_path, 7, [10, 9, 7, 5, 4, 2, 1])
    result = brain.convergence()
    assert result["trend"] == "converging"


def test_convergence_monotonic_increase_is_diverging(tmp_path):
    """Increasing corrections = diverging."""
    brain = _make_brain_with_corrections(tmp_path, 7, [1, 2, 4, 5, 7, 9, 10])
    result = brain.convergence()
    assert result["trend"] == "diverging"


def test_convergence_flat_is_converged(tmp_path):
    """No trend = converged (already stable)."""
    brain = _make_brain_with_corrections(tmp_path, 7, [3, 3, 3, 3, 3, 3, 3])
    result = brain.convergence()
    assert result["trend"] == "converged"


def test_convergence_noisy_decline_still_converging(tmp_path):
    """Noisy but overall declining should still detect trend."""
    brain = _make_brain_with_corrections(tmp_path, 8, [10, 8, 9, 6, 7, 4, 3, 2])
    result = brain.convergence()
    assert result["trend"] == "converging"


def test_convergence_insufficient_data(tmp_path):
    """Need at least 3 sessions for trend detection."""
    brain = _make_brain_with_corrections(tmp_path, 2, [5, 3])
    result = brain.convergence()
    assert result["trend"] == "insufficient_data"


# --- Mann-Kendall p-value ---


def test_convergence_includes_p_value(tmp_path):
    """Mann-Kendall should return a p-value for the trend."""
    brain = _make_brain_with_corrections(tmp_path, 7, [10, 9, 7, 5, 4, 2, 1])
    result = brain.convergence()
    assert "p_value" in result
    assert result["p_value"] < 0.05  # strong monotonic trend


def test_convergence_flat_high_p_value(tmp_path):
    """Flat data should have high p-value (no significant trend)."""
    brain = _make_brain_with_corrections(tmp_path, 7, [3, 3, 3, 3, 3, 3, 3])
    result = brain.convergence()
    assert result["p_value"] > 0.05


# --- Per-category convergence ---


def test_convergence_per_category(tmp_path):
    """Should return per-category breakdown."""
    brain = _make_brain_with_corrections(tmp_path, 0, [])
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
