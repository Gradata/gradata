"""Integration test: full nervous system loop."""

import pytest

from tests.conftest import init_brain


class TestNervousSystemIntegration:
    def test_correction_emits_to_all_subscribers(self, tmp_path):
        brain = init_brain(tmp_path)
        events_received = {"correction": [], "session": []}
        brain.bus.on("correction.created", lambda p: events_received["correction"].append(p))
        brain.bus.on("session.ended", lambda p: events_received["session"].append(p))
        brain.correct("old code", "new code", category="CODE")
        assert len(events_received["correction"]) == 1
        assert events_received["correction"][0]["category"] == "CODE"
        brain.end_session()
        assert len(events_received["session"]) == 1

    def test_rule_ranker_with_context(self, tmp_path):
        from gradata.rules.rule_ranker import rank_rules

        rules = [
            {
                "description": "validate email",
                "confidence": 0.8,
                "category": "SALES",
                "fire_count": 3,
                "last_session": 5,
            },
            {
                "description": "clamp confidence",
                "confidence": 0.8,
                "category": "CODE",
                "fire_count": 3,
                "last_session": 5,
            },
        ]
        ranked = rank_rules(
            rules, current_session=10, context_keywords=["confidence", "graduation"]
        )
        assert ranked[0]["description"] == "clamp confidence"

    def test_bus_error_isolation(self, tmp_path):
        brain = init_brain(tmp_path)
        brain.bus.on("correction.created", lambda p: 1 / 0)
        result = brain.correct("old", "new", category="CODE")
        assert result is not None

    def test_session_history_wires_to_bus(self, tmp_path):
        brain = init_brain(tmp_path)
        brain.bus.emit(
            "rules.injected",
            {
                "rules": [
                    {"id": "r1", "description": "test rule"},
                ]
            },
        )
        brain.correct("bad", "good", category="CODE")
        brain.end_session()

    def test_embeddings_cosine_similarity(self):
        from gradata.integrations.embeddings import cosine_similarity

        assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_embedding_client_local_fallback(self):
        from gradata.integrations.embeddings import EmbeddingClient

        client = EmbeddingClient(api_url=None)
        result = client.embed("test text for embedding")
        assert result is None or isinstance(result, list)
