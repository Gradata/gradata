"""Tests for rule graph — conflict and co-occurrence edges."""
from pathlib import Path

from gradata.rules.rule_graph import RuleGraph


def test_add_conflict():
    graph = RuleGraph()
    graph.add_conflict("DRAFTING:001", "TONE:002")
    assert graph.has_conflict("DRAFTING:001", "TONE:002")
    assert graph.has_conflict("TONE:002", "DRAFTING:001")  # Bidirectional
    assert graph.conflict_count("DRAFTING:001", "TONE:002") == 1


def test_conflict_count_increments():
    graph = RuleGraph()
    graph.add_conflict("A", "B")
    graph.add_conflict("A", "B")
    graph.add_conflict("A", "B")
    assert graph.conflict_count("A", "B") == 3


def test_add_co_occurrence():
    graph = RuleGraph()
    graph.add_co_occurrence(["A", "B", "C"])
    assert graph.get_co_occurrences("A") == {"B": 1, "C": 1}
    assert graph.get_co_occurrences("B") == {"A": 1, "C": 1}


def test_no_conflict_returns_false():
    graph = RuleGraph()
    assert graph.has_conflict("A", "B") is False
    assert graph.conflict_count("A", "B") == 0


def test_get_conflicts_empty():
    graph = RuleGraph()
    assert graph.get_conflicts("nonexistent") == {}


def test_save_and_load(tmp_path: Path):
    path = tmp_path / "rule_graph.json"
    graph = RuleGraph(path)
    graph.add_conflict("A", "B")
    graph.add_co_occurrence(["A", "C", "D"])
    graph.save()

    loaded = RuleGraph(path)
    assert loaded.has_conflict("A", "B")
    assert loaded.get_co_occurrences("A") == {"C": 1, "D": 1}


def test_node_and_edge_counts():
    graph = RuleGraph()
    graph.add_conflict("A", "B")
    graph.add_co_occurrence(["A", "C"])
    assert graph.node_count == 3
    assert graph.edge_count == 2  # 1 conflict + 1 co-occurrence


def test_handles_corrupt_file(tmp_path: Path):
    path = tmp_path / "rule_graph.json"
    path.write_text("not json", encoding="utf-8")
    graph = RuleGraph(path)
    assert graph.node_count == 0  # Gracefully handles corruption
