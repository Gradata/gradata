"""Tests for convergence-gated extraction — skip LLM when category converged."""
from unittest.mock import patch, MagicMock
from gradata.brain import Brain


def test_extraction_skipped_when_converged(tmp_path):
    """Behavioral extraction is skipped when category trend is converged."""
    brain = Brain.init(str(tmp_path / "test-brain"), domain="test", interactive=False)

    converged_result = {
        "sessions": [1, 2, 3, 4, 5],
        "corrections_per_session": [10, 8, 5, 5, 5],
        "trend": "converged",
        "p_value": 0.8,
        "by_category": {
            "DRAFTING": {"corrections_per_session": [5, 4, 2, 2, 2], "trend": "converged", "p_value": 0.9},
        },
        "total_corrections": 33,
        "total_sessions": 5,
    }

    with patch.object(brain, "_get_convergence", return_value=converged_result):
        with patch("gradata.enhancements.edit_classifier.extract_behavioral_instruction") as mock_extract:
            brain.correct(
                "The system is working good",
                "The system is working well",
                category="DRAFTING",
            )
            mock_extract.assert_not_called()


def test_extraction_runs_when_diverging(tmp_path):
    """Behavioral extraction runs when category trend is diverging."""
    brain = Brain.init(str(tmp_path / "test-brain"), domain="test", interactive=False)

    diverging_result = {
        "sessions": [1, 2, 3],
        "corrections_per_session": [2, 5, 10],
        "trend": "diverging",
        "p_value": 0.02,
        "by_category": {
            "DRAFTING": {"corrections_per_session": [1, 3, 8], "trend": "diverging", "p_value": 0.01},
        },
        "total_corrections": 17,
        "total_sessions": 3,
    }

    with patch.object(brain, "_get_convergence", return_value=diverging_result):
        with patch("gradata.enhancements.behavioral_extractor.extract_instruction", return_value="Use 'well' instead of 'good'") as mock_extract:
            brain.correct(
                "The system is working good",
                "The system is working well",
                category="DRAFTING",
            )
            mock_extract.assert_called_once()


def test_convergence_cache_per_session(tmp_path):
    """Convergence result is cached within a session, refreshed across sessions."""
    brain = Brain.init(str(tmp_path / "test-brain"), domain="test", interactive=False)

    with patch("gradata._core.brain_convergence", return_value={"trend": "converging", "by_category": {}}) as mock_conv:
        brain._get_convergence()
        brain._get_convergence()
        assert mock_conv.call_count == 1  # Cached

        # Simulate session change by invalidating the cache session
        brain._convergence_session = -1
        brain._get_convergence()
        assert mock_conv.call_count == 2  # New session
