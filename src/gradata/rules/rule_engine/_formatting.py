"""
Rule formatting — deduplication, merging, entropy ordering, prompt injection.
==============================================================================
Transforms :class:`AppliedRule` objects into injected text for LLM prompts.
No I/O, no external state.
"""

from __future__ import annotations

import hashlib
import random
import secrets
from collections import defaultdict

from gradata._types import Lesson, LessonState, RuleTransferScope

from ._models import AppliedRule


# ---------------------------------------------------------------------------
# Deduplication and Merging
# ---------------------------------------------------------------------------


def _deduplicate_rules(rules: list[AppliedRule], threshold: float = 0.85) -> list[AppliedRule]:
    """Remove near-duplicate rules based on word overlap ratio.

    Only removes rules that are nearly identical (85%+ word overlap).
    Rules from different categories are never considered duplicates.
    """
    if len(rules) <= 1:
        return rules

    def _word_set(text: str) -> set[str]:
        return set(text.lower().split())

    kept: list[AppliedRule] = []
    for rule in rules:
        words = _word_set(rule.lesson.description)
        is_dup = False
        for existing in kept:
            # Different categories are never duplicates
            if existing.lesson.category != rule.lesson.category:
                continue
            existing_words = _word_set(existing.lesson.description)
            if not words or not existing_words:
                continue
            overlap = len(words & existing_words) / min(len(words), len(existing_words))
            if overlap >= threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(rule)
    return kept


def merge_related_rules(rules: list[AppliedRule], min_group_size: int = 2) -> list[AppliedRule]:
    """Merge rules sharing a category into compressed blocks.

    Groups with fewer than *min_group_size* rules stay individual.
    Merged rules use the highest confidence from the group and combine
    descriptions into one compressed instruction, saving tokens.
    """
    by_cat: dict[str, list[AppliedRule]] = defaultdict(list)
    for rule in rules:
        by_cat[rule.lesson.category].append(rule)

    result: list[AppliedRule] = []
    for cat, group in by_cat.items():
        if len(group) < min_group_size:
            result.extend(group)
            continue
        # Merge: combine descriptions, take highest confidence
        best = max(group, key=lambda r: r.lesson.confidence)
        descriptions = [r.lesson.description for r in group]
        merged_desc = ". ".join(d.rstrip(".") for d in descriptions) + "."
        merged_instruction = f"{cat}: {merged_desc}"
        merged_rule = AppliedRule(
            rule_id=f"merged_{cat.lower()}",
            lesson=best.lesson,
            relevance=max(r.relevance for r in group),
            instruction=merged_instruction,
        )
        result.append(merged_rule)
    return result


# ---------------------------------------------------------------------------
# Entropy-based rule ordering (Lu et al. 2022)
# ---------------------------------------------------------------------------
# Lu et al. 2022, "Fantastically Ordered Prompts and Where to Find Them"
# (https://arxiv.org/abs/2104.08786) showed that the same demonstrations in
# different orders span random-guess to SOTA performance in ICL. The paper
# proposes two order-selection proxies: GlobalE (entropy of predicted labels
# across a probing set) and LocalE (per-example label entropy). Both require
# live LLM scoring which the SDK's pure-logic layer cannot do.
#
# We use a structural proxy for GlobalE: category-distribution entropy across
# positional zones (primacy / middle / recency). Higher entropy means the
# ordering spreads topically diverse rules across salient attention positions
# (primacy + recency, per Liu et al. 2023 "Lost in the Middle"), which
# empirically correlates with LLM performance per Lu 2022. We sample
# `_DEFAULT_PERMUTATION_SAMPLES` random permutations and pick the highest
# scorer; ties broken by the first sample seen.
#
# Results are cached by (task_type, rule_set_hash) so session start does not
# pay the permutation cost twice.

_DEFAULT_PERMUTATION_SAMPLES: int = 8
_ORDERING_CACHE: dict[tuple[str, str], list[int]] = {}
_ORDERING_CACHE_MAX: int = 256


def _rule_set_hash(rules: list[AppliedRule]) -> str:
    """Stable content-addressed hash of a rule set for cache keying."""
    joined = "|".join(sorted(r.rule_id for r in rules))
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


def _category_entropy(categories: list[str]) -> float:
    """Shannon entropy (bits) of a category multiset. 0.0 when empty/singleton."""
    if not categories:
        return 0.0
    import math

    counts: dict[str, int] = defaultdict(int)
    for c in categories:
        counts[c] += 1
    total = float(len(categories))
    ent = 0.0
    for n in counts.values():
        p = n / total
        if p > 0.0:
            ent -= p * math.log2(p)
    return ent


def _ordering_entropy(rules: list[AppliedRule]) -> float:
    """Score an ordering by positional category-entropy (GlobalE proxy).

    Partitions the sequence into three zones (primacy / middle / recency)
    and sums the Shannon entropy of categories within each zone. High scores
    mean each salient zone sees a diverse mix of topics instead of a run of
    same-category rules. Zero-padded for sequences shorter than three.
    """
    n = len(rules)
    if n <= 1:
        return 0.0
    # Three roughly-equal zones; middle absorbs remainder when n % 3 != 0
    third = max(1, n // 3)
    primacy = [r.lesson.category for r in rules[:third]]
    recency = [r.lesson.category for r in rules[-third:]]
    middle = [r.lesson.category for r in rules[third:-third]] if n > 2 * third else []
    return _category_entropy(primacy) + _category_entropy(middle) + _category_entropy(recency)


def choose_entropy_ordering(
    rules: list[AppliedRule],
    samples: int = _DEFAULT_PERMUTATION_SAMPLES,
    seed: int | None = None,
    cache_key: tuple[str, str] | None = None,
) -> list[AppliedRule]:
    """Pick the highest-entropy permutation of *rules* over *samples* tries.

    Implements a compute-cheap analogue of Lu et al. 2022's GlobalE selection
    (arXiv:2104.08786). See the module-level note for the structural proxy
    used in place of live LLM scoring. Returns a new list; does not mutate.

    Args:
        rules: Candidates to order. Lists of length <=1 are returned as-is.
        samples: Number of random permutations to evaluate. Default 8.
        seed: Optional seed for deterministic sampling. When None, uses
            :func:`secrets.randbelow` for non-determinism (preserves the
            injection-order security property of the prior shuffle path).
        cache_key: Optional ``(task_type, rule_set_hash)`` tuple to cache
            the winning permutation for reuse. When a cached order exists
            and still matches the current rule ids, it is returned without
            re-scoring.

    Returns:
        Permuted list of the same rules, with the lowest structural
        entropy-deficit among the sampled permutations.
    """
    n = len(rules)
    if n <= 1 or samples <= 0:
        return list(rules)

    # Cache hit — but validate that the rule set still matches.
    if cache_key is not None:
        cached = _ORDERING_CACHE.get(cache_key)
        if cached is not None and len(cached) == n and set(cached) == set(range(n)):
            return [rules[i] for i in cached]

    indices = list(range(n))
    rng = random.Random(seed) if seed is not None else None

    def _shuffled() -> list[int]:
        xs = list(indices)
        if rng is not None:
            rng.shuffle(xs)
        else:
            for i in range(len(xs) - 1, 0, -1):
                j = secrets.randbelow(i + 1)
                xs[i], xs[j] = xs[j], xs[i]
        return xs

    best_perm: list[int] | None = None
    best_score = -1.0
    for _ in range(samples):
        perm = _shuffled()
        permuted = [rules[i] for i in perm]
        score = _ordering_entropy(permuted)
        if score > best_score:
            best_score = score
            best_perm = perm

    if best_perm is None:
        best_perm = indices

    # LRU-ish cache eviction: drop arbitrary entries if we hit the cap.
    if cache_key is not None:
        if len(_ORDERING_CACHE) >= _ORDERING_CACHE_MAX:
            # Evict one arbitrary entry (dict insertion order; pop the oldest).
            _ORDERING_CACHE.pop(next(iter(_ORDERING_CACHE)), None)
        _ORDERING_CACHE[cache_key] = best_perm

    return [rules[i] for i in best_perm]


def clear_ordering_cache() -> None:
    """Reset the cross-session permutation cache. Mainly for tests."""
    _ORDERING_CACHE.clear()


# ---------------------------------------------------------------------------
# Prompt Injection Formatting
# ---------------------------------------------------------------------------


def format_rules_for_prompt(
    rules: list[AppliedRule],
    merge: bool = True,
    scope_filter: RuleTransferScope | None = None,
    shuffle_seed: int | None = None,
    entropy_search: bool = True,
    task_type: str = "",
) -> str:
    """Format applied rules into an XML-tagged LLM-injectable block.

    Uses XML tags for unambiguous constraint signaling (Claude best practice).
    Applies primacy/recency positioning: highest-priority rules first,
    brief reminder of the #1 rule at the end.

    If *merge* is True, related rules in the same category are compressed
    into single blocks to save tokens.

    When *scope_filter* is provided, only rules whose lesson's
    ``transfer_scope`` matches are included. This lets the SDK demo
    surface only universal rules.

    When *entropy_search* is True (default), within each tier the ordering
    is chosen by :func:`choose_entropy_ordering` — an approximation of
    GlobalE from Lu et al. 2022 "Fantastically Ordered Prompts"
    (https://arxiv.org/abs/2104.08786). Best orderings are cached per
    ``(task_type, rule_set_hash)`` tuple.

    Args:
        rules: Output from :func:`apply_rules`.
        merge: Whether to merge same-category rules (default True).
        scope_filter: When set, only include rules with this transfer scope.
        shuffle_seed: Optional deterministic seed for in-tier permutation
            sampling. Forwarded to :func:`choose_entropy_ordering`. When
            None, falls back to :mod:`secrets` for non-determinism.
        entropy_search: When True (default), select the highest-entropy
            permutation per tier; when False, keep the input order
            (bypasses search).
        task_type: Optional task-type tag used as part of the ordering
            cache key. Pass the detected task type so different task
            contexts do not share a cached ordering.

    Returns:
        Formatted XML block, or ``""`` if *rules* is empty.
    """
    if scope_filter is not None:
        rules = [r for r in rules if r.lesson.transfer_scope == scope_filter]

    if not rules:
        return ""

    # Deduplicate and merge related rules to save tokens
    rules = _deduplicate_rules(rules)
    if merge:
        rules = merge_related_rules(rules)

    # Bucketed ordering: group by tier, order within each tier by entropy
    # proxy (Lu 2022), concatenate in tier order (RULE first). Still
    # preserves the prior security property — adversaries cannot infer
    # per-rule confidence rankings because the in-tier order is driven by
    # category diversity, not confidence — while also picking the
    # empirically-better permutation for ICL.
    tier_order = [LessonState.RULE, LessonState.PATTERN, LessonState.INSTINCT]
    buckets: dict[LessonState, list[AppliedRule]] = {t: [] for t in tier_order}
    for r in rules:
        bucket = buckets.get(r.lesson.state)
        if bucket is not None:
            bucket.append(r)

    ordered: list[AppliedRule] = []
    for tier in tier_order:
        bucket = buckets[tier]
        if not bucket:
            continue
        if entropy_search and len(bucket) > 1:
            # When a caller supplies shuffle_seed they want per-seed
            # determinism (e.g. security tests that compare orderings
            # across seeds). Skip the cross-session cache in that path.
            cache_key = (
                None
                if shuffle_seed is not None
                else (f"{task_type}::{tier.value}", _rule_set_hash(bucket))
            )
            bucket = choose_entropy_ordering(
                bucket,
                seed=shuffle_seed,
                cache_key=cache_key,
            )
        ordered.extend(bucket)
    rules = ordered

    lines = [
        "<brain-rules>",
    ]

    for rule in rules:
        lines.append(f"- {rule.instruction}")

        # Include few-shot examples only for low-confidence rules with misfires
        lesson = rule.lesson
        needs_reinforcement = lesson.confidence < 0.70 and getattr(lesson, "misfire_count", 0) > 1
        example_draft = getattr(lesson, "example_draft", None)
        example_corrected = getattr(lesson, "example_corrected", None)
        if needs_reinforcement and example_draft is not None and example_corrected is not None:
            lines.append(f'   e.g. "{example_draft[:80]}" -> "{example_corrected[:80]}"')

    lines.append("</brain-rules>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Constitutional Format (Experimental)
# ---------------------------------------------------------------------------

# Category-to-value mapping for constitutional framing
_CONSTITUTIONAL_VALUE_MAP: dict[str, str] = {
    "TONE": "communication style",
    "ACCURACY": "accuracy and precision",
    "STRUCTURE": "clear organization",
    "DRAFTING": "polished writing",
    "FORMAT": "the user's formatting preferences",
    "SECURITY": "security and safety",
}

# Imperative prefixes stripped during constitutional transformation
_IMPERATIVE_PREFIXES: tuple[str, ...] = (
    "Always ",
    "Never ",
    "Don't ",
    "Do not ",
    "Be ",
    "Use ",
    "Avoid ",
)


def format_rule_constitutional(category: str, description: str) -> str:
    """Format a rule as a constitutional principle (experimental).

    Transforms imperative rules into value statements:
    - "Be concise" -> "You value communication style -- concise"
    - "Always cite sources" -> "You value accuracy and precision -- cite sources"
    - "Never use em dashes" -> "You value the user's formatting preferences -- use em dashes"

    This is EXPERIMENTAL. Ship behind format_style="constitutional" flag.

    Args:
        category: The lesson category (e.g. "TONE", "ACCURACY").
        description: The rule description text.

    Returns:
        XML-tagged principle string.
    """
    value = _CONSTITUTIONAL_VALUE_MAP.get(category.upper(), "quality")

    desc = description.strip()
    for prefix in _IMPERATIVE_PREFIXES:
        if desc.startswith(prefix):
            desc = desc[len(prefix):]
            break

    return f"<principle>You value {value} — {desc.lower()}</principle>"


def format_rules_styled(
    rules: list[AppliedRule],
    format_style: str = "imperative",
) -> str:
    """Format rules for prompt injection in the specified style.

    Args:
        rules: List of :class:`AppliedRule` objects from :func:`apply_rules`.
        format_style: ``"imperative"`` (default) uses the existing bracket
            format. ``"constitutional"`` (experimental) reframes each rule
            as a value-based principle.

    Returns:
        Newline-joined formatted rules string. Empty string if *rules* is empty.
    """
    if not rules:
        return ""

    if format_style == "constitutional":
        lines = []
        for rule in rules:
            lines.append(format_rule_constitutional(rule.lesson.category, rule.lesson.description))
        return "\n".join(lines)
    else:
        # Default imperative format
        return "\n".join(rule.instruction for rule in rules)


# ---------------------------------------------------------------------------
# Example Capture
# ---------------------------------------------------------------------------

_EXAMPLE_MAX_CHARS = 80


def capture_example_from_correction(
    lesson: Lesson,
    draft: str,
    corrected: str,
) -> Lesson:
    """Attach a draft/corrected pair as a few-shot example on a lesson.

    When a correction matches an existing lesson's category, the caller
    should invoke this to store the pair on the lesson so that
    :func:`format_rules_for_prompt` can include it for reinforcement.

    Only the first ``_EXAMPLE_MAX_CHARS`` characters of each string are
    stored to keep token cost low.  If the lesson already has an example
    the new one overwrites it (most recent correction is most relevant).

    Args:
        lesson: The lesson to attach the example to.
        draft: The AI-generated text before correction.
        corrected: The human-edited text after correction.

    Returns:
        The same lesson instance, mutated with the new example fields.
    """
    lesson.example_draft = draft[:_EXAMPLE_MAX_CHARS]
    lesson.example_corrected = corrected[:_EXAMPLE_MAX_CHARS]
    return lesson
