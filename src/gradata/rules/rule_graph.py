"""Rule graph — conflict and co-occurrence edges between lessons.

Lightweight adjacency list tracking relationships between rules:
- conflict: rules that contradict each other
- co_occurrence: rules that frequently fire together

Persisted as JSON in the brain directory.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)


class RuleGraph:
    """Lightweight graph of rule relationships."""

    def __init__(self, path: Path | None = None):
        self._path = path
        # edges[rule_id] = {"conflicts": {other_id: count}, "co_occurs": {other_id: count}}
        self._edges: dict[str, dict[str, dict[str, int]]] = {}
        if path and path.is_file():
            try:
                self._edges = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                _log.debug("Could not load rule graph from %s", path)

    def add_conflict(self, rule_a: str, rule_b: str) -> None:
        """Record a conflict between two rules."""
        self._ensure_node(rule_a)
        self._ensure_node(rule_b)
        self._edges[rule_a]["conflicts"][rule_b] = (
            self._edges[rule_a]["conflicts"].get(rule_b, 0) + 1
        )
        self._edges[rule_b]["conflicts"][rule_a] = (
            self._edges[rule_b]["conflicts"].get(rule_a, 0) + 1
        )

    def add_co_occurrence(self, rule_ids: list[str]) -> None:
        """Record that these rules fired together in a session."""
        for i, a in enumerate(rule_ids):
            self._ensure_node(a)
            for b in rule_ids[i + 1 :]:
                self._ensure_node(b)
                self._edges[a]["co_occurs"][b] = (
                    self._edges[a]["co_occurs"].get(b, 0) + 1
                )
                self._edges[b]["co_occurs"][a] = (
                    self._edges[b]["co_occurs"].get(a, 0) + 1
                )

    def get_conflicts(self, rule_id: str) -> dict[str, int]:
        """Get all rules that conflict with this one. Returns {rule_id: count}."""
        return dict(self._edges.get(rule_id, {}).get("conflicts", {}))

    def get_co_occurrences(self, rule_id: str) -> dict[str, int]:
        """Get all rules that co-occur with this one. Returns {rule_id: count}."""
        return dict(self._edges.get(rule_id, {}).get("co_occurs", {}))

    def has_conflict(self, rule_a: str, rule_b: str) -> bool:
        """Check if two rules have ever conflicted."""
        return rule_b in self._edges.get(rule_a, {}).get("conflicts", {})

    def conflict_count(self, rule_a: str, rule_b: str) -> int:
        """Number of times two rules have conflicted."""
        return self._edges.get(rule_a, {}).get("conflicts", {}).get(rule_b, 0)

    def save(self) -> None:
        """Persist graph to disk."""
        if self._path:
            self._path.write_text(
                json.dumps(self._edges, indent=2), encoding="utf-8"
            )

    def _ensure_node(self, rule_id: str) -> None:
        if rule_id not in self._edges:
            self._edges[rule_id] = {"conflicts": {}, "co_occurs": {}}

    @property
    def node_count(self) -> int:
        return len(self._edges)

    @property
    def edge_count(self) -> int:
        count = 0
        for node in self._edges.values():
            count += len(node.get("conflicts", {}))
            count += len(node.get("co_occurs", {}))
        return count // 2  # Each edge counted twice
