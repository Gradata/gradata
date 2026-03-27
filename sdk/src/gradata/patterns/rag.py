"""
RAG — Retrieval-Augmented Generation with cascade and graduation scoring.
=========================================================================
Layer 0 pattern: domain-agnostic.

Implements a retrieval cascade:
  FTS5 (keyword) -> Vector (semantic) -> Hybrid (RRF merge) -> LLM fallback

Also implements graduation-aware scoring:
  RULE results get 1.2x boost, INSTINCT gets 0.8x penalty.

This module provides the retrieval strategy layer. Actual FTS5/vector
backends are in _query.py and _embed.py (the existing modules).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """A retrieved chunk of brain content."""

    content: str
    source: str           # file/doc name
    chunk_id: str = ""
    relevance_score: float = 0.0
    recency_weight: float = 1.0
    memory_type: str = ""  # episodic, semantic, procedural
    graduation_level: str = ""  # INSTINCT, PATTERN, RULE


@dataclass
class RetrievalResult:
    """Result of a retrieval operation."""

    chunks: list[Chunk]
    query: str
    mode: str              # "fts", "vector", "hybrid", "cascade"
    total_candidates: int = 0
    citations: dict[str, str] = field(default_factory=dict)  # claim -> source


@dataclass
class CascadeConfig:
    """Configuration for the retrieval cascade."""

    fts_threshold: float = 0.3      # min FTS score to stop cascade
    vector_threshold: float = 0.5   # min vector score to stop cascade
    hybrid_rrf_k: int = 60          # RRF constant
    max_results: int = 10
    two_pass: bool = False          # Enable two-pass query expansion
    two_pass_top_k: int = 3         # How many results to mine for expansion terms
    graduation_boost: dict[str, float] = field(default_factory=lambda: {
        "RULE": 1.2,
        "PATTERN": 1.0,
        "INSTINCT": 0.8,
        "UNTESTABLE": 0.5,
    })


# ---------------------------------------------------------------------------
# Graduation-aware scoring
# ---------------------------------------------------------------------------

def apply_graduation_scoring(
    chunks: list[Chunk],
    config: CascadeConfig | None = None,
) -> list[Chunk]:
    """Apply graduation-aware score multipliers to chunks.

    RULE-sourced content gets boosted; INSTINCT-sourced gets penalized.
    This ensures proven behavioral rules rank higher in retrieval.
    """
    cfg = config or CascadeConfig()
    scored = []
    for chunk in chunks:
        boost = cfg.graduation_boost.get(chunk.graduation_level, 1.0)
        scored_chunk = Chunk(
            content=chunk.content,
            source=chunk.source,
            chunk_id=chunk.chunk_id,
            relevance_score=round(chunk.relevance_score * boost, 4),
            recency_weight=chunk.recency_weight,
            memory_type=chunk.memory_type,
            graduation_level=chunk.graduation_level,
        )
        scored.append(scored_chunk)
    return sorted(scored, key=lambda c: -c.relevance_score)


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion (RRF)
# ---------------------------------------------------------------------------

def rrf_merge(
    *result_lists: list[Chunk],
    k: int = 60,
) -> list[Chunk]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion.

    RRF score = sum(1 / (k + rank_i)) across all lists.
    Produces a single ranked list that balances keyword and semantic signals.
    """
    scores: dict[str, float] = {}
    chunks_by_id: dict[str, Chunk] = {}

    for result_list in result_lists:
        for rank, chunk in enumerate(result_list):
            cid = chunk.chunk_id or f"{chunk.source}:{hash(chunk.content) % 10000}"
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            if cid not in chunks_by_id:
                chunks_by_id[cid] = chunk

    # Build merged list sorted by RRF score
    merged: list[Chunk] = []
    for cid, score in sorted(scores.items(), key=lambda x: -x[1]):
        chunk = chunks_by_id[cid]
        merged.append(Chunk(
            content=chunk.content,
            source=chunk.source,
            chunk_id=cid,
            relevance_score=round(score, 6),
            recency_weight=chunk.recency_weight,
            memory_type=chunk.memory_type,
            graduation_level=chunk.graduation_level,
        ))
    return merged


# ---------------------------------------------------------------------------
# Two-pass query expansion
# ---------------------------------------------------------------------------

# Common stopwords to filter out during term extraction (pure stdlib)
_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "shall should may might can could of in to for on with at by from as into "
    "through during before after above below between out off over under again "
    "further then once here there when where why how all each every both few "
    "more most other some such no nor not only own same so than too very it its "
    "and but or if while that this these those i me my we our you your he him "
    "his she her they them their what which who whom".split()
)


def extract_expansion_terms(
    chunks: list[Chunk],
    original_query: str,
    top_k: int = 3,
    max_terms: int = 8,
) -> list[str]:
    """Extract key terms from top retrieval results for query expansion.

    Mines the top-k retrieved chunks for terms that don't appear in the
    original query. These terms capture domain vocabulary the user may
    not have used but that the relevant documents contain.

    Args:
        chunks: Retrieved chunks sorted by relevance (best first).
        original_query: The user's original search query.
        top_k: Number of top chunks to mine for terms.
        max_terms: Maximum expansion terms to return.

    Returns:
        List of expansion terms, ordered by frequency across chunks.
    """
    if not chunks:
        return []

    query_words = set(original_query.lower().split())

    # Count term frequency across top chunks
    term_freq: dict[str, int] = {}
    for chunk in chunks[:top_k]:
        words = set(chunk.content.lower().split())
        for word in words:
            # Filter: not in query, not a stopword, 3+ chars, alphanumeric
            cleaned = word.strip(".,;:!?\"'()[]{}")
            if (
                cleaned
                and len(cleaned) >= 3
                and cleaned not in query_words
                and cleaned not in _STOPWORDS
                and cleaned.isalpha()
            ):
                term_freq[cleaned] = term_freq.get(cleaned, 0) + 1

    # Sort by frequency (most common across chunks = most relevant)
    ranked = sorted(term_freq.items(), key=lambda kv: -kv[1])
    return [term for term, _ in ranked[:max_terms]]


# ---------------------------------------------------------------------------
# Retrieval cascade
# ---------------------------------------------------------------------------

def cascade_retrieve(
    query: str,
    fts_fn: Callable | None = None,
    vector_fn: Callable | None = None,
    config: CascadeConfig | None = None,
) -> RetrievalResult:
    """Execute retrieval cascade: FTS -> Vector -> Hybrid.

    The cascade stops at the first stage that returns results above
    the configured threshold. This minimizes latency and compute.

    Args:
        query: Search query string.
        fts_fn: FTS5 search function. Takes (query, limit) -> list[Chunk].
        vector_fn: Vector search function. Takes (query, limit) -> list[Chunk].
        config: Cascade configuration.

    Returns:
        RetrievalResult with chunks, mode used, and total candidates.
    """
    cfg = config or CascadeConfig()
    limit = cfg.max_results
    _cascade_errors: list[str] = []

    # Stage 1: FTS5 keyword search
    if fts_fn is not None:
        try:
            fts_results = fts_fn(query, limit)
            if fts_results and fts_results[0].relevance_score >= cfg.fts_threshold:
                graduated = apply_graduation_scoring(fts_results, cfg)
                return RetrievalResult(
                    chunks=graduated[:limit],
                    query=query,
                    mode="fts",
                    total_candidates=len(fts_results),
                )
        except Exception as e:
            _cascade_errors.append(f"fts: {e}")

    # Stage 2: Vector semantic search
    if vector_fn is not None:
        try:
            vec_results = vector_fn(query, limit)
            if vec_results and vec_results[0].relevance_score >= cfg.vector_threshold:
                graduated = apply_graduation_scoring(vec_results, cfg)
                return RetrievalResult(
                    chunks=graduated[:limit],
                    query=query,
                    mode="vector",
                    total_candidates=len(vec_results),
                )
        except Exception as e:
            _cascade_errors.append(f"vector: {e}")

    # Stage 3: Hybrid (RRF merge of whatever we got)
    all_results: list[list[Chunk]] = []
    total = 0
    if fts_fn is not None:
        try:
            fts_results = fts_fn(query, limit * 2)
            all_results.append(fts_results)
            total += len(fts_results)
        except Exception as e:
            _cascade_errors.append(f"hybrid-fts: {e}")
    if vector_fn is not None:
        try:
            vec_results = vector_fn(query, limit * 2)
            all_results.append(vec_results)
            total += len(vec_results)
        except Exception as e:
            _cascade_errors.append(f"hybrid-vec: {e}")

    if all_results:
        merged = rrf_merge(*all_results, k=cfg.hybrid_rrf_k)
        graduated = apply_graduation_scoring(merged, cfg)
        result = RetrievalResult(
            chunks=graduated[:limit],
            query=query,
            mode="hybrid",
            total_candidates=total,
        )
        if _cascade_errors:
            result.mode = f"hybrid (warnings: {', '.join(_cascade_errors)})"
        return result

    # Stage 4: Two-pass query expansion (if enabled and we got SOME results)
    if cfg.two_pass and all_results:
        flat_chunks = [c for sublist in all_results for c in sublist]
        expansion_terms = extract_expansion_terms(flat_chunks, query, top_k=cfg.two_pass_top_k)
        if expansion_terms:
            expanded_query = query + " " + " ".join(expansion_terms)
            # Second pass with expanded query
            pass2_results: list[list[Chunk]] = []
            pass2_total = 0
            if fts_fn is not None:
                try:
                    fts2 = fts_fn(expanded_query, limit * 2)
                    pass2_results.append(fts2)
                    pass2_total += len(fts2)
                except Exception:
                    pass
            if vector_fn is not None:
                try:
                    vec2 = vector_fn(expanded_query, limit * 2)
                    pass2_results.append(vec2)
                    pass2_total += len(vec2)
                except Exception:
                    pass

            if pass2_results:
                # Merge pass 1 + pass 2, deduplicate by chunk_id
                all_combined = all_results + pass2_results
                merged = rrf_merge(*all_combined, k=cfg.hybrid_rrf_k)
                graduated = apply_graduation_scoring(merged, cfg)
                return RetrievalResult(
                    chunks=graduated[:limit],
                    query=expanded_query,
                    mode=f"two_pass (expanded: +{len(expansion_terms)} terms)",
                    total_candidates=total + pass2_total,
                )

    # Stage 5: Nothing found — include error context if cascade failed
    mode = "empty"
    if _cascade_errors:
        mode = f"cascade_failed ({', '.join(_cascade_errors)})"
    return RetrievalResult(
        chunks=[], query=query, mode=mode, total_candidates=0,
    )


# ---------------------------------------------------------------------------
# Context ordering (Lost in the Middle paper)
# ---------------------------------------------------------------------------

def order_by_relevance_position(chunks: list[Chunk]) -> list[Chunk]:
    """Reorder chunks per "Lost in the Middle" paper findings.

    The most relevant chunks go at the beginning and end of the context,
    while less relevant ones go in the middle. This maximizes LLM attention
    to the most important information.
    """
    if len(chunks) <= 2:
        return chunks

    sorted_chunks = sorted(chunks, key=lambda c: -c.relevance_score)
    result: list[Chunk] = []
    left = True
    for chunk in sorted_chunks:
        if left:
            result.insert(0, chunk)
        else:
            result.append(chunk)
        left = not left
    return result


def format_context(result: RetrievalResult, max_chars: int = 5000) -> str:
    """Format retrieval result as context block for prompt injection."""
    if not result.chunks:
        return ""

    lines = [f"## Brain Context ({result.mode}, {len(result.chunks)} results)"]
    total = 0
    for chunk in result.chunks:
        text = chunk.content[:500]
        if total + len(text) > max_chars:
            break
        grad = f" [{chunk.graduation_level}]" if chunk.graduation_level else ""
        lines.append(f"- [{chunk.source}{grad}] {text}")
        total += len(text)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Progressive disclosure (from claude-mem: compact -> timeline -> full)
# ---------------------------------------------------------------------------

def progressive_disclose(
    chunks: list[Chunk],
    budget: int = 2000,
    tier: str = "auto",
) -> tuple[str, str]:
    """Return context in progressive tiers based on budget.

    From claude-mem pattern: don't dump everything. Start compact,
    expand only if the task needs it.

    Tiers:
      compact  — one-line summaries, source only (~200 chars each)
      timeline — source + first sentence (~500 chars each)
      full     — complete chunk content

    Args:
        chunks: Retrieved chunks sorted by relevance.
        budget: Character budget for the context block.
        tier: "compact", "timeline", "full", or "auto" (picks based on budget).

    Returns:
        (formatted_context, tier_used)
    """
    if not chunks:
        return "", "empty"

    if tier == "auto":
        if budget < 1000:
            tier = "compact"
        elif budget < 3000:
            tier = "timeline"
        else:
            tier = "full"

    lines: list[str] = []
    total = 0

    for chunk in chunks:
        if tier == "compact":
            text = f"[{chunk.source}] {chunk.content[:80].split(chr(10))[0]}..."
        elif tier == "timeline":
            first_sentence = chunk.content.split(".")[0] + "." if "." in chunk.content else chunk.content[:200]
            text = f"[{chunk.source}] {first_sentence}"
        else:
            text = f"[{chunk.source}] {chunk.content[:500]}"

        if total + len(text) > budget:
            break
        lines.append(text)
        total += len(text)

    return "\n".join(lines), tier


# ---------------------------------------------------------------------------
# Private content filtering (from claude-mem: <private> tag convention)
# ---------------------------------------------------------------------------

import re as _re

_PRIVATE_RE = _re.compile(r"<private>.*?</private>", _re.DOTALL | _re.IGNORECASE)


def strip_private(text: str) -> str:
    """Remove <private>...</private> blocks from text.

    From claude-mem pattern: users can mark content that should never
    be stored, retrieved, or included in brain operations.

    Example:
        >>> strip_private("Hello <private>secret API key</private> world")
        'Hello  world'
    """
    return _PRIVATE_RE.sub("", text)


def filter_private_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Remove chunks that contain only private content."""
    filtered: list[Chunk] = []
    for chunk in chunks:
        cleaned = strip_private(chunk.content).strip()
        if cleaned:
            filtered.append(Chunk(
                content=cleaned,
                source=chunk.source,
                chunk_id=chunk.chunk_id,
                relevance_score=chunk.relevance_score,
                recency_weight=chunk.recency_weight,
                memory_type=chunk.memory_type,
                graduation_level=chunk.graduation_level,
            ))
    return filtered


# ---------------------------------------------------------------------------
# Convenience classes (wrap cascade_retrieve for OOP usage)
# ---------------------------------------------------------------------------

class SmartRAG:
    """Smart retrieval with graduation-aware scoring and cascade strategy.

    Wraps ``cascade_retrieve`` in a class for users who prefer OOP patterns.

    Usage::

        rag = SmartRAG(fts_fn=my_fts, vector_fn=my_vec)
        result = rag.retrieve("budget objections")
    """

    def __init__(
        self,
        fts_fn: Callable | None = None,
        vector_fn: Callable | None = None,
        config: CascadeConfig | None = None,
    ) -> None:
        self.fts_fn = fts_fn
        self.vector_fn = vector_fn
        self.config = config or CascadeConfig()

    def retrieve(self, query: str) -> RetrievalResult:
        """Run the cascade retrieval pipeline."""
        return cascade_retrieve(query, fts_fn=self.fts_fn, vector_fn=self.vector_fn, config=self.config)


class NaiveRAG:
    """Simple keyword-only RAG without graduation scoring.

    Falls back to FTS-only search. Useful for quick prototypes.
    """

    def __init__(self, fts_fn: Callable | None = None) -> None:
        self.fts_fn = fts_fn

    def retrieve(self, query: str, top_k: int = 5) -> RetrievalResult:
        """Simple FTS-only retrieval."""
        if self.fts_fn is None:
            return RetrievalResult(chunks=[], query=query, mode="naive", total_candidates=0)
        try:
            results = self.fts_fn(query, top_k)
            return RetrievalResult(chunks=results, query=query, mode="naive", total_candidates=len(results))
        except Exception:
            return RetrievalResult(chunks=[], query=query, mode="naive", total_candidates=0)
