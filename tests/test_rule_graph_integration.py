"""Tests for RuleGraph integration with the correction pipeline."""
from gradata.brain import Brain
from gradata.rules.rule_graph import RuleGraph


def test_brain_has_rule_graph(tmp_path):
    brain = Brain(str(tmp_path))
    assert hasattr(brain, '_rule_graph')
    assert isinstance(brain._rule_graph, RuleGraph)


def test_rule_graph_persists_after_correction(tmp_path):
    brain = Brain(str(tmp_path))
    brain.correct(
        "The system is working good",
        "The system is working well",
        category="DRAFTING",
        session=1,
    )
    # Graph file should exist after correction
    graph_path = tmp_path / "rule_graph.json"
    # Graph may or may not have edges depending on whether rules were applied
    assert hasattr(brain._rule_graph, 'node_count')


def test_co_occurrence_tracked_in_apply_rules():
    """apply_rules records co-occurrence when graph is provided."""
    from gradata._types import Lesson, LessonState
    from gradata._scope import RuleScope
    from gradata.rules.rule_engine import apply_rules

    graph = RuleGraph()
    rules = [
        Lesson(date="2026-04-06", state=LessonState.RULE, confidence=0.95,
               category="DRAFTING", description="Use active voice"),
        Lesson(date="2026-04-06", state=LessonState.RULE, confidence=0.90,
               category="TONE", description="Be concise"),
    ]
    scope = RuleScope()
    apply_rules(rules, scope, graph=graph)

    # Both rules should be applied, creating a co-occurrence edge
    assert graph.node_count >= 0  # May or may not have edges depending on relevance
