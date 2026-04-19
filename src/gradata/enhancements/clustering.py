"""Rule Clustering and Contradiction Detection — Layer 1 cluster analysis. Detects contradictions
between rules and groups related lessons by category/domain. Imports from gradata._types only."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .._types import Lesson, LessonState


@dataclass
class RuleCluster:
    """A cluster of related rules with shared domain/category."""

    cluster_id: str
    domain: str
    category: str
    member_ids: list[str] = field(default_factory=list)
    cluster_confidence: float = 0.0
    summary: str = ""
    contradictions: list[tuple[str, str]] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.member_ids)

    @property
    def has_contradictions(self) -> bool:
        return len(self.contradictions) > 0


def detect_contradictions(
    lessons: list[Lesson],
) -> list[tuple[str, str]]:
    """Find potentially contradicting rules within a group.

    Uses keyword overlap + negation detection. Two rules contradict if:
    - They share significant keyword overlap (>= 3 common tokens)
    - One contains negation language the other doesn't

    Returns list of (rule_id_1, rule_id_2) pairs.
    """
    _NEGATION_WORDS = {"never", "dont", "don", "not", "stop", "avoid", "without"}

    def tokenize(text: str) -> set[str]:
        return set(re.findall(r"[a-z]{3,}", text.lower()))

    def has_negation(text: str) -> bool:
        words = set(re.findall(r"[a-z]+", text.lower()))
        return bool(words & _NEGATION_WORDS | {w for w in words if w == "no"})

    contradictions: list[tuple[str, str]] = []
    for i, a in enumerate(lessons):
        tokens_a = tokenize(a.description)
        neg_a = has_negation(a.description)

        for b in lessons[i + 1 :]:
            tokens_b = tokenize(b.description)
            neg_b = has_negation(b.description)

            # Need significant overlap AND different negation status
            overlap = len(tokens_a & tokens_b)
            if overlap >= 3 and neg_a != neg_b:
                id_a = f"{a.category}:{a.description[:40]}"
                id_b = f"{b.category}:{b.description[:40]}"
                contradictions.append((id_a, id_b))

    return contradictions


def cluster_rules(
    lessons: list[Lesson],
    min_cluster_size: int = 2,
) -> list[RuleCluster]:
    """Group graduated rules into clusters by (category, domain).

    Rules in the same category and domain with similar descriptions are clustered.
    Cluster confidence = weighted mean of member confidences.
    """
    import json
    from collections import defaultdict

    def _extract_domain(lesson: Lesson) -> str:
        if lesson.scope_json:
            try:
                scope = json.loads(lesson.scope_json)
                return scope.get("domain", "") or "global"
            except (json.JSONDecodeError, TypeError):
                pass
        return "global"

    # Only cluster RULE and PATTERN tier
    graduated = [l for l in lessons if l.state.name in ("RULE", "PATTERN")]

    # Group by (category, domain)
    by_category_domain: dict[tuple[str, str], list[Lesson]] = defaultdict(list)
    for lesson in graduated:
        key = (lesson.category, _extract_domain(lesson))
        by_category_domain[key].append(lesson)

    clusters: list[RuleCluster] = []
    for (category, domain), members in by_category_domain.items():
        if len(members) < min_cluster_size:
            continue

        member_ids = [f"{m.category}:{m.description[:40]}" for m in members]
        avg_conf = sum(m.confidence for m in members) / len(members)

        # Detect contradictions within cluster
        contradictions = detect_contradictions(members)

        # Build summary from member descriptions.
        # Lean format: bracket header already encodes count + category, so the
        # summary text only needs the descriptions themselves. Cap at 3 (was 5)
        # since clusters now only fire when no meta-rule covers the category —
        # the cluster is the fallback abstraction, not the primary one.
        descriptions = [m.description for m in members[:3]]
        summary = "; ".join(descriptions)
        if len(members) > 3:
            summary += f" (+{len(members) - 3})"

        cluster = RuleCluster(
            cluster_id=f"cluster-{category.lower()}-{domain.lower()}",
            domain=domain,
            category=category,
            member_ids=member_ids,
            cluster_confidence=round(avg_conf, 4),
            summary=summary,
            contradictions=contradictions,
        )
        clusters.append(cluster)

    return clusters


def promote_instinct_clusters(
    lessons: list[Lesson],
    min_cluster_size: int = 3,
    coherence_threshold: float = 0.80,
) -> list[str]:
    """Find INSTINCT-tier clusters that deserve PATTERN promotion.

    3+ INSTINCT rules in the same category with high inter-coherence
    (no contradictions, similar confidence) get promoted as a group.

    Returns list of promoted lesson descriptions.
    """
    from collections import defaultdict

    instinct = [l for l in lessons if l.state.name == "INSTINCT"]
    by_category: dict[str, list[Lesson]] = defaultdict(list)
    for lesson in instinct:
        by_category[lesson.category].append(lesson)

    promoted: list[str] = []
    for _category, members in by_category.items():
        if len(members) < min_cluster_size:
            continue

        contradictions = detect_contradictions(members)
        if contradictions:
            continue  # Incoherent cluster, skip

        # Check confidence coherence (std dev < threshold complement)
        confs = [m.confidence for m in members]
        mean_conf = sum(confs) / len(confs)
        variance = sum((c - mean_conf) ** 2 for c in confs) / len(confs)
        std_dev = variance**0.5

        if std_dev > (1.0 - coherence_threshold):
            continue  # Too much variance

        # Promote all members to PATTERN; leave confidence untouched so the
        # graduation pipeline can apply its own thresholds.
        for member in members:
            member.state = LessonState.PATTERN
            promoted.append(member.description)

    return promoted
