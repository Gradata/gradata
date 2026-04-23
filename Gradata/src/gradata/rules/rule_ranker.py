"""Context-aware rule ranker with effectiveness, recency, BM25, and Thompson weighting.

Ranking modes (in order of precedence):

1. **BM25 context relevance** (default when ``bm25s`` is available): scores rules
   by BM25 over the corpus ``category + description + tags`` against a query built
   from ``task_type + context_keywords``. Replaces the legacy substring-overlap
   scorer. See the 2026-04 autoresearch synthesis §5 for the motivation.
2. **Keyword fallback**: the original substring-overlap scorer is used when
   ``bm25s`` is not installed (keeps the SDK zero-required-deps).
3. **Thompson sampling** over Beta(α, β) posteriors on the candidate lessons
   (opt-in via ``GRADATA_THOMPSON_RANKING=1``). When enabled, the confidence
   term is replaced by ``p ~ Beta(α, β)`` — giving exploration weight to newly
   graduated PATTERN-tier rules that have low observed posteriors but uncertain
   upside. Deterministic within a session when ``session_seed`` is passed.

Weighted formula (sums to 1.0):

    30% scope match
    25% confidence   (or Thompson-sampled p when Thompson mode is on)
    20% context relevance  (BM25 normalized score when bm25s available)
    15% recency
    10% fire count

Plus effectiveness bonus/penalty (clamped to [0, 1]).

The ``rank_rules`` signature is stable — new behavior is additive. Callers that
pass a plain ``list[dict[str, Any]]`` continue to work; lessons with ``alpha`` /
``beta_param`` fields unlock Thompson sampling.
"""

from __future__ import annotations

import logging
import math
import os
import random
from typing import Any

try:  # BM25 is optional — SDK must stay zero-required-deps.
    import bm25s  # type: ignore[import-not-found]

    _BM25_AVAILABLE = True
except ImportError:  # pragma: no cover - import gate
    bm25s = None  # type: ignore[assignment]
    _BM25_AVAILABLE = False

_log = logging.getLogger(__name__)

# Env-gated toggles
_THOMPSON_ENV = "GRADATA_THOMPSON_RANKING"


def rank_rules(
    rules: list[dict[str, Any]],
    *,
    current_session: int,
    task_type: str | None = None,
    context_keywords: list[str] | None = None,
    effectiveness: dict[str, dict[str, Any]] | None = None,
    max_rules: int = 5,
    wiki_boost: dict[str, float] | None = None,
    session_seed: int | None = None,
) -> list[dict[str, Any]]:
    """Rank rules by composite score and return top *max_rules*.

    Parameters
    ----------
    rules:
        Iterable of rule dicts. Recognized keys: ``description``, ``category``,
        ``confidence``, ``fire_count``, ``last_session``, ``id``, ``tags``,
        ``alpha``, ``beta_param``.
    current_session:
        Current session number for recency scoring.
    task_type:
        Task scope (e.g. "CODE", "SALES"). Drives scope-match weight.
    context_keywords:
        Free-form keywords summarizing the current context. Combined with
        ``task_type`` to form the BM25 query (or legacy substring query when
        ``bm25s`` is unavailable).
    effectiveness:
        Optional map of ``rule_id -> {effective: bool, ...}`` from SessionHistory.
        Adds ±0.10 to the final score.
    max_rules:
        Top-K cap.
    wiki_boost:
        Optional map of ``rule_id -> boost`` in [0, 1] from qmd wiki search.
        Added to the context component. Keeps the wiki-aware path unified here.
    session_seed:
        When Thompson sampling is enabled (``GRADATA_THOMPSON_RANKING=1``),
        seeds the per-rank RNG so a given session picks the same top-K each
        time this function is called. ``None`` → non-deterministic.
    """
    if not rules:
        return []

    thompson_on = os.environ.get(_THOMPSON_ENV, "").strip() in ("1", "true", "True")

    # Build BM25 context-score map once per call.
    bm25_scores = _bm25_context_scores(rules, task_type, context_keywords)

    # Deterministic-per-session RNG for Thompson.
    rng = random.Random(session_seed) if session_seed is not None else random.Random()

    scored: list[tuple[float, dict[str, Any]]] = []
    for idx, rule in enumerate(rules):
        score = _score_rule(
            rule,
            idx=idx,
            current_session=current_session,
            task_type=task_type,
            context_keywords=context_keywords,
            effectiveness=effectiveness,
            bm25_scores=bm25_scores,
            wiki_boost=wiki_boost,
            thompson=thompson_on,
            rng=rng,
        )
        scored.append((score, rule))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [rule for _, rule in scored[:max_rules]]


# ------------------------------------------------------------------
# Internal scoring helpers
# ------------------------------------------------------------------


def _score_rule(
    rule: dict[str, Any],
    *,
    idx: int,
    current_session: int,
    task_type: str | None,
    context_keywords: list[str] | None,
    effectiveness: dict[str, dict[str, Any]] | None,
    bm25_scores: list[float] | None,
    wiki_boost: dict[str, float] | None,
    thompson: bool,
    rng: random.Random,
) -> float:
    scope = _scope_match(rule.get("category", ""), task_type)

    if thompson:
        alpha = float(rule.get("alpha", 1.0) or 1.0)
        beta_param = float(rule.get("beta_param", 1.0) or 1.0)
        # Guard against non-positive params (Beta is undefined).
        alpha = max(alpha, 1e-3)
        beta_param = max(beta_param, 1e-3)
        confidence = rng.betavariate(alpha, beta_param)
    else:
        confidence = float(rule.get("confidence", 0.5))

    context = _context_component(
        rule,
        idx=idx,
        keywords=context_keywords,
        bm25_scores=bm25_scores,
    )
    if wiki_boost:
        rule_id = rule.get("id") or rule.get("description", "")
        boost = wiki_boost.get(rule_id, 0.0)
        context = min(1.0, context + boost)

    recency = _recency_score(rule.get("last_session", 0), current_session)
    fire = _fire_count_score(rule.get("fire_count", 0))

    base = 0.30 * scope + 0.25 * confidence + 0.20 * context + 0.15 * recency + 0.10 * fire
    bonus = _effectiveness_bonus(rule, effectiveness)
    return max(0.0, min(1.0, base + bonus))


def _scope_match(category: str, task_type: str | None) -> float:
    if task_type is None:
        return 0.5
    cat = category.upper()
    tt = task_type.upper()
    if cat == tt:
        return 1.0
    if cat in tt or tt in cat:
        return 0.7
    return 0.5


def _bm25_context_scores(
    rules: list[dict[str, Any]],
    task_type: str | None,
    keywords: list[str] | None,
) -> list[float] | None:
    """Return normalized BM25 scores aligned to *rules*, or None if unavailable.

    The corpus for each rule is ``category + description + tags``. The query is
    ``task_type + keywords``. Returns None when bm25s isn't installed or when
    there's no query to run — callers fall back to the keyword scorer.
    """
    if not _BM25_AVAILABLE or bm25s is None:
        return None
    query_terms: list[str] = []
    if task_type:
        query_terms.append(str(task_type))
    if keywords:
        query_terms.extend(str(k) for k in keywords)
    if not query_terms:
        return None

    corpus: list[str] = []
    for rule in rules:
        tags = rule.get("tags", "")
        if isinstance(tags, (list, tuple)):
            tags = " ".join(str(t) for t in tags)
        doc = " ".join(str(rule.get(field, "")) for field in ("category", "description"))
        corpus.append(f"{doc} {tags}".strip())

    # BM25 wants at least one non-empty doc.
    if not any(corpus):
        return None

    try:
        retriever = bm25s.BM25()
        corpus_tokens = bm25s.tokenize(corpus, stopwords="en", show_progress=False)
        retriever.index(corpus_tokens, show_progress=False)
        query_tokens = bm25s.tokenize(
            [" ".join(query_terms)],
            stopwords="en",
            show_progress=False,
        )
        doc_ids, scores = retriever.retrieve(
            query_tokens,
            k=len(corpus),
            show_progress=False,
        )
    except Exception as exc:  # pragma: no cover - defensive; bm25s is fiddly
        _log.debug("bm25 scoring failed (%s) — falling back to keyword scorer", exc)
        return None

    # Map returned (doc_id, score) pairs back to the input order.
    aligned = [0.0] * len(corpus)
    row_ids = doc_ids[0]
    row_scores = scores[0]
    max_score = 0.0
    for j in range(len(row_ids)):
        s = float(row_scores[j])
        if s > max_score:
            max_score = s
    for j in range(len(row_ids)):
        doc_idx = int(row_ids[j])
        raw = float(row_scores[j])
        aligned[doc_idx] = raw / max_score if max_score > 0 else 0.0
    return aligned


def _context_component(
    rule: dict[str, Any],
    *,
    idx: int,
    keywords: list[str] | None,
    bm25_scores: list[float] | None,
) -> float:
    """Context relevance: BM25 normalized score when available, keyword fallback otherwise."""
    if bm25_scores is not None and 0 <= idx < len(bm25_scores):
        return bm25_scores[idx]
    return _keyword_context_relevance(rule.get("description", ""), keywords)


def _keyword_context_relevance(description: str, keywords: list[str] | None) -> float:
    if not keywords:
        return 0.5  # neutral when no context provided
    desc_lower = description.lower()
    hits = sum(1 for kw in keywords if kw.lower() in desc_lower)
    return hits / len(keywords)


def _recency_score(last_session: int, current_session: int) -> float:
    if current_session <= 0 or last_session <= 0:
        return 0.5  # neutral when session info unavailable
    sessions_ago = max(0, current_session - last_session)
    return 1.0 / (1.0 + sessions_ago * 0.1)


def _fire_count_score(fire_count: int) -> float:
    return min(1.0, math.log1p(fire_count) / 5.0)


def _effectiveness_bonus(
    rule: dict[str, Any],
    effectiveness: dict[str, dict[str, Any]] | None,
) -> float:
    if not effectiveness:
        return 0.0
    rule_id = rule.get("id") or rule.get("description", "")
    info = effectiveness.get(rule_id)
    if info is None:
        return 0.0
    if info.get("effective"):
        return 0.10
    return -0.10
