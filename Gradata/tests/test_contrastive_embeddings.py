"""Tests for contrastive embeddings — semantic delta for corrections."""

from __future__ import annotations

from unittest.mock import patch


class TestCosineDistance:
    """Pure math tests — no mocking needed."""

    def test_identical_vectors(self):
        from gradata._embed import _cosine_distance

        assert _cosine_distance([1, 0, 0], [1, 0, 0]) == 0.0

    def test_opposite_vectors(self):
        from gradata._embed import _cosine_distance

        dist = _cosine_distance([1, 0], [-1, 0])
        assert dist == 1.0

    def test_orthogonal_vectors(self):
        from gradata._embed import _cosine_distance

        dist = _cosine_distance([1, 0], [0, 1])
        assert abs(dist - 1.0) < 0.01  # cosine distance = 1 for orthogonal

    def test_similar_vectors(self):
        from gradata._embed import _cosine_distance

        dist = _cosine_distance([1, 0.1], [1, 0.2])
        assert dist < 0.1  # very similar

    def test_zero_vector_returns_zero(self):
        from gradata._embed import _cosine_distance

        assert _cosine_distance([0, 0], [1, 0]) == 0.0

    def test_both_zero_vectors(self):
        from gradata._embed import _cosine_distance

        assert _cosine_distance([0, 0], [0, 0]) == 0.0

    def test_negative_similarity_clamped(self):
        """Cosine distance should be clamped to [0, 1]."""
        from gradata._embed import _cosine_distance

        dist = _cosine_distance([1, 0], [-1, 0])
        assert 0.0 <= dist <= 1.0


class TestEmbedPair:
    """Tests for embed_pair — mocks embedding calls."""

    @patch("gradata._embed.embed_texts")
    def test_computes_semantic_delta(self, mock_embed):
        from gradata._embed import embed_pair

        mock_embed.return_value = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        result = embed_pair("draft text", "final text")

        assert result["draft_embedding"] == [1.0, 0.0, 0.0]
        assert result["final_embedding"] == [0.0, 1.0, 0.0]
        assert result["cosine_distance"] > 0
        assert result["semantic_delta"] > 0
        assert 0.0 <= result["semantic_delta"] <= 1.0

    @patch("gradata._embed.embed_texts")
    def test_identical_texts_zero_delta(self, mock_embed):
        from gradata._embed import embed_pair

        mock_embed.return_value = [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        result = embed_pair("same", "same")

        assert result["cosine_distance"] == 0.0
        assert result["semantic_delta"] == 0.0

    @patch("gradata._embed.embed_texts")
    def test_semantic_delta_capped_at_one(self, mock_embed):
        from gradata._embed import embed_pair

        # Opposite vectors => cosine_distance = 1.0, delta = min(1.0, 2.0) = 1.0
        mock_embed.return_value = [[1.0, 0.0], [-1.0, 0.0]]
        result = embed_pair("a", "b")

        assert result["semantic_delta"] <= 1.0

    @patch("gradata._embed.embed_texts", side_effect=Exception("model not loaded"))
    def test_graceful_fallback_on_exception(self, mock_embed):
        from gradata._embed import embed_pair

        result = embed_pair("hello", "world")

        assert result["draft_embedding"] is None
        assert result["final_embedding"] is None
        assert result["cosine_distance"] == 0.0
        assert result["semantic_delta"] == 0.0

    @patch("gradata._embed.embed_texts", return_value=[None, [1.0, 0.0]])
    def test_graceful_fallback_partial_none(self, mock_embed):
        from gradata._embed import embed_pair

        result = embed_pair("hello", "world")

        assert result["draft_embedding"] is None
        assert result["cosine_distance"] == 0.0
        assert result["semantic_delta"] == 0.0

    @patch("gradata._embed.embed_texts")
    def test_returns_rounded_values(self, mock_embed):
        from gradata._embed import embed_pair

        mock_embed.return_value = [[0.5, 0.5, 0.0], [0.0, 0.5, 0.5]]
        result = embed_pair("a", "b")

        # Values should be rounded to 4 decimal places
        cos_str = str(result["cosine_distance"])
        delta_str = str(result["semantic_delta"])
        assert len(cos_str.split(".")[-1]) <= 4
        assert len(delta_str.split(".")[-1]) <= 4

    @patch("gradata._embed.embed_texts")
    def test_calls_embed_texts_with_both_strings(self, mock_embed):
        from gradata._embed import embed_pair

        mock_embed.return_value = [[1.0, 0.0], [0.0, 1.0]]
        embed_pair("draft", "final")

        mock_embed.assert_called_once_with(["draft", "final"])
