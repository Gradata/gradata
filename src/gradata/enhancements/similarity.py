"""
Semantic Similarity — intent-aware lesson deduplication.
=========================================================
SDK LAYER: Layer 1 (enhancements). Pure Python with optional embedding support.

Two modes:
  1. **TF-IDF cosine** (default, zero deps): tokenize, weight by inverse frequency,
     cosine similarity. Good enough for "make it warmer" ≈ "add empathy" if the
     correction descriptions share semantic structure.
  2. **Embedding-based** (optional): uses Ollama's nomic-embed-text if available.
     768-dim vectors, much higher accuracy for paraphrase detection.

Public API::

    from .similarity import semantic_similarity
    score = semantic_similarity("make it warmer", "add empathy")  # 0.0-1.0
"""

from __future__ import annotations

import math
import re
from collections import Counter

# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "can", "could", "might", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "that",
    "this", "it", "its", "and", "or", "but", "not", "no", "if", "so",
    "than", "too", "very", "just", "also", "then", "now", "here",
    "i", "you", "we", "they", "he", "she", "me", "my", "your", "our",
    "their", "his", "her", "us", "them", "up", "out", "all", "am",
    "make", "more", "less", "get", "put", "use", "new", "old", "way",
    "change", "changed", "content", "added", "cut", "edit", "edits",
})


def _tokenize(text: str) -> list[str]:
    """Extract meaningful lowercase tokens from text."""
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return [w for w in words if w not in _STOP_WORDS]


# ---------------------------------------------------------------------------
# TF-IDF Cosine Similarity (zero deps)
# ---------------------------------------------------------------------------

def _tf(tokens: list[str]) -> dict[str, float]:
    """Term frequency: count / total."""
    counts = Counter(tokens)
    total = len(tokens) or 1
    return {t: c / total for t, c in counts.items()}


def _cosine(v1: dict[str, float], v2: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    common = set(v1) & set(v2)
    if not common:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in common)
    mag1 = math.sqrt(sum(v ** 2 for v in v1.values()))
    mag2 = math.sqrt(sum(v ** 2 for v in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


# ---------------------------------------------------------------------------
# Synonym expansion (boosts recall for paraphrases)
# ---------------------------------------------------------------------------

_SYNONYM_GROUPS: list[frozenset[str]] = [
    frozenset({"warm", "warmer", "empathy", "empathetic", "friendly", "human", "personal"}),
    frozenset({"direct", "blunt", "concise", "short", "brief", "terse", "tight"}),
    frozenset({"formal", "formalized", "professional", "polished", "proper"}),
    frozenset({"casual", "casualized", "informal", "relaxed", "conversational"}),
    frozenset({"hedge", "hedging", "might", "maybe", "perhaps", "probably", "possibly", "potentially"}),
    frozenset({"fluff", "filler", "wordy", "verbose", "bloated", "long", "lengthy"}),
    frozenset({"specific", "concrete", "precise", "exact", "detailed", "measurable"}),
    frozenset({"vague", "generic", "abstract", "unclear", "ambiguous"}),
    frozenset({"strengthen", "strengthened", "stronger", "bolder", "assertive", "confident"}),
    frozenset({"soften", "softened", "gentler", "lighter", "diplomatic", "tactful"}),
    frozenset({"structure", "restructure", "reorder", "reorganize", "format", "formatting"}),
    frozenset({"cta", "action", "ask", "close", "book", "schedule", "meeting", "call"}),
    frozenset({"research", "investigate", "lookup", "check", "verify", "confirm"}),
    frozenset({"metric", "metrics", "number", "numbers", "data", "stats", "roi", "kpi"}),
]

# Correction intent pairs: opposite-sounding PHRASINGS of the SAME intent.
# "less hedging" = "more direct" (same intent: be direct)
# "remove fluff" = "be concise" (same intent: shorten)
# NOTE: formal/casual and vague/specific are ANTONYMS (opposite intents),
# NOT same-intent pairs. They must NOT be mapped together or contradictory
# corrections will silently reinforce each other.
_INTENT_PAIRS: list[tuple[frozenset[str], frozenset[str]]] = [
    (frozenset({"hedging", "hedge", "perhaps", "maybe", "might"}),
     frozenset({"direct", "blunt", "assertive"})),
    (frozenset({"fluff", "filler", "wordy", "verbose", "long"}),
     frozenset({"short", "brief", "tight", "concise", "terse"})),
]

_SYNONYM_MAP: dict[str, str] = {}
for group in _SYNONYM_GROUPS:
    canonical = sorted(group)[0]
    for word in group:
        _SYNONYM_MAP[word] = canonical

# Map intent pairs: both sides of a correction intent → same canonical.
# Intent pairs OVERRIDE synonym groups because "less hedging" = "be direct"
# is the key insight for correction dedup.
for neg_set, pos_set in _INTENT_PAIRS:
    combined = neg_set | pos_set
    canonical = sorted(combined)[0]
    for word in combined:
        _SYNONYM_MAP[word] = canonical  # Override, not conditional


def _expand_synonyms(tokens: list[str]) -> list[str]:
    """Replace tokens with canonical synonyms for better matching."""
    return [_SYNONYM_MAP.get(t, t) for t in tokens]


def semantic_similarity(text1: str, text2: str) -> float:
    """Compute semantic similarity between two correction descriptions.

    Uses synonym-expanded TF cosine similarity. Handles paraphrases like:
    - "make it warmer" ≈ "add empathy" (synonym group: warm/empathy)
    - "cut the fluff" ≈ "too wordy" (synonym group: fluff/wordy)
    - "be more direct" ≈ "less hedging" (synonym group: direct + hedge)

    Returns:
        Similarity score in [0.0, 1.0]. Above 0.4 = likely same intent.
    """
    t1 = _expand_synonyms(_tokenize(text1))
    t2 = _expand_synonyms(_tokenize(text2))
    if not t1 or not t2:
        return 0.0
    return _cosine(_tf(t1), _tf(t2))


# ---------------------------------------------------------------------------
# Optional: Embedding-based similarity (requires Ollama)
# ---------------------------------------------------------------------------

_OLLAMA_BASE: str | None = None
_EMBED_MODEL: str = "nomic-embed-text"


def _get_embedding(text: str) -> list[float] | None:
    """Get embedding vector from Ollama (returns None if unavailable)."""
    if not _OLLAMA_BASE:
        return None
    try:
        import requests
        resp = requests.post(
            f"{_OLLAMA_BASE}/api/embed",
            json={"model": _EMBED_MODEL, "input": text},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            embeddings = data.get("embeddings", [])
            if embeddings:
                return embeddings[0]
        return None
    except Exception:
        return None


def embedding_similarity(text1: str, text2: str) -> float | None:
    """Compute embedding-based cosine similarity.

    Returns:
        Similarity score in [0.0, 1.0], or None if embeddings unavailable.
    """
    e1 = _get_embedding(text1)
    e2 = _get_embedding(text2)
    if e1 is None or e2 is None:
        return None
    dot = sum(a * b for a, b in zip(e1, e2, strict=False))
    mag1 = math.sqrt(sum(a * a for a in e1))
    mag2 = math.sqrt(sum(b * b for b in e2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def best_similarity(text1: str, text2: str) -> float:
    """Use embeddings if available, fall back to synonym-expanded TF cosine.

    Returns:
        Similarity score in [0.0, 1.0].
    """
    emb = embedding_similarity(text1, text2)
    if emb is not None:
        return emb
    return semantic_similarity(text1, text2)
