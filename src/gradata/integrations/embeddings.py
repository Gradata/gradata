"""Two-tier embedding integration with event bus subscription.

Provides lightweight local embeddings (trigram hashing) with optional
API-based embedding for higher quality.  Includes cosine similarity
and single-linkage clustering for lesson deduplication.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from typing import Any, Sequence
from urllib.request import Request, urlopen
import json

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 128


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingClient:
    def __init__(self, api_url=None, api_token=None, dim=EMBEDDING_DIM):
        self.api_url = api_url
        self._token = api_token
        self.dim = dim

    def embed(self, text):
        if self.api_url:
            try:
                return self._embed_api(text)
            except Exception:
                logger.warning("API embedding failed, falling back to local", exc_info=True)
        return self._embed_local(text)

    def _embed_api(self, text):
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = "Bearer " + self._token
        body = json.dumps({"text": text}).encode()
        req = Request(self.api_url, data=body, headers=headers, method="POST")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data["embedding"]

    def _embed_local(self, text):
        vec = [0.0] * self.dim
        text_lower = text.lower()
        for i in range(len(text_lower) - 2):
            trigram = text_lower[i : i + 3]
            h = int(hashlib.md5(trigram.encode()).hexdigest(), 16)
            idx = h % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


_default_client = None


def get_client():
    global _default_client
    if _default_client is None:
        _default_client = EmbeddingClient(
            api_url=os.environ.get("GRADATA_API_URL"),
            api_token=os.environ.get("GRADATA_API_TOKEN"),
        )
    return _default_client


def cluster_lessons_by_similarity(lessons, threshold=0.7, client=None):
    if not lessons:
        return []
    if client is None:
        client = get_client()
    vectors = [client.embed(l["description"]) for l in lessons]
    parent = list(range(len(lessons)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(len(lessons)):
        for j in range(i + 1, len(lessons)):
            if vectors[i] is not None and vectors[j] is not None:
                sim = cosine_similarity(vectors[i], vectors[j])
                if sim >= threshold:
                    union(i, j)

    clusters = {}
    for i, lesson in enumerate(lessons):
        root = find(i)
        clusters.setdefault(root, []).append(lesson)
    return list(clusters.values())


def subscribe_to_bus(bus):
    def _on_correction(payload):
        try:
            desc = payload.get("description") or payload.get("text", "")
            if desc:
                get_client().embed(desc)
        except Exception:
            logger.warning("Failed to embed correction", exc_info=True)

    def _on_lesson_graduated(payload):
        try:
            desc = payload.get("description", "")
            if desc:
                get_client().embed(desc)
        except Exception:
            logger.warning("Failed to embed graduated lesson", exc_info=True)

    def _on_meta_rule(payload):
        try:
            desc = payload.get("description") or payload.get("rule", "")
            if desc:
                get_client().embed(desc)
        except Exception:
            logger.warning("Failed to embed meta-rule", exc_info=True)

    bus.on("correction.created", _on_correction, async_handler=True)
    bus.on("lesson.graduated", _on_lesson_graduated, async_handler=True)
    bus.on("meta_rule.created", _on_meta_rule, async_handler=True)
    logger.info("Embeddings integration subscribed to event bus")
