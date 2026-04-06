"""Two-tier embedding integration with event bus subscription.

Provides lightweight local embeddings (trigram hashing) with optional
API-based embedding for higher quality.  Includes cosine similarity
and single-linkage clustering for lesson deduplication.
"""

from __future__ import annotations

import logging
import math
import os
from urllib.request import Request, urlopen
import json

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 128


from gradata._math import cosine_similarity  # noqa: E402 — shared utility


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

    @staticmethod
    def _is_trusted_url(url):
        """SSRF protection: only allow HTTPS to gradata.ai or localhost."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.hostname in ("localhost", "127.0.0.1"):
            return True
        if parsed.scheme == "https" and parsed.hostname and parsed.hostname.endswith("gradata.ai"):
            return True
        return False

    def _embed_api(self, text):
        if not self._is_trusted_url(self.api_url):
            logger.warning("Blocked embedding request to untrusted URL")
            return self._embed_local(text)
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = "Bearer " + self._token
        body = json.dumps({"text": text}).encode()
        req = Request(str(self.api_url), data=body, headers=headers, method="POST")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data["embedding"]

    def _embed_local(self, text):
        vec = [0.0] * self.dim
        text_lower = text.lower()
        for i in range(len(text_lower) - 2):
            trigram = text_lower[i : i + 3]
            h = hash(trigram)
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


# Embedding cache: keyed by description text → vector
_embedding_cache: dict[str, list[float]] = {}


def subscribe_to_bus(bus):
    """Register embedding handlers. Embeddings are cached for clustering."""

    def _embed_and_cache(payload, *keys):
        try:
            desc = ""
            for key in keys:
                desc = payload.get(key, "")
                if desc:
                    break
            if not desc:
                desc = payload.get("lesson", {}).get("description", "")
            if desc and desc not in _embedding_cache:
                vec = get_client().embed(desc)
                if vec:
                    _embedding_cache[desc] = vec
        except Exception:
            logger.warning("Failed to embed payload", exc_info=True)

    bus.on("correction.created", lambda p: _embed_and_cache(p, "description", "text"), async_handler=True)
    bus.on("lesson.graduated", lambda p: _embed_and_cache(p, "description"), async_handler=True)
    bus.on("meta_rule.created", lambda p: _embed_and_cache(p, "description", "rule"), async_handler=True)
