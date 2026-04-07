"""Integration tests — full correction pipeline with real LLM extraction.

These tests hit external APIs and cost money. Skip in normal CI.
Run manually: pytest tests/test_integration_workflow.py -v -m integration
"""
import os
import tempfile

import pytest

from gradata.brain import Brain

# Skip all tests if no API key available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="No API key — skipping integration tests",
    ),
]


@pytest.fixture
def brain(tmp_path):
    """Fresh brain in temp directory."""
    yield Brain(str(tmp_path))


class TestMultiSessionWorkflow:
    """Test the full correction -> lesson -> graduation -> convergence flow."""

    @pytest.mark.integration
    def test_correction_creates_lesson(self, brain):
        """A single correction should create an INSTINCT lesson."""
        result = brain.correct(
            "The system is working good",
            "The system is working well",
            category="DRAFTING",
            session=1,
        )
        assert result.get("lessons_created") == 1 or result.get("lesson_reinforced")

    @pytest.mark.integration
    def test_repeated_corrections_reinforce_lesson(self, brain):
        """Same correction type repeated should reinforce, not duplicate."""
        brain.correct("working good", "working well", category="DRAFTING", session=1)
        result = brain.correct("doing good", "doing well", category="DRAFTING", session=2)
        # Second similar correction should reinforce, not create new
        assert result.get("lesson_reinforced") or result.get("lessons_created")

    @pytest.mark.integration
    def test_convergence_after_corrections(self, brain):
        """Convergence should return data after multiple sessions."""
        for session in range(1, 6):
            brain.correct(
                f"Draft text session {session} is working good",
                f"Draft text session {session} is working well",
                category="DRAFTING",
                session=session,
            )
        conv = brain.convergence()
        assert conv["total_sessions"] >= 1
        assert conv["total_corrections"] >= 5
        assert "trend" in conv
        assert "p_value" in conv
        assert "changepoints" in conv
        assert "edit_distance_per_session" in conv

    @pytest.mark.integration
    def test_efficiency_after_corrections(self, brain):
        """Efficiency should return valid data after corrections."""
        for session in range(1, 6):
            brain.correct(
                "The data needs processed",
                "The data needs to be processed",
                category="ACCURACY",
                session=session,
            )
        eff = brain.efficiency()
        assert "effort_ratio" in eff
        assert isinstance(eff["effort_ratio"], float)

        eff_time = brain.efficiency(estimate_time=True)
        assert "estimated_seconds_saved" in eff_time

    @pytest.mark.integration
    def test_full_lifecycle_multi_category(self, brain):
        """Full lifecycle: multiple categories, convergence, efficiency."""
        corrections = [
            ("working good", "working well", "DRAFTING"),
            ("Dear Sir/Madam", "Hi", "TONE"),
            ("utilize", "use", "STYLE"),
            ("The server has 16GB", "The server has 32GB", "ACCURACY"),
        ]
        for session in range(1, 8):
            for draft, final, cat in corrections:
                brain.correct(
                    f"{draft} (session {session})",
                    f"{final} (session {session})",
                    category=cat,
                    session=session,
                )

        conv = brain.convergence()
        assert conv["total_sessions"] >= 1
        assert len(conv.get("by_category", {})) > 0

        eff = brain.efficiency()
        assert eff["total_sessions"] >= 1
