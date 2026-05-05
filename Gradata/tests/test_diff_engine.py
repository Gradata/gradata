"""Tests for diff engine semantic severity adjustment."""

from __future__ import annotations

import pytest

from gradata.enhancements.diff_engine import (
    DEFAULT_SEMANTIC_WEIGHT,
    DEFAULT_SURFACE_WEIGHT,
    DiffResult,
    adjust_severity_by_semantics,
    combine_distances,
    compute_diff,
    compute_semantic_distance,
)


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


# ---------------------------------------------------------------------------
# Semantic edit distance (fix #11)
# ---------------------------------------------------------------------------


def _fake_embedder(vectors: dict[str, list[float]]):
    """Returns a deterministic embedder that looks up precomputed vectors.

    Keeps tests fast and independent of sentence-transformers.
    """

    def _embed(texts):
        return [vectors.get(t, [0.0, 0.0, 0.0]) for t in texts]

    return _embed


class TestComputeSemanticDistance:
    def test_identical_texts_zero_distance(self):
        embedder = _fake_embedder({"hello": [1.0, 0.0, 0.0]})
        d = compute_semantic_distance("hello", "hello", embedder=embedder)
        assert d == 0.0

    def test_orthogonal_vectors_unit_distance(self):
        embedder = _fake_embedder(
            {
                "a": [1.0, 0.0, 0.0],
                "b": [0.0, 1.0, 0.0],
            }
        )
        d = compute_semantic_distance("a", "b", embedder=embedder)
        assert d is not None
        assert abs(d - 1.0) < 1e-6

    def test_opposite_vectors_clamped_to_one(self):
        embedder = _fake_embedder(
            {
                "x": [1.0, 0.0, 0.0],
                "y": [-1.0, 0.0, 0.0],
            }
        )
        d = compute_semantic_distance("x", "y", embedder=embedder)
        assert d == 1.0  # cos_dist=2.0 clamped to 1.0

    def test_polarity_flip_vs_morphology(self):
        """The motivating case: 'helpful' -> 'unhelpful' should yield higher
        semantic distance than 'helpful' -> 'helpfully'."""
        embedder = _fake_embedder(
            {
                "helpful": [1.0, 0.0, 0.0],
                "helpfully": [0.98, 0.2, 0.0],  # near-identical meaning
                "unhelpful": [-0.95, 0.1, 0.0],  # flipped
            }
        )
        morph = compute_semantic_distance("helpful", "helpfully", embedder=embedder)
        flip = compute_semantic_distance("helpful", "unhelpful", embedder=embedder)
        assert morph is not None and flip is not None
        assert flip > morph + 0.5  # polarity clearly worse than morphology

    def test_no_embedder_returns_none_when_unavailable(self, monkeypatch):
        """If sentence-transformers isn't importable, returns None."""
        import gradata.enhancements.diff_engine as de

        # Force the lazy loader to believe the dep is missing.
        monkeypatch.setattr(de, "_default_embedder_cache", None, raising=False)
        monkeypatch.setattr(de, "_default_embedder_unavailable", True, raising=False)
        d = compute_semantic_distance("a", "b", embedder=None)
        assert d is None

    def test_zero_vectors_return_zero(self):
        embedder = _fake_embedder({"a": [0.0, 0.0, 0.0], "b": [0.0, 0.0, 0.0]})
        d = compute_semantic_distance("a", "b", embedder=embedder)
        assert d == 0.0


class TestCombineDistances:
    def test_default_weights_sum_to_one(self):
        assert abs(DEFAULT_SURFACE_WEIGHT + DEFAULT_SEMANTIC_WEIGHT - 1.0) < 1e-6

    def test_blend_identical_is_zero(self):
        assert combine_distances(0.0, 0.0) == 0.0

    def test_blend_both_max_is_one(self):
        assert combine_distances(1.0, 1.0) == 1.0

    def test_semantic_dominates_default(self):
        """Default 0.7 weight on semantic → semantic=1, surface=0 → 0.7 blend."""
        blended = combine_distances(0.0, 1.0)
        assert abs(blended - 0.7) < 1e-6

    def test_weights_configurable(self):
        blended = combine_distances(
            1.0,
            0.0,
            surface_weight=0.5,
            semantic_weight=0.5,
        )
        assert abs(blended - 0.5) < 1e-6

    def test_weights_must_sum_to_one(self):
        with pytest.raises(ValueError):
            combine_distances(0.5, 0.5, surface_weight=0.3, semantic_weight=0.3)


class TestComputeDiffWithSemantic:
    def test_use_semantic_false_backwards_compatible(self):
        r = compute_diff("hello", "hello world")
        assert r.semantic_distance is None
        assert r.blended_distance is None
        assert r.severity in ("as-is", "minor", "moderate", "major", "discarded")

    def test_use_semantic_with_injected_embedder(self):
        embedder = _fake_embedder(
            {
                "hello": [1.0, 0.0, 0.0],
                "hello world": [0.9, 0.2, 0.0],
            }
        )
        r = compute_diff("hello", "hello world", embedder=embedder)
        assert r.semantic_distance is not None
        assert r.blended_distance is not None
        assert 0.0 <= r.blended_distance <= 1.0

    def test_semantic_flip_raises_severity(self):
        """Same surface edit distance, opposite semantic — severity should
        rise under the blended classifier."""
        # Morphology pair: small semantic delta.
        morph_embedder = _fake_embedder(
            {
                "this is helpful": [1.0, 0.0, 0.0],
                "this is helpfully": [0.99, 0.01, 0.0],
            }
        )
        flip_embedder = _fake_embedder(
            {
                "this is helpful": [1.0, 0.0, 0.0],
                "this is unhelpful": [-1.0, 0.0, 0.0],
            }
        )
        morph = compute_diff(
            "this is helpful",
            "this is helpfully",
            embedder=morph_embedder,
        )
        flip = compute_diff(
            "this is helpful",
            "this is unhelpful",
            embedder=flip_embedder,
        )
        # Same-ish surface distance; semantic flip must push blended higher.
        assert flip.blended_distance is not None
        assert morph.blended_distance is not None
        assert flip.blended_distance > morph.blended_distance

    def test_use_semantic_true_without_dep_gracefully_falls_back(self, monkeypatch):
        """use_semantic=True but embedder unavailable → surface-only severity."""
        import gradata.enhancements.diff_engine as de

        monkeypatch.setattr(de, "_default_embedder_cache", None, raising=False)
        monkeypatch.setattr(de, "_default_embedder_unavailable", True, raising=False)
        r = compute_diff("hello", "hello world", use_semantic=True)
        assert r.semantic_distance is None
        assert r.blended_distance is None
        # Must still produce a valid severity via surface fallback.
        assert r.severity in ("as-is", "minor", "moderate", "major", "discarded")

    def test_custom_weights_propagate(self):
        embedder = _fake_embedder(
            {
                "a": [1.0, 0.0, 0.0],
                "b": [-1.0, 0.0, 0.0],
            }
        )
        # Full weight on surface → blended equals surface for-severity value.
        r = compute_diff(
            "a",
            "b",
            embedder=embedder,
            surface_weight=1.0,
            semantic_weight=0.0,
        )
        # Surface was computed from edit_distance (short text).
        assert r.blended_distance is not None
        assert abs(r.blended_distance - r.edit_distance) < 1e-6
