"""Tests for rule clustering and contradiction detection (Phase 1)."""
from __future__ import annotations

import pytest

from gradata._types import CorrectionType, Lesson, LessonState, RuleTransferScope
from gradata.enhancements.self_improvement import (
    RuleCluster,
    cluster_rules,
    detect_contradictions,
    promote_instinct_clusters,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lesson(
    description: str,
    category: str = "DRAFTING",
    state: LessonState = LessonState.RULE,
    confidence: float = 0.92,
    scope_json: str = "",
) -> Lesson:
    return Lesson(
        date="2026-01-01",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
        scope_json=scope_json,
    )


# ---------------------------------------------------------------------------
# cluster_rules tests
# ---------------------------------------------------------------------------

def test_cluster_rules_empty_lessons_returns_empty():
    """cluster_rules with no lessons should return an empty list."""
    assert cluster_rules([]) == []


def test_cluster_rules_groups_by_category():
    """Lessons in the same category should end up in the same cluster."""
    lessons = [
        _lesson("Always use full stops at the end", category="DRAFTING"),
        _lesson("Use active voice in emails", category="DRAFTING"),
        _lesson("Verify numbers before reporting", category="ACCURACY"),
        _lesson("Double check statistics before sharing", category="ACCURACY"),
    ]
    clusters = cluster_rules(lessons, min_cluster_size=2)
    categories = {c.category for c in clusters}
    assert "DRAFTING" in categories
    assert "ACCURACY" in categories
    # Each cluster should only contain members from its own category
    for cluster in clusters:
        for member_id in cluster.member_ids:
            assert member_id.startswith(cluster.category + ":")


def test_cluster_rules_min_cluster_size_filters_small_groups():
    """Categories with fewer members than min_cluster_size should be excluded."""
    lessons = [
        _lesson("Use full stops", category="DRAFTING"),
        _lesson("Active voice preferred", category="DRAFTING"),
        _lesson("Solo rule here", category="PROCESS"),  # only one
    ]
    clusters = cluster_rules(lessons, min_cluster_size=2)
    categories = {c.category for c in clusters}
    assert "DRAFTING" in categories
    assert "PROCESS" not in categories


def test_cluster_confidence_is_mean_of_member_confidences():
    """cluster_confidence should be the arithmetic mean of member confidences."""
    lessons = [
        _lesson("Rule A", confidence=0.90),
        _lesson("Rule B", confidence=0.94),
        _lesson("Rule C", confidence=0.92),
    ]
    clusters = cluster_rules(lessons, min_cluster_size=2)
    assert len(clusters) == 1
    expected = round((0.90 + 0.94 + 0.92) / 3, 4)
    assert clusters[0].cluster_confidence == expected


def test_cluster_rules_only_includes_rule_and_pattern_tier():
    """INSTINCT-tier lessons should not appear in clusters."""
    lessons = [
        _lesson("Rule level", state=LessonState.RULE),
        _lesson("Pattern level", state=LessonState.PATTERN, confidence=0.75),
        _lesson("Instinct level", state=LessonState.INSTINCT, confidence=0.45),
    ]
    clusters = cluster_rules(lessons, min_cluster_size=2)
    # Only two qualified lessons -> one cluster (DRAFTING)
    assert len(clusters) == 1
    # The instinct member_id should not appear
    all_ids = [mid for c in clusters for mid in c.member_ids]
    assert all("Instinct level" not in mid for mid in all_ids)


def test_cluster_rules_domain_from_scope_json():
    """Domain should be extracted from the first member's scope_json."""
    import json
    scope = json.dumps({"domain": "email"})
    lessons = [
        _lesson("Rule A", scope_json=scope),
        _lesson("Rule B", scope_json=scope),
    ]
    clusters = cluster_rules(lessons, min_cluster_size=2)
    assert clusters[0].domain == "email"


def test_cluster_rules_domain_defaults_to_global_when_no_scope():
    """Domain should fall back to 'global' when scope_json is empty."""
    lessons = [
        _lesson("Rule A"),
        _lesson("Rule B"),
    ]
    clusters = cluster_rules(lessons, min_cluster_size=2)
    assert clusters[0].domain == "global"


# ---------------------------------------------------------------------------
# detect_contradictions tests
# ---------------------------------------------------------------------------

def test_detect_contradictions_finds_never_vs_always_pair():
    """'never X' and 'always X' with >= 3 shared tokens should be flagged."""
    a = _lesson("never use emojis in professional emails drafts")
    b = _lesson("always use emojis in professional emails drafts")
    result = detect_contradictions([a, b])
    assert len(result) == 1
    # Both IDs should appear in the contradiction pair
    assert any("never use emojis" in r[0] or "never use emojis" in r[1] for r in result)


def test_detect_contradictions_ignores_non_overlapping_rules():
    """Rules with no shared keywords should not be flagged."""
    a = _lesson("never skip unit tests before shipping")
    b = _lesson("always greet prospects warmly and personally")
    result = detect_contradictions([a, b])
    assert result == []


def test_detect_contradictions_requires_at_least_3_overlapping_tokens():
    """Two tokens of overlap should not trigger a contradiction flag."""
    # "report numbers" — 2 meaningful tokens overlapping
    a = _lesson("never report numbers")
    b = _lesson("always report numbers")
    # "report" and "numbers" = 2 tokens (each >= 3 chars) -> should NOT trigger
    # We need at least 3 common tokens
    # Let's verify by checking token extraction: "never", "report", "numbers" vs
    # "always", "report", "numbers" -> overlap = {"report", "numbers"} = 2 tokens
    result = detect_contradictions([a, b])
    # 2 overlapping tokens < 3 threshold -> no contradiction
    assert result == []


def test_detect_contradictions_returns_pairs_as_tuples():
    """Each contradiction should be a (str, str) tuple."""
    a = _lesson("never use passive voice in professional email drafts")
    b = _lesson("always use passive voice in professional email drafts")
    result = detect_contradictions([a, b])
    assert len(result) >= 1
    for pair in result:
        assert isinstance(pair, tuple)
        assert len(pair) == 2
        assert isinstance(pair[0], str)
        assert isinstance(pair[1], str)


def test_detect_contradictions_same_negation_not_flagged():
    """Two rules both negated should not be flagged as contradictions."""
    a = _lesson("never send emails without proofreading carefully")
    b = _lesson("never skip tests without running coverage report")
    # Both have negation -> neg_a == neg_b -> no contradiction
    result = detect_contradictions([a, b])
    assert result == []


# ---------------------------------------------------------------------------
# RuleCluster property tests
# ---------------------------------------------------------------------------

def test_rule_cluster_has_contradictions_property_true():
    """has_contradictions should be True when contradictions list is non-empty."""
    cluster = RuleCluster(
        cluster_id="cluster-drafting",
        domain="global",
        category="DRAFTING",
        contradictions=[("rule_a", "rule_b")],
    )
    assert cluster.has_contradictions is True


def test_rule_cluster_has_contradictions_property_false():
    """has_contradictions should be False when contradictions list is empty."""
    cluster = RuleCluster(
        cluster_id="cluster-drafting",
        domain="global",
        category="DRAFTING",
        contradictions=[],
    )
    assert cluster.has_contradictions is False


def test_rule_cluster_size_property():
    """size should reflect the number of member_ids."""
    cluster = RuleCluster(
        cluster_id="cluster-drafting",
        domain="global",
        category="DRAFTING",
        member_ids=["a", "b", "c"],
    )
    assert cluster.size == 3


# ---------------------------------------------------------------------------
# promote_instinct_clusters tests
# ---------------------------------------------------------------------------

def _instinct_lesson(description: str, category: str = "DRAFTING", confidence: float = 0.50) -> Lesson:
    return _lesson(description, category=category, state=LessonState.INSTINCT, confidence=confidence)


def test_promote_instinct_clusters_promotes_coherent_group():
    """3+ coherent INSTINCT lessons in the same category should be promoted to PATTERN."""
    lessons = [
        _instinct_lesson("Use clear subject lines in all outbound emails", confidence=0.52),
        _instinct_lesson("Write concise paragraphs in all outbound messages", confidence=0.54),
        _instinct_lesson("Proofread outbound emails before sending them", confidence=0.53),
    ]
    promoted = promote_instinct_clusters(lessons, min_cluster_size=3)
    assert len(promoted) == 3
    for lesson in lessons:
        assert lesson.state == LessonState.PATTERN
        assert lesson.confidence >= 0.60


def test_promote_instinct_clusters_skips_contradicting_groups():
    """A cluster with contradictions should not be promoted."""
    # "never use emojis professional emails drafts" has negation ("never")
    # "always use emojis professional emails drafts" has NO negation word
    # They share >= 3 tokens -> contradiction detected -> cluster skipped
    lessons = [
        _instinct_lesson("never use emojis in professional emails drafts"),
        _instinct_lesson("always use emojis in professional emails drafts"),
        _instinct_lesson("Use bullet points for clarity in lists and outlines"),
    ]
    promoted = promote_instinct_clusters(lessons, min_cluster_size=2)
    # The first two contradict -> cluster skipped -> nothing promoted
    assert promoted == []
    # States should remain INSTINCT
    for lesson in lessons:
        assert lesson.state == LessonState.INSTINCT


def test_promote_instinct_clusters_skips_small_groups():
    """Fewer than min_cluster_size INSTINCT lessons should not be promoted."""
    lessons = [
        _instinct_lesson("Use full stops at end", confidence=0.52),
        _instinct_lesson("Keep emails brief", confidence=0.54),
    ]
    promoted = promote_instinct_clusters(lessons, min_cluster_size=3)
    assert promoted == []
    for lesson in lessons:
        assert lesson.state == LessonState.INSTINCT


def test_promote_instinct_clusters_skips_high_variance_groups():
    """Groups with high confidence variance should not be promoted."""
    lessons = [
        _instinct_lesson("Rule low confidence", confidence=0.40),
        _instinct_lesson("Rule mid confidence", confidence=0.55),
        _instinct_lesson("Rule high confidence", confidence=0.58),
    ]
    # std_dev of [0.40, 0.55, 0.58] is around 0.079, threshold complement is 0.20 -> should pass
    # To force high variance, use very spread values
    lessons[0].confidence = 0.01
    lessons[1].confidence = 0.55
    lessons[2].confidence = 0.59
    # std_dev ~ 0.24 > (1 - 0.80) = 0.20 -> skip
    promoted = promote_instinct_clusters(lessons, min_cluster_size=3, coherence_threshold=0.80)
    assert promoted == []


def test_promote_instinct_clusters_returns_descriptions():
    """Return value should be a list of the promoted lessons' descriptions."""
    lessons = [
        _instinct_lesson("Write concise email subjects every time", confidence=0.52),
        _instinct_lesson("Avoid jargon in all email communications sent", confidence=0.53),
        _instinct_lesson("Personalize greetings in each outbound email sent", confidence=0.51),
    ]
    promoted = promote_instinct_clusters(lessons, min_cluster_size=3)
    assert set(promoted) == {l.description for l in lessons}


def test_promote_instinct_clusters_only_targets_instinct_tier():
    """RULE/PATTERN lessons should be ignored by promote_instinct_clusters."""
    lessons = [
        _lesson("An established rule", state=LessonState.RULE),
        _lesson("A pattern rule", state=LessonState.PATTERN, confidence=0.75),
        _instinct_lesson("Solo instinct rule"),
    ]
    promoted = promote_instinct_clusters(lessons, min_cluster_size=2)
    # Only one INSTINCT lesson -> below min_cluster_size of 2 -> no promotion
    assert promoted == []
    # RULE and PATTERN lessons untouched
    assert lessons[0].state == LessonState.RULE
    assert lessons[1].state == LessonState.PATTERN
