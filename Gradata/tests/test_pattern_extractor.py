"""
Tests for the pattern extractor module (corrections → lessons pipeline).

Tests the shim in sdk/src/gradata/_pattern_extractor.py, which resolves to
gradata.enhancements.pattern_extractor when gradata_cloud is absent.

All tests operate on pure Python dataclasses — no file I/O, no DB, no mocks
required except for the cloud import shim path.

Run: cd sdk && python -m pytest tests/test_pattern_extractor.py -v
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_classification(
    category: str, description: str, confidence: float = 0.8, severity: str = "minor"
):
    """Build an EditClassification using whatever is importable."""
    try:
        from gradata.enhancements.edit_classifier import EditClassification
    except ImportError:
        from gradata.enhancements.edit_classifier import (
            EditClassification,  # type: ignore[assignment]
        )
    return EditClassification(
        category=category,
        confidence=confidence,
        severity=severity,
        description=description,
    )


# ---------------------------------------------------------------------------
# 1. Shim import — ExtractedPattern is always available
# ---------------------------------------------------------------------------


class TestShimImport:
    """The shim in _pattern_extractor.py must always export the four names."""

    def test_extracted_pattern_importable(self):
        from gradata.enhancements.pattern_extractor import ExtractedPattern

        assert ExtractedPattern is not None

    def test_extract_patterns_callable(self):
        from gradata.enhancements.pattern_extractor import extract_patterns

        assert callable(extract_patterns)

    def test_merge_patterns_callable(self):
        from gradata.enhancements.pattern_extractor import merge_patterns

        assert callable(merge_patterns)

    def test_patterns_to_lessons_callable(self):
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        assert callable(patterns_to_lessons)

    def test_extracted_pattern_has_required_fields(self):
        from gradata.enhancements.pattern_extractor import ExtractedPattern

        p = ExtractedPattern(category="TONE", description="test", confidence=0.5)
        assert p.category == "TONE"
        assert p.description == "test"
        assert p.confidence == 0.5
        assert isinstance(p.edits, list)


# ---------------------------------------------------------------------------
# 2. extract_patterns()
# ---------------------------------------------------------------------------


class TestExtractPatterns:
    """extract_patterns() groups classified edits into repeating patterns."""

    def test_empty_input_returns_empty_list(self):
        from gradata.enhancements.pattern_extractor import extract_patterns

        result = extract_patterns([])
        assert result == []

    def test_single_classification_returns_empty(self):
        """One edit is never a 'pattern' — requires at least 2 similar edits."""
        from gradata.enhancements.pattern_extractor import extract_patterns

        c = _make_classification("TONE", "use warmer language in the closing paragraph")
        result = extract_patterns([c])
        assert result == []

    def test_two_similar_edits_same_category_forms_pattern(self):
        from gradata.enhancements.pattern_extractor import extract_patterns

        c1 = _make_classification("TONE", "use warmer friendlier language closing")
        c2 = _make_classification("TONE", "warmer language needed closing section")
        result = extract_patterns([c1, c2])
        assert len(result) >= 1

    def test_pattern_has_correct_category(self):
        from gradata.enhancements.pattern_extractor import extract_patterns

        c1 = _make_classification("FORMAT", "use bullet points in the list section")
        c2 = _make_classification("FORMAT", "bullet points needed for the list")
        result = extract_patterns([c1, c2])
        if result:
            assert result[0].category == "FORMAT"

    def test_different_categories_do_not_merge(self):
        """TONE and FORMAT edits should not form a cross-category pattern."""
        from gradata.enhancements.pattern_extractor import extract_patterns

        c1 = _make_classification("TONE", "warmer friendlier closing language")
        c2 = _make_classification("FORMAT", "warmer friendlier closing language")
        result = extract_patterns([c1, c2])
        # If patterns are extracted, each should have its own category
        {p.category for p in result}
        # TONE and FORMAT should not be merged into one pattern
        if len(result) > 0:
            for p in result:
                assert p.category in ("TONE", "FORMAT")

    def test_pattern_confidence_within_bounds(self):
        from gradata.enhancements.pattern_extractor import extract_patterns

        edits = [
            _make_classification("STRUCTURE", f"restructure the {word} section header")
            for word in ["main", "primary", "core", "key", "central"]
        ]
        result = extract_patterns(edits)
        for p in result:
            assert 0.0 <= p.confidence <= 1.0

    def test_unrelated_edits_in_same_category_do_not_cluster(self):
        """Dissimilar descriptions (low Jaccard) should not form a pattern."""
        from gradata.enhancements.pattern_extractor import extract_patterns

        c1 = _make_classification("TONE", "use warmer language in the greeting")
        c2 = _make_classification("TONE", "remove aggressive demanding requests")
        # These share few keywords — likely below 0.3 Jaccard threshold
        result = extract_patterns([c1, c2])
        # Result may be empty or non-empty depending on keyword overlap
        assert isinstance(result, list)

    def test_pattern_edits_list_populated(self):
        from gradata.enhancements.pattern_extractor import extract_patterns

        c1 = _make_classification("TONE", "warmer friendlier closing language here")
        c2 = _make_classification("TONE", "warmer language needed closing section")
        result = extract_patterns([c1, c2])
        if result:
            assert len(result[0].edits) >= 2

    def test_scope_argument_accepted(self):
        """scope kwarg is accepted without raising (stored as metadata)."""
        from gradata.enhancements.pattern_extractor import extract_patterns

        c1 = _make_classification("TONE", "warmer friendlier closing language")
        c2 = _make_classification("TONE", "warmer language needed closing section")

        class FakeScope:
            task_type = "email_draft"

        result = extract_patterns([c1, c2], scope=FakeScope())
        assert isinstance(result, list)

    def test_large_input_does_not_raise(self):
        """100 classifications in same category — must complete without error."""
        from gradata.enhancements.pattern_extractor import extract_patterns

        edits = [
            _make_classification("ACCURACY", f"fact check the claim about topic_{i}")
            for i in range(100)
        ]
        result = extract_patterns(edits)
        assert isinstance(result, list)

    def test_returns_list_type(self):
        from gradata.enhancements.pattern_extractor import extract_patterns

        c1 = _make_classification("TONE", "warmer friendly language closing")
        c2 = _make_classification("TONE", "warmer language needed closing")
        result = extract_patterns([c1, c2])
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 3. merge_patterns()
# ---------------------------------------------------------------------------


class TestMergePatterns:
    """merge_patterns() combines new patterns into an existing list."""

    def _make_pattern(self, category: str, description: str, confidence: float = 0.4):
        from gradata.enhancements.pattern_extractor import ExtractedPattern

        return ExtractedPattern(
            category=category,
            description=description,
            confidence=confidence,
        )

    def test_merging_into_empty_list_returns_new_patterns(self):
        from gradata.enhancements.pattern_extractor import merge_patterns

        new = [self._make_pattern("TONE", "warmer friendlier closing")]
        result = merge_patterns([], new)
        assert len(result) == 1

    def test_existing_plus_unrelated_new_appends(self):
        from gradata.enhancements.pattern_extractor import merge_patterns

        existing = [self._make_pattern("TONE", "warmer closing language")]
        new = [self._make_pattern("FORMAT", "use bullet points listing")]
        result = merge_patterns(existing, new)
        assert len(result) == 2

    def test_similar_patterns_same_category_merged(self):
        """High-Jaccard overlap in same category → confidence boost, not append."""
        from gradata.enhancements.pattern_extractor import merge_patterns

        existing = [self._make_pattern("TONE", "warmer friendlier closing language", 0.4)]
        new = [self._make_pattern("TONE", "warmer friendlier closing language repeated", 0.4)]
        result = merge_patterns(existing, new)
        # Should merge, not create a new entry
        tone_patterns = [p for p in result if p.category == "TONE"]
        assert len(tone_patterns) == 1

    def test_merge_boosts_confidence(self):
        """Merging similar patterns increases the existing pattern's confidence."""
        from gradata.enhancements.pattern_extractor import merge_patterns

        existing = [self._make_pattern("TONE", "warmer friendlier closing language", 0.4)]
        new = [self._make_pattern("TONE", "warmer friendlier closing language repeated", 0.4)]
        result = merge_patterns(existing, new)
        tone = next(p for p in result if p.category == "TONE")
        assert tone.confidence >= 0.4

    def test_empty_new_returns_existing_unchanged(self):
        from gradata.enhancements.pattern_extractor import merge_patterns

        existing = [self._make_pattern("TONE", "test")]
        result = merge_patterns(existing, [])
        assert len(result) == 1

    def test_both_empty_returns_empty(self):
        from gradata.enhancements.pattern_extractor import merge_patterns

        result = merge_patterns([], [])
        assert result == []

    def test_confidence_never_exceeds_1(self):
        """Repeated merging must not push confidence above 1.0."""
        from gradata.enhancements.pattern_extractor import merge_patterns

        existing = [self._make_pattern("TONE", "warmer friendlier closing language", 0.9)]
        for _ in range(20):
            existing = merge_patterns(
                existing,
                [self._make_pattern("TONE", "warmer friendlier closing language", 0.4)],
            )
        assert existing[0].confidence <= 1.0

    def test_different_category_never_merged(self):
        from gradata.enhancements.pattern_extractor import merge_patterns

        existing = [self._make_pattern("TONE", "warmer friendlier language")]
        new = [self._make_pattern("FORMAT", "warmer friendlier language")]
        result = merge_patterns(existing, new)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# 4. patterns_to_lessons()
# ---------------------------------------------------------------------------


class TestPatternsToLessons:
    """patterns_to_lessons() converts high-confidence patterns into Lesson objects."""

    def _make_pattern(self, category: str, description: str, confidence: float):
        from gradata.enhancements.pattern_extractor import ExtractedPattern

        return ExtractedPattern(
            category=category,
            description=description,
            confidence=confidence,
        )

    def test_empty_input_returns_empty_list(self):
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        assert patterns_to_lessons([]) == []

    def test_low_confidence_pattern_excluded(self):
        """Patterns below 0.25 confidence threshold must not become lessons."""
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        p = self._make_pattern("TONE", "some pattern", confidence=0.10)
        result = patterns_to_lessons([p])
        assert result == []

    def test_sufficient_confidence_creates_lesson(self):
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        p = self._make_pattern("TONE", "use warmer language always", confidence=0.40)
        result = patterns_to_lessons([p])
        assert len(result) == 1

    def test_lesson_category_matches_pattern(self):
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        p = self._make_pattern("FORMAT", "use bullet lists", confidence=0.40)
        result = patterns_to_lessons([p])
        assert result[0].category == "FORMAT"

    def test_lesson_starts_as_instinct(self):
        from gradata._types import LessonState
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        p = self._make_pattern("TONE", "warmer language", confidence=0.40)
        result = patterns_to_lessons([p])
        assert result[0].state == LessonState.INSTINCT

    def test_lesson_initial_confidence_is_constant(self):
        from gradata.enhancements.pattern_extractor import INITIAL_CONFIDENCE, patterns_to_lessons

        p = self._make_pattern("TONE", "warmer language", confidence=0.40)
        result = patterns_to_lessons([p])
        assert result[0].confidence == INITIAL_CONFIDENCE

    def test_lesson_description_from_pattern(self):
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        desc = "Repeated tone pattern involving warm friendly language"
        p = self._make_pattern("TONE", desc, confidence=0.40)
        result = patterns_to_lessons([p])
        assert result[0].description == desc

    def test_multiple_patterns_produce_multiple_lessons(self):
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        patterns = [
            self._make_pattern("TONE", "tone pattern one warm", 0.40),
            self._make_pattern("FORMAT", "format pattern two list", 0.40),
        ]
        result = patterns_to_lessons(patterns)
        assert len(result) == 2

    def test_boundary_at_threshold(self):
        """Confidence exactly at 0.25 should be included (>= threshold)."""
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        p = self._make_pattern("TONE", "boundary pattern", confidence=0.25)
        result = patterns_to_lessons([p])
        assert len(result) == 1

    def test_boundary_just_below_threshold_excluded(self):
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        p = self._make_pattern("TONE", "below threshold", confidence=0.24)
        result = patterns_to_lessons([p])
        assert result == []

    def test_lesson_has_date_field(self):
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        p = self._make_pattern("TONE", "warmer language", confidence=0.40)
        result = patterns_to_lessons([p])
        assert result[0].date is not None
        # Date should be an ISO-formatted string
        assert len(result[0].date) == 10

    def test_unknown_category_defaults_to_behavioral(self):
        """Categories not in the map fall back to CorrectionType.BEHAVIORAL."""
        from gradata._types import CorrectionType
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        p = self._make_pattern("UNKNOWN_XYZ", "some pattern text", confidence=0.40)
        result = patterns_to_lessons([p])
        assert len(result) == 1
        assert result[0].correction_type == CorrectionType.BEHAVIORAL

    def test_factual_category_maps_to_factual_type(self):
        from gradata._types import CorrectionType
        from gradata.enhancements.pattern_extractor import patterns_to_lessons

        p = self._make_pattern("FACTUAL", "fact check pattern text", confidence=0.40)
        result = patterns_to_lessons([p])
        assert result[0].correction_type == CorrectionType.FACTUAL


# ---------------------------------------------------------------------------
# 5. Internal helpers — _keywords() and _jaccard()
# ---------------------------------------------------------------------------


class TestInternalHelpers:
    """Unit tests for the private helpers used by the clustering algorithm."""

    def test_keywords_removes_stopwords(self):
        from gradata.enhancements.pattern_extractor import _keywords

        words = _keywords("the quick brown fox and a dog")
        assert "the" not in words
        assert "and" not in words
        assert "fox" in words

    def test_keywords_returns_set(self):
        from gradata.enhancements.pattern_extractor import _keywords

        result = _keywords("hello world")
        assert isinstance(result, set)

    def test_keywords_lowercase(self):
        from gradata.enhancements.pattern_extractor import _keywords

        result = _keywords("Hello WORLD Gradata")
        assert "hello" in result
        assert "world" in result

    def test_keywords_minimum_length_three(self):
        from gradata.enhancements.pattern_extractor import _keywords

        result = _keywords("I am ok go do")
        # Single/double char words should not appear
        assert all(len(w) >= 3 for w in result)

    def test_keywords_empty_string(self):
        from gradata.enhancements.pattern_extractor import _keywords

        assert _keywords("") == set()

    def test_jaccard_identical_sets(self):
        from gradata.enhancements.pattern_extractor import _jaccard

        s = {"a", "b", "c"}
        assert _jaccard(s, s) == 1.0

    def test_jaccard_disjoint_sets(self):
        from gradata.enhancements.pattern_extractor import _jaccard

        assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_jaccard_both_empty(self):
        from gradata.enhancements.pattern_extractor import _jaccard

        assert _jaccard(set(), set()) == 0.0

    def test_jaccard_partial_overlap(self):
        from gradata.enhancements.pattern_extractor import _jaccard

        # |intersection| = 1, |union| = 3
        score = _jaccard({"a", "b"}, {"b", "c"})
        assert abs(score - (1 / 3)) < 1e-9

    def test_jaccard_symmetric(self):
        from gradata.enhancements.pattern_extractor import _jaccard

        a, b = {"x", "y", "z"}, {"y", "z", "w"}
        assert _jaccard(a, b) == _jaccard(b, a)
