"""Tests for CUSUM changepoint detection."""

from __future__ import annotations

from gradata._stats import cusum_changepoints


def test_cusum_detects_single_step_change():
    data = [10, 10, 10, 10, 10, 3, 3, 3, 3, 3]
    points = cusum_changepoints(data)
    assert len(points) >= 1
    assert any(4 <= p <= 6 for p in points)


def test_cusum_detects_multiple_changes():
    data = [20, 20, 20, 5, 5, 5, 20, 20, 20, 5]
    points = cusum_changepoints(data)
    assert len(points) >= 2


def test_cusum_flat_data_no_changepoints():
    data = [5, 5, 5, 5, 5, 5, 5, 5]
    points = cusum_changepoints(data)
    assert points == []


def test_cusum_insufficient_data():
    assert cusum_changepoints([5, 3]) == []
    assert cusum_changepoints([]) == []


def test_cusum_returns_sorted_indices():
    data = [10, 10, 10, 3, 3, 3, 8, 8, 8, 2, 2, 2]
    points = cusum_changepoints(data)
    assert points == sorted(points)


# ── Integration ──────────────────────────────────────────────────────────

from gradata.brain import Brain


def test_convergence_includes_changepoints(tmp_path):
    (tmp_path / "lessons.md").write_text("", encoding="utf-8")
    brain = Brain(str(tmp_path))
    result = brain.convergence()
    assert "changepoints" in result
    assert isinstance(result["changepoints"], list)
