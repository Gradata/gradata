import pytest
from unittest.mock import patch, MagicMock
from gradata.integrations.embeddings import (
    EmbeddingClient,
    cosine_similarity,
    cluster_lessons_by_similarity,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_zero_vector(self):
        assert cosine_similarity([0, 0], [1, 1]) == 0.0


class TestEmbeddingClient:
    def test_local_fallback_when_api_unavailable(self):
        client = EmbeddingClient(api_url=None)
        result = client.embed("test text")
        assert result is None or isinstance(result, list)

    def test_embed_returns_list_of_floats(self):
        client = EmbeddingClient(api_url=None)
        with patch.object(client, '_embed_local', return_value=[0.1, 0.2, 0.3]):
            result = client.embed("test")
            assert result == [0.1, 0.2, 0.3]

    def test_api_preferred_over_local(self):
        client = EmbeddingClient(api_url="https://example.com/embed", api_token="tok")
        with patch.object(client, '_embed_api', return_value=[0.5, 0.6]) as mock_api:
            with patch.object(client, '_embed_local') as mock_local:
                client.embed("test")
                mock_api.assert_called_once()
                mock_local.assert_not_called()

    def test_api_failure_falls_back_to_local(self):
        client = EmbeddingClient(api_url="https://example.com/embed", api_token="tok")
        with patch.object(client, '_embed_api', side_effect=Exception("down")):
            with patch.object(client, '_embed_local', return_value=[0.1]) as mock_local:
                client.embed("test")
                mock_local.assert_called_once()


class TestClustering:
    def test_empty_lessons(self):
        assert cluster_lessons_by_similarity([]) == []

    def test_lessons_cluster_by_similarity(self):
        lessons = [
            {"description": "validate email before upload"},
            {"description": "check email format before send"},
            {"description": "run unit tests after changes"},
        ]
        clusters = cluster_lessons_by_similarity(lessons, threshold=0.5)
        assert len(clusters) >= 1
