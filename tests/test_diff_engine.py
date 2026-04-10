"""Tests for diff engine semantic severity adjustment."""

import pytest

from gradata.enhancements.diff_engine import DiffResult, adjust_severity_by_semantics


class TestSemanticSeverityAdjustment:
    def test_high_similarity_downgrades_moderate_to_minor(self):
        result = DiffResult(
            edit_distance=0.25,
            compression_distance=0.20,
            changed_sections=[],
            severity="moderate",
            summary_stats={"lines_added": 2, "lines_removed": 1, "lines_changed": 1},
        )
        adjusted = adjust_severity_by_semantics(result, semantic_similarity=0.90)
        assert adjusted.severity == "minor"
        assert adjusted.semantic_similarity == 0.90

    def test_low_similarity_no_change(self):
        result = DiffResult(
            edit_distance=0.25,
            compression_distance=0.20,
            changed_sections=[],
            severity="moderate",
            summary_stats={"lines_added": 2, "lines_removed": 1, "lines_changed": 1},
        )
        adjusted = adjust_severity_by_semantics(result, semantic_similarity=0.50)
        assert adjusted.severity == "moderate"

    def test_as_is_not_downgraded(self):
        result = DiffResult(
            edit_distance=0.01,
            compression_distance=0.01,
            changed_sections=[],
            severity="as-is",
            summary_stats={"lines_added": 0, "lines_removed": 0, "lines_changed": 0},
        )
        adjusted = adjust_severity_by_semantics(result, semantic_similarity=0.95)
        assert adjusted.severity == "as-is"

    def test_discarded_downgrades_to_major(self):
        result = DiffResult(
            edit_distance=0.85,
            compression_distance=0.82,
            changed_sections=[],
            severity="discarded",
            summary_stats={"lines_added": 10, "lines_removed": 8, "lines_changed": 8},
        )
        adjusted = adjust_severity_by_semantics(result, semantic_similarity=0.92)
        assert adjusted.severity == "major"
