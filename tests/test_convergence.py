"""Tests for brain.convergence() metric."""
from __future__ import annotations

import tempfile
from pathlib import Path

from gradata.brain import Brain


def _make_brain_with_corrections(num_sessions: int, corrections_per: list[int]) -> Brain:
    """Create a brain with simulated correction events across sessions."""
    d = tempfile.mkdtemp()
    (Path(d) / "lessons.md").write_text("", encoding="utf-8")
    brain = Brain(d)
    for session_num, count in enumerate(corrections_per, start=1):
        for _ in range(count):
            try:
                brain.emit("CORRECTION", "test", {
                    "category": "TEST", "severity": "minor",
                    "edit_distance": 0.1, "summary": "test correction",
                }, ["category:TEST"], session_num)
            except Exception:
                pass
    return brain


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


def test_convergence_includes_trend():
    brain = _make_brain_with_corrections(5, [10, 8, 6, 4, 2])
    result = brain.convergence()
    assert "trend" in result
    assert result["trend"] == "converging"  # declining corrections


def test_convergence_flat_is_converged():
    brain = _make_brain_with_corrections(5, [2, 2, 2, 2, 2])
    result = brain.convergence()
    assert result["trend"] == "converged"
