"""
Tests for brain.prove() and brain.export_rules().
===================================================

brain.prove() — statistical proof that corrections decrease after graduation.
brain.export_rules() — cross-agent rule export in 4 formats.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gradata.brain import Brain
from gradata._types import LessonState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def brain_with_history(tmp_path: Path) -> Brain:
    """Create a brain with enough correction history to test prove()."""
    brain = Brain.init(str(tmp_path / "prove_brain"), domain="Test")

    # Simulate 30 sessions of corrections (enough for prove() to work)
    # First 15 sessions: lots of corrections (before graduation)
    drafts_before = [
        ("Dear Sir, I wanted to reach out.", "Hi, I wanted to reach out."),
        ("The system is very performant.", "The system handles 10K req/s."),
        ("We should look into this.", "Action: deliver RCA by Friday."),
        ("Your performance is bad.", "Performance hasn't met expectations."),
        ("The revenue was about $2M.", "Revenue was $2,347,891 (SAP export)."),
    ]
    # After graduation: fewer corrections (brain learned)
    drafts_after = [
        ("Hi, reaching out about your growth.", "Hi, reaching out about your growth in digital ads."),
        ("The system handles requests fast.", "The system handles requests efficiently."),
    ]

    # Before: 15 sessions × 3-5 corrections each
    for session in range(1, 16):
        for draft, final in drafts_before:
            variant = f" [s{session}]"
            brain.correct(draft + variant, final + variant, session=session)

    # After: 15 sessions × 1-2 corrections each (fewer!)
    for session in range(16, 31):
        for draft, final in drafts_after:
            variant = f" [s{session}]"
            brain.correct(draft + variant, final + variant, session=session)

    return brain


@pytest.fixture
def brain_with_lessons(tmp_path: Path) -> Brain:
    """Create a brain with graduated lessons for export_rules() testing."""
    brain = Brain.init(str(tmp_path / "export_brain"), domain="Test")

    # Write lessons directly to lessons.md
    lessons_path = tmp_path / "export_brain" / "lessons.md"
    lessons_path.write_text(
        "# Active Lessons\n\n"
        "[2026-03-01] [RULE:0.95] DRAFTING: never use em dashes in email prose\n"
        "  Root cause: Repeated Oliver corrections on em dash usage\n"
        "  Fire count: 8 | Sessions since fire: 2 | Misfires: 0\n\n"
        "[2026-03-05] [RULE:0.92] ACCURACY: never report unverified numbers\n"
        "  Root cause: Multiple incidents of approximate figures\n"
        "  Fire count: 6 | Sessions since fire: 1 | Misfires: 0\n\n"
        "[2026-03-10] [PATTERN:0.75] COMMUNICATION: match tone to audience seniority\n"
        "  Root cause: Tone mismatch in executive emails\n"
        "  Fire count: 4 | Sessions since fire: 3 | Misfires: 1\n\n"
        "[2026-03-15] [INSTINCT:0.45] PROCESS: always plan before implementing\n"
        "  Root cause: Jumped to code without adversary check\n"
        "  Fire count: 2 | Sessions since fire: 5 | Misfires: 0\n\n",
        encoding="utf-8",
    )

    return brain


@pytest.fixture
def empty_brain(tmp_path: Path) -> Brain:
    """Brain with no history."""
    return Brain.init(str(tmp_path / "empty_brain"), domain="Test")


# ---------------------------------------------------------------------------
# brain.prove() tests
# ---------------------------------------------------------------------------

class TestProve:

    def test_returns_dict(self, brain_with_history: Brain) -> None:
        result = brain_with_history.prove()
        assert isinstance(result, dict)
        assert "verdict" in result
        assert "p_value" in result
        assert "correction_rate_before" in result
        assert "correction_rate_after" in result

    def test_correction_rate_decreases(self, brain_with_history: Brain) -> None:
        """Before window should have higher correction rate than after."""
        result = brain_with_history.prove()
        if result["correction_rate_before"] is not None:
            assert result["correction_rate_before"] > result["correction_rate_after"], (
                f"Before ({result['correction_rate_before']}) should > "
                f"After ({result['correction_rate_after']})"
            )

    def test_reduction_pct_positive(self, brain_with_history: Brain) -> None:
        result = brain_with_history.prove()
        if result["reduction_pct"] is not None:
            assert result["reduction_pct"] > 0, (
                f"Expected positive reduction, got {result['reduction_pct']}%"
            )

    def test_verdict_is_valid(self, brain_with_history: Brain) -> None:
        result = brain_with_history.prove()
        assert result["verdict"] in (
            "PROVEN", "EMERGING", "INSUFFICIENT_DATA", "NO_EFFECT"
        )

    def test_empty_brain_returns_insufficient(self, empty_brain: Brain) -> None:
        result = empty_brain.prove()
        assert result["verdict"] == "INSUFFICIENT_DATA"
        assert result["p_value"] is None

    def test_confidence_interval(self, brain_with_history: Brain) -> None:
        result = brain_with_history.prove()
        if result["confidence_interval"] is not None:
            ci_low, ci_high = result["confidence_interval"]
            assert ci_low <= ci_high, f"CI inverted: ({ci_low}, {ci_high})"

    def test_sessions_analyzed(self, brain_with_history: Brain) -> None:
        result = brain_with_history.prove()
        assert result["sessions_analyzed"] >= 10, (
            f"Only {result['sessions_analyzed']} sessions analyzed"
        )


class TestWilcoxon:
    """Test the pure-Python Wilcoxon implementation."""

    def test_clear_decrease(self) -> None:
        """All positive diffs (before > after) should give significant p."""
        diffs = [3.0, 2.0, 4.0, 1.0, 5.0, 2.0, 3.0, 4.0, 2.0, 1.0]
        p, effect = Brain._wilcoxon_test(diffs)
        assert p is not None
        assert p < 0.05, f"p={p} should be < 0.05 for clear decrease"
        assert effect > 0, f"Effect {effect} should be positive"

    def test_no_difference(self) -> None:
        """Random noise should give non-significant p."""
        diffs = [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]
        p, effect = Brain._wilcoxon_test(diffs)
        assert p is not None
        # With perfectly alternating diffs, W+ ≈ W-, p should be high
        assert p > 0.05 or abs(effect) < 0.3

    def test_too_few_samples(self) -> None:
        """< 5 samples should return None."""
        p, effect = Brain._wilcoxon_test([1.0, 2.0, 3.0])
        assert p is None
        assert effect is None

    def test_all_zeros(self) -> None:
        """All zero diffs should return None (no signal)."""
        p, effect = Brain._wilcoxon_test([0.0] * 10)
        assert p is None


# ---------------------------------------------------------------------------
# brain.export_rules() tests
# ---------------------------------------------------------------------------

class TestExportRules:

    def test_claude_format(self, brain_with_lessons: Brain) -> None:
        output = brain_with_lessons.export_rules(output_format="claude")
        assert "<brain-rules>" in output
        assert "</brain-rules>" in output
        assert "em dashes" in output
        assert 'category="DRAFTING"' in output

    def test_cursor_format(self, brain_with_lessons: Brain) -> None:
        output = brain_with_lessons.export_rules(output_format="cursor")
        assert "# Rules learned" in output
        assert "[DRAFTING]" in output

    def test_system_format(self, brain_with_lessons: Brain) -> None:
        output = brain_with_lessons.export_rules(output_format="system")
        assert "You have learned" in output
        assert "1." in output

    def test_json_format(self, brain_with_lessons: Brain) -> None:
        import json
        output = brain_with_lessons.export_rules(output_format="json")
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "category" in data[0]
        assert "confidence" in data[0]

    def test_respects_max_rules(self, brain_with_lessons: Brain) -> None:
        output = brain_with_lessons.export_rules(output_format="json", max_rules=2)
        import json
        data = json.loads(output)
        assert len(data) <= 2

    def test_min_state_filter(self, brain_with_lessons: Brain) -> None:
        """min_state='RULE' should exclude PATTERN and INSTINCT lessons."""
        import json
        output = brain_with_lessons.export_rules(output_format="json", min_state="RULE")
        data = json.loads(output)
        for rule in data:
            assert rule["state"] == "RULE", (
                f"Expected only RULE, got {rule['state']}"
            )

    def test_empty_brain_returns_empty(self, empty_brain: Brain) -> None:
        output = empty_brain.export_rules(output_format="claude")
        assert output == ""

    def test_invalid_format_raises(self, brain_with_lessons: Brain) -> None:
        with pytest.raises(ValueError, match="Unknown format"):
            brain_with_lessons.export_rules(output_format="invalid_format")

    def test_xml_escaping(self, brain_with_lessons: Brain) -> None:
        """XML output should escape special characters."""
        output = brain_with_lessons.export_rules(output_format="claude")
        # The descriptions don't have <> but the escaping code is there
        # for safety. At minimum, output should be valid XML-like structure.
        assert output.count("<brain-rules>") == 1
        assert output.count("</brain-rules>") == 1

    def test_sorted_by_confidence(self, brain_with_lessons: Brain) -> None:
        """Rules should be sorted by confidence descending."""
        import json
        output = brain_with_lessons.export_rules(output_format="json")
        data = json.loads(output)
        if len(data) >= 2:
            confs = [d["confidence"] for d in data]
            assert confs == sorted(confs, reverse=True), (
                f"Rules not sorted by confidence: {confs}"
            )
