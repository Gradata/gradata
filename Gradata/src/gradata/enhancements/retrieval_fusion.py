"""Multi-strategy retrieval fusion with correction-aware boosting.

Adapted from Hindsight's reciprocal rank fusion (RRF) algorithm.
Merges results from multiple retrieval strategies into one ranked list,
then applies correction-aware boosting (Gradata-unique).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScoredRule:
    """A rule scored by a single retrieval strategy."""

    rule_id: str
    text: str
    score: float
    source: str  # "semantic", "keyword", "scope", "temporal"
    metadata: dict = field(default_factory=dict)


@dataclass
class MergedRule:
    """A rule after RRF merging from multiple strategies."""

    rule: ScoredRule
    rrf_score: float
    rrf_rank: int
    source_ranks: dict[str, int] = field(default_factory=dict)
    combined_score: float = 0.0


def reciprocal_rank_fusion(
    result_lists: list[list[ScoredRule]],
    k: int = 60,
    source_weights: dict[str, float] | None = None,
) -> list[MergedRule]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion.

    Formula: score(doc) = SUM over lists L: weight_L / (k + rank_L(doc))
    Default k=60 from Cormack et al. 2009.

    Args:
        result_lists: List of ranked result lists from different strategies.
        k: Smoothing constant. Higher = flatter rank distribution.
        source_weights: Optional per-source weight multipliers.

    Returns:
        List of MergedRule sorted by descending rrf_score.
    """
    if not result_lists:
        return []

    source_names = ["semantic", "keyword", "scope", "temporal"]
    rrf_scores: dict[str, float] = {}
    source_ranks: dict[str, dict[str, int]] = {}
    all_rules: dict[str, ScoredRule] = {}

    for idx, results in enumerate(result_lists):
        list_source = source_names[idx] if idx < len(source_names) else f"source_{idx}"

        for rank, rule in enumerate(results, start=1):
            # Use rule.source for weight lookup (actual source, not list position)
            source = rule.source
            weight = (source_weights or {}).get(source, 1.0)
            # First-seen metadata wins (deduplication)
            if rule.rule_id not in all_rules:
                all_rules[rule.rule_id] = rule
            if rule.rule_id not in rrf_scores:
                rrf_scores[rule.rule_id] = 0.0
                source_ranks[rule.rule_id] = {}

            rrf_scores[rule.rule_id] += weight / (k + rank)
            source_ranks[rule.rule_id][f"{list_source}_rank"] = rank

    sorted_ids = sorted(rrf_scores, key=lambda rid: rrf_scores[rid], reverse=True)

    merged = []
    for rrf_rank, rule_id in enumerate(sorted_ids, start=1):
        merged.append(
            MergedRule(
                rule=all_rules[rule_id],
                rrf_score=rrf_scores[rule_id],
                rrf_rank=rrf_rank,
                source_ranks=source_ranks[rule_id],
                combined_score=rrf_scores[rule_id],
            )
        )

    return merged


def apply_correction_boost(
    results: list[MergedRule],
    correction_alpha: float = 0.30,
    recency_alpha: float = 0.20,
    severity_alpha: float = 0.10,
) -> None:
    """Apply multiplicative correction-aware boosting (in-place).

    Adapted from Hindsight's reranking but with Gradata-unique signals:
    - correction_alpha: boost for rules born from corrections
    - recency_alpha: boost for recently-fired rules
    - severity_alpha: boost for rules from severe corrections

    Each boost = 1.0 + alpha * (signal - 0.5), so range is [1-alpha/2, 1+alpha/2].
    Signals are floats in [0, 1]. A signal of 0.5 is neutral (no boost, no penalty).

    Args:
        results: List of MergedRule to boost in-place.
        correction_alpha: Weight for correction-origin signal.
        recency_alpha: Weight for recency signal.
        severity_alpha: Weight for severity signal.
    """
    for mr in results:
        meta = mr.rule.metadata

        # Correction-born boost (binary: 0.0 or 1.0)
        is_correction = 1.0 if meta.get("from_correction", False) else 0.0
        correction_boost = 1.0 + correction_alpha * (is_correction - 0.5)

        # Recency boost (0.0 = stale, 1.0 = just fired)
        recency = max(0.0, min(1.0, float(meta.get("recency_score", 0.5))))
        recency_boost = 1.0 + recency_alpha * (recency - 0.5)

        # Severity boost (normalized 0-1 from avg correction severity)
        severity = max(0.0, min(1.0, float(meta.get("severity_score", 0.5))))
        severity_boost = 1.0 + severity_alpha * (severity - 0.5)

        mr.combined_score = mr.rrf_score * correction_boost * recency_boost * severity_boost
