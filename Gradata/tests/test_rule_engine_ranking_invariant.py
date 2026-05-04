"""
Ranking-equivalence regression: ``apply_rules`` vs ``apply_rules_with_tree``
on legacy (no-path) corpora.

When no lesson carries a ``path`` field, ``apply_rules_with_tree`` MUST
delegate to the flat ``apply_rules`` path so legacy callers keep their
existing top-K ordering. This locks in the migration-001 backwards-compat
contract introduced when the ``path`` column was added.
"""

from __future__ import annotations

from gradata._scope import RuleScope
from gradata._types import Lesson, LessonState
from gradata.rules.rule_engine import apply_rules, apply_rules_with_tree


def _legacy_lesson(category: str, description: str, confidence: float) -> Lesson:
    """Lesson with no path — represents pre-tree-migration state."""
    return Lesson(
        date="2026-05-04",
        state=LessonState.RULE,
        confidence=confidence,
        category=category,
        description=description,
        fire_count=5,
        # path defaults to "" — legacy corpus
    )


def test_top_k_equivalent_when_no_lessons_have_path():
    """No-path corpus → tree path delegates → identical top-K ordering."""
    lessons = [
        _legacy_lesson("TONE", "be casual", 0.92),
        _legacy_lesson("TONE", "no em dashes", 0.85),
        _legacy_lesson("FORMAT", "short paragraphs", 0.70),
        _legacy_lesson("DRAFTING", "include pricing", 0.60),
        _legacy_lesson("TONE", "first-name basis", 0.45),
    ]
    scope = RuleScope(domain="sales", task_type="email_draft")

    flat = apply_rules(lessons, scope, max_rules=3)
    tree = apply_rules_with_tree(lessons, scope, max_rules=3)

    assert [r.rule_id for r in flat] == [r.rule_id for r in tree], (
        "tree path must defer to flat ranker on legacy (no-path) corpora"
    )
    # Relevance scores must also match in the legacy path — proves we are
    # not silently re-rating in the fallback branch.
    assert [round(r.relevance, 4) for r in flat] == [
        round(r.relevance, 4) for r in tree
    ]


def test_relevance_not_flat_rated_when_paths_present():
    """Companion check: with paths present the new ranker still produces a
    real (non-degenerate) relevance signal — not the old ``1.0`` constant."""
    lessons = [
        Lesson(
            date="2026-05-04",
            state=LessonState.RULE,
            confidence=conf,
            category="TONE",
            description=f"rule-{i}",
            path="TONE/sales/email_draft",
            fire_count=5,
        )
        for i, conf in enumerate([0.95, 0.65, 0.30])
    ]
    scope = RuleScope(domain="sales", task_type="email_draft")
    applied = apply_rules_with_tree(lessons, scope, max_rules=5)

    rels = [a.relevance for a in applied]
    assert applied, "expected ranked rules"
    assert {round(r, 4) for r in rels} != {1.0}, (
        f"relevance regressed to flat 1.0: {rels}"
    )
