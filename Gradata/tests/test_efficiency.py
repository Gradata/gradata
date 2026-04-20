"""Tests for brain.efficiency() — effort-saved metric."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from gradata.brain import Brain


def _make_brain(tmp_path: Path) -> Brain:
    (tmp_path / "lessons.md").write_text("", encoding="utf-8")
    return Brain(str(tmp_path))


def _mock_convergence(corrections_per_session):
    return {
        "sessions": list(range(1, len(corrections_per_session) + 1)),
        "corrections_per_session": corrections_per_session,
        "trend": "converging",
        "p_value": 0.01,
        "by_category": {},
        "total_corrections": sum(corrections_per_session),
        "total_sessions": len(corrections_per_session),
    }


def test_efficiency_ratio_declining(tmp_path):
    brain = _make_brain(tmp_path)
    conv = _mock_convergence([10, 12, 8, 5, 4, 3])
    with patch.object(brain, "_get_convergence", return_value=conv):
        result = brain.efficiency()
    assert "effort_ratio" in result
    assert result["effort_ratio"] < 1.0
    assert result["corrections_initial"] == 10.0  # avg(10,12,8)
    assert result["corrections_recent"] == 4.0    # avg(5,4,3)


def test_efficiency_ratio_no_improvement(tmp_path):
    brain = _make_brain(tmp_path)
    conv = _mock_convergence([5, 5, 5, 5, 5, 5])
    with patch.object(brain, "_get_convergence", return_value=conv):
        result = brain.efficiency()
    assert result["effort_ratio"] == 1.0


def test_efficiency_insufficient_data(tmp_path):
    brain = _make_brain(tmp_path)
    conv = _mock_convergence([5, 3])
    with patch.object(brain, "_get_convergence", return_value=conv):
        result = brain.efficiency()
    assert result["effort_ratio"] == 1.0
    assert result["corrections_initial"] == 0
    assert result["corrections_recent"] == 0


def test_efficiency_no_time_fields_by_default(tmp_path):
    brain = _make_brain(tmp_path)
    conv = _mock_convergence([10, 12, 8, 5, 4, 3])
    with patch.object(brain, "_get_convergence", return_value=conv):
        result = brain.efficiency()
    assert "estimated_seconds_saved" not in result


def test_efficiency_with_time_estimate(tmp_path):
    brain = _make_brain(tmp_path)
    conv = _mock_convergence([10, 12, 8, 5, 4, 3])
    with patch.object(brain, "_get_convergence", return_value=conv):
        result = brain.efficiency(estimate_time=True)
    assert "estimated_seconds_saved" in result
    assert isinstance(result["estimated_seconds_saved"], (int, float))
    assert result["estimated_seconds_saved"] > 0
