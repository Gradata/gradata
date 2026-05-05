"""Tests for brain.prove() — quality proof generation."""

from unittest.mock import patch

from gradata.brain import Brain


def _mock_convergence(
    trend, p_value, sessions, corrections, by_category=None, corrections_per_session=None
):
    if corrections_per_session is None:
        corrections_per_session = [corrections // max(1, sessions)] * sessions
    return {
        "sessions": list(range(1, sessions + 1)),
        "corrections_per_session": corrections_per_session,
        "trend": trend,
        "p_value": p_value,
        "changepoints": [],
        "by_category": by_category or {},
        "total_corrections": corrections,
        "total_sessions": sessions,
        "edit_distance_per_session": [],
        "edit_distance_trend": "insufficient_data",
    }


def test_prove_strong_evidence(tmp_path):
    """Strong proof: converging trend, low p-value, good effort ratio."""
    brain = Brain(str(tmp_path))
    # Decreasing corrections: initial avg=10, recent avg=2 -> effort_ratio=0.2
    cps = [10, 10, 10, 8, 6, 5, 4, 3, 2, 2]
    conv = _mock_convergence("converging", 0.01, 10, sum(cps), corrections_per_session=cps)
    with patch.object(brain, "_get_convergence", return_value=conv):
        result = brain.prove()
    assert result["proven"] is True
    assert result["confidence_level"] == "strong"
    assert "reduces correction effort" in result["summary"]


def test_prove_insufficient_data(tmp_path):
    """Not proven with too few sessions."""
    brain = Brain(str(tmp_path))
    conv = _mock_convergence("insufficient_data", 1.0, 1, 2)
    with patch.object(brain, "_get_convergence", return_value=conv):
        result = brain.prove()
    assert result["proven"] is False
    assert result["confidence_level"] == "insufficient"


def test_prove_moderate_evidence(tmp_path):
    """Moderate proof: converged but not statistically strong."""
    brain = Brain(str(tmp_path))
    # Decreasing corrections: initial avg=6, recent avg=4 -> effort_ratio=0.67
    cps = [6, 6, 6, 5, 5, 4, 4, 4]
    conv = _mock_convergence("converged", 0.5, 8, sum(cps), corrections_per_session=cps)
    with patch.object(brain, "_get_convergence", return_value=conv):
        result = brain.prove()
    assert result["proven"] is True
    assert result["confidence_level"] in ("moderate", "weak")


def test_prove_returns_all_fields(tmp_path):
    """Proof document includes all expected fields."""
    brain = Brain(str(tmp_path))
    cps = [10, 10, 10, 8, 6, 5, 4, 3, 2, 2]
    conv = _mock_convergence("converging", 0.02, 10, sum(cps), corrections_per_session=cps)
    with patch.object(brain, "_get_convergence", return_value=conv):
        result = brain.prove()
    assert "proven" in result
    assert "confidence_level" in result
    assert "evidence" in result
    assert "summary" in result
    evidence = result["evidence"]
    for key in [
        "convergence_trend",
        "p_value",
        "effort_ratio",
        "rule_count",
        "correction_count",
        "sessions",
        "categories_converged",
    ]:
        assert key in evidence, f"Missing evidence key: {key}"


def test_prove_tracks_converged_categories(tmp_path):
    """Proof lists which categories have converged."""
    brain = Brain(str(tmp_path))
    cps = [10, 10, 10, 8, 6, 5, 4, 3, 2, 2]
    conv = _mock_convergence(
        "converging",
        0.02,
        10,
        sum(cps),
        corrections_per_session=cps,
        by_category={
            "DRAFTING": {"trend": "converged", "p_value": 0.8},
            "TONE": {"trend": "converging", "p_value": 0.03},
            "ACCURACY": {"trend": "diverging", "p_value": 0.01},
        },
    )
    with patch.object(brain, "_get_convergence", return_value=conv):
        result = brain.prove()
    assert "DRAFTING" in result["evidence"]["categories_converged"]
    assert "ACCURACY" not in result["evidence"]["categories_converged"]
    assert result["evidence"]["strongest_category"] == "TONE"
