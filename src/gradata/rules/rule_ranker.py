"""Context-aware rule ranker. Weights: 30% scope / 25% confidence (Thompson Beta(α,β) when
GRADATA_THOMPSON_RANKING=1) / 20% BM25 / 15% recency / 10% fires. Effectiveness bonus
∈[0,1]. Deterministic per session_seed."""

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
                    _retr.index(
                        bm25s.tokenize(_corpus, stopwords="en", show_progress=False),
                        show_progress=False,
                    )
                    _qtok = bm25s.tokenize([" ".join(_qt)], stopwords="en", show_progress=False)
                    _ids, _scs = _retr.retrieve(_qtok, k=len(_corpus), show_progress=False)
                    _max = max((float(s) for s in _scs[0]), default=0.0)
                    bm25_scores = [0.0] * len(_corpus)
                    for _j in range(len(_ids[0])):
                        bm25_scores[int(_ids[0][_j])] = (
                            float(_scs[0][_j]) / _max if _max > 0 else 0.0
                        )
                except Exception as _exc:  # pragma: no cover - defensive
                    _log.debug("bm25 scoring failed (%s) — falling back to keyword scorer", _exc)
                    bm25_scores = None

    # Deterministic-per-session RNG for Thompson.
    rng = random.Random(session_seed) if session_seed is not None else random.Random()

    scored: list[tuple[float, dict[str, Any]]] = []
    for idx, rule in enumerate(rules):
        if task_type is None:
            _scope = 0.5
        else:
            _cat = rule.get("category", "").upper()
            _tt = task_type.upper()
            _scope = 1.0 if _cat == _tt else (0.7 if _cat in _tt or _tt in _cat else 0.5)
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
        _ls = rule.get("last_session", 0)
        _rec = (
            1.0 / (1.0 + max(0, current_session - _ls) * 0.1)
            if current_session > 0 and _ls > 0
            else 0.5
        )
        _fire = _fire_count_score(rule.get("fire_count", 0))
        _base = 0.30 * _scope + 0.25 * _confidence + 0.20 * _ctx + 0.15 * _rec + 0.10 * _fire
        _eb = 0.0
        if effectiveness and (
            _info := effectiveness.get(rule.get("id") or rule.get("description", ""))
        ):
            _eb = 0.10 if _info.get("effective") else -0.10
        score = max(0.0, min(1.0, _base + _eb))
        scored.append((score, rule))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [rule for _, rule in scored[:max_rules]]


# ------------------------------------------------------------------
# Internal scoring helpers
# ------------------------------------------------------------------


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
    if not keywords:
        return 0.5
    _dl = rule.get("description", "").lower()
    return sum(1 for kw in keywords if kw.lower() in _dl) / len(keywords)


def _fire_count_score(fire_count: int) -> float:
    return min(1.0, math.log1p(fire_count) / 5.0)
