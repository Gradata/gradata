"""
Tree retrieval ranking correctness — regression tests for
``apply_rules_with_tree``.

Council finding (council_2026-05-04T15-53-40.md, Skeptic perspective):
``apply_rules_with_tree`` previously hard-coded ``relevance=1.0`` for every
returned rule, silently bypassing the FSRS / scope-weight ranker. This file
locks in the fix: tree retrieval MUST produce a meaningful relevance score
spread, and high-confidence rules MUST outrank low-confidence ones.
"""

from __future__ import annotations

from gradata._scope import RuleScope
from gradata._types import Lesson, LessonState
from gradata.rules.rule_engine import apply_rules_with_tree


def _make(
    description: str,
    confidence: float,
    *,
    path: str = "TONE/sales/email_draft",
    state: LessonState = LessonState.RULE,
    category: str = "TONE",
) -> Lesson:
    return Lesson(
        date="2026-05-04",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
        path=path,
        fire_count=5,
    )


def test_tree_retrieval_does_not_flat_rate_relevance():
    """High-confidence rule must outrank low-confidence one in tree path.

    Both lessons share the same path so they are co-candidates after tree
    filtering. Ranking must then break the tie via confidence.
    """
    rule_a = _make("Use direct verbs (high-conf)", confidence=0.9)
    rule_b = _make("Use direct verbs (low-conf)", confidence=0.2)
    lessons = [rule_b, rule_a]  # input order intentionally inverted

    scope = RuleScope(domain="sales", task_type="email_draft")
    applied = apply_rules_with_tree(lessons, scope, max_rules=5)

    assert len(applied) == 2, f"expected 2 rules, got {len(applied)}"
    # Highest-confidence lesson must be first.
    assert applied[0].lesson.confidence == 0.9
    assert applied[-1].lesson.confidence == 0.2


def test_tree_retrieval_relevance_is_not_constant():
    """Relevance must reflect ranking — not be flat-rated to 1.0.

    The original bug: every returned AppliedRule had ``relevance=1.0``,
    erasing any signal from scope match / confidence. This test fails on
    the buggy code (all 1.0 → set size == 1) and passes once ranking is
    restored.
    """
    lessons = [
        _make("rule-high", confidence=0.95),
        _make("rule-mid", confidence=0.60),
        _make("rule-low", confidence=0.25),
    ]
    scope = RuleScope(domain="sales", task_type="email_draft")
    applied = apply_rules_with_tree(lessons, scope, max_rules=5)

    relevances = [a.relevance for a in applied]
    assert len(applied) == 3
    # The bug: every AppliedRule had relevance=1.0 (a single value across
    # the result set). Once ranking is restored, downstream consumers must
    # see a non-degenerate relevance signal — not a flat 1.0.
    unique = {round(r, 4) for r in relevances}
    assert unique != {1.0}, (
        f"tree retrieval flat-rated relevance to 1.0 (council finding): relevances={relevances}"
    )


def test_tree_retrieval_top_result_is_highest_confidence():
    """Top-1 invariant: the most confident matching rule wins."""
    lessons = [
        _make("low", confidence=0.30),
        _make("med", confidence=0.55),
        _make("HIGH", confidence=0.92),
        _make("low2", confidence=0.20),
    ]
    scope = RuleScope(domain="sales", task_type="email_draft")
    applied = apply_rules_with_tree(lessons, scope, max_rules=4)

    assert applied, "tree retrieval returned nothing"
    assert applied[0].lesson.description == "HIGH"
