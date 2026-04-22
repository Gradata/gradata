"""Tests for EmbeddingClient.semantic_similarity()."""

from __future__ import annotations

import json

import pytest

from gradata.services.embeddings import EMBEDDING_DIM, EmbeddingClient


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


class _FakeURLResp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestEmbedApiShapeValidation:
    """``_embed_api`` must reject malformed payloads so the outer ``embed()``
    try/except can fall back to the local embedding path cleanly."""

    def test_missing_embedding_key_raises(self, monkeypatch):
        client = EmbeddingClient(api_url="https://localhost/embed")
        monkeypatch.setattr(
            "gradata.services.embeddings.urlopen",
            lambda *a, **k: _FakeURLResp(json.dumps({"foo": "bar"}).encode()),
        )
        with pytest.raises(ValueError):
            client._embed_api("hello")

    def test_wrong_dimension_raises(self, monkeypatch):
        client = EmbeddingClient(api_url="https://localhost/embed")
        monkeypatch.setattr(
            "gradata.services.embeddings.urlopen",
            lambda *a, **k: _FakeURLResp(json.dumps({"embedding": [0.1, 0.2]}).encode()),
        )
        with pytest.raises(ValueError):
            client._embed_api("hello")

    def test_non_numeric_vector_raises(self, monkeypatch):
        client = EmbeddingClient(api_url="https://localhost/embed")
        bad = ["x"] * EMBEDDING_DIM
        monkeypatch.setattr(
            "gradata.services.embeddings.urlopen",
            lambda *a, **k: _FakeURLResp(json.dumps({"embedding": bad}).encode()),
        )
        with pytest.raises(ValueError):
            client._embed_api("hello")

    def test_falls_back_to_local_on_malformed_response(self, monkeypatch):
        client = EmbeddingClient(api_url="https://localhost/embed")
        monkeypatch.setattr(
            "gradata.services.embeddings.urlopen",
            lambda *a, **k: _FakeURLResp(json.dumps({"embedding": None}).encode()),
        )
        # ``embed()`` swallows the validation error and returns the local vector.
        vec = client.embed("hello world")
        assert isinstance(vec, list)
        assert len(vec) == EMBEDDING_DIM


def test_cluster_skips_blank_descriptions():
    from gradata.services.embeddings import cluster_lessons_by_similarity

    lessons = [
        {"description": "build a report"},
        {"description": ""},
        {"description": "   "},
        {"description": "build a report"},
    ]
    clusters = cluster_lessons_by_similarity(lessons, threshold=0.9)
    # Blank-description lessons stay as their own singleton clusters (never
    # merged into real rows); the two identical descriptions cluster.
    sizes = sorted(len(c) for c in clusters)
    assert sizes == [1, 1, 2]
