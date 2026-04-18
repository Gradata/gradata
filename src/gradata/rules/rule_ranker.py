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
    bm25_scores: list[float] | None = None
    if _BM25_AVAILABLE and bm25s is not None:
        _qt: list[str] = []
        if task_type:
            _qt.append(str(task_type))
        if context_keywords:
            _qt.extend(str(k) for k in context_keywords)
        if _qt:
            _corpus: list[str] = []
            for _r in rules:
                _tags = _r.get("tags", "")
                if isinstance(_tags, (list, tuple)):
                    _tags = " ".join(str(t) for t in _tags)
                _doc = " ".join(str(_r.get(f, "")) for f in ("category", "description"))
                _corpus.append(f"{_doc} {_tags}".strip())
            if any(_corpus):
                try:
                    _retr = bm25s.BM25()
                    _retr.index(bm25s.tokenize(_corpus, stopwords="en", show_progress=False), show_progress=False)
                    _qtok = bm25s.tokenize([" ".join(_qt)], stopwords="en", show_progress=False)
                    _ids, _scs = _retr.retrieve(_qtok, k=len(_corpus), show_progress=False)
                    _max = max((float(s) for s in _scs[0]), default=0.0)
                    bm25_scores = [0.0] * len(_corpus)
                    for _j in range(len(_ids[0])):
                        bm25_scores[int(_ids[0][_j])] = float(_scs[0][_j]) / _max if _max > 0 else 0.0
                except Exception as _exc:  # pragma: no cover - defensive
                    _log.debug("bm25 scoring failed (%s) — falling back to keyword scorer", _exc)
                    bm25_scores = None

    # Deterministic-per-session RNG for Thompson.
    rng = random.Random(session_seed) if session_seed is not None else random.Random()

    scored: list[tuple[float, dict[str, Any]]] = []
    for idx, rule in enumerate(rules):
        _scope = _scope_match(rule.get("category", ""), task_type)
        if thompson_on:
            _a = max(float(rule.get("alpha", 1.0) or 1.0), 1e-3)
            _b = max(float(rule.get("beta_param", 1.0) or 1.0), 1e-3)
            _confidence = rng.betavariate(_a, _b)
        else:
            _confidence = float(rule.get("confidence", 0.5))
        _ctx = _context_component(rule, idx=idx, keywords=context_keywords, bm25_scores=bm25_scores)
        if wiki_boost:
            _rid = rule.get("id") or rule.get("description", "")
            _ctx = min(1.0, _ctx + wiki_boost.get(_rid, 0.0))
        _rec = _recency_score(rule.get("last_session", 0), current_session)
        _fire = _fire_count_score(rule.get("fire_count", 0))
        _base = 0.30 * _scope + 0.25 * _confidence + 0.20 * _ctx + 0.15 * _rec + 0.10 * _fire
        score = max(0.0, min(1.0, _base + _effectiveness_bonus(rule, effectiveness)))
        scored.append((score, rule))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [rule for _, rule in scored[:max_rules]]


# ------------------------------------------------------------------
# Internal scoring helpers
# ------------------------------------------------------------------


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
