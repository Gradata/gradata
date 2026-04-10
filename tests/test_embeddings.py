"""Tests for EmbeddingClient.semantic_similarity()."""

import pytest

from gradata.integrations.embeddings import EmbeddingClient


class TestSemanticSimilarity:
    def test_identical_texts_similarity_is_one(self):
        client = EmbeddingClient()
        sim = client.semantic_similarity("hello world", "hello world")
        assert sim == pytest.approx(1.0, abs=0.01)

    def test_different_texts_similarity_below_one(self):
        client = EmbeddingClient()
        sim = client.semantic_similarity(
            "Please send the invoice by Friday",
            "The weather is sunny today",
        )
        assert sim < 0.8

    def test_empty_text_returns_zero(self):
        client = EmbeddingClient()
        assert client.semantic_similarity("", "hello") == 0.0
        assert client.semantic_similarity("hello", "") == 0.0
        assert client.semantic_similarity("", "") == 0.0
