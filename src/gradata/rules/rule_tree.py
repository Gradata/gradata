"""
Hierarchical Rule Tree — organize rules as Rosch category -> domain -> task_type.
================================================================================
Provides tree-based retrieval with task-type fast-path index. Rules at deeper
levels (more specific) are preferred over broader parent rules via tiebreaker.

Usage:
    tree = RuleTree(lessons)
    rules = tree.get_rules_for_context("email_draft", "sales", max_rules=5)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata._types import Lesson

_log = logging.getLogger(__name__)

__all__ = ["RuleTree", "build_path"]


def build_path(category: str, domain: str, task_type: str) -> str:
    """Build a tree path from category/domain/task_type, skipping empty segments.

    Category is uppercased. Domain and task_type are lowercased.
    Trailing slashes are stripped.

    Examples:
        build_path("TONE", "sales", "email_draft") -> "TONE/sales/email_draft"
        build_path("TONE", "sales", "") -> "TONE/sales"
        build_path("TONE", "", "") -> "TONE"
    """
    segments = []
    if category:
        segments.append(category.upper())
    if domain:
        segments.append(domain.lower())
    if task_type:
        segments.append(task_type.lower())
    return "/".join(segments)


def _parent_path(path: str) -> str:
    """Return the parent path, or empty string if at root."""
    parts = path.rsplit("/", 1)
    return parts[0] if len(parts) > 1 else ""


def _depth(path: str) -> int:
    """Return the depth of a path (number of segments - 1)."""
    if not path:
        return -1
    return path.count("/")


class RuleTree:
    """Hierarchical tree of rules organized by path.

    Attributes:
        nodes: Dict mapping path -> list of lessons at that node.
        task_index: Dict mapping task_type -> set of paths containing rules for that task.
        _all_lessons: Flat list of all lessons (for fallback).
    """

    def __init__(self, lessons: list[Lesson]):
        self.nodes: dict[str, list[Lesson]] = defaultdict(list)
        self.task_index: dict[str, set[str]] = defaultdict(set)
        self._all_lessons = lessons
        self._secondary_index: dict[str, list[Lesson]] = defaultdict(list)

        for lesson in lessons:
            path = lesson.path
            if not path:
                # No path = flat fallback pool
                self.nodes["_flat"].append(lesson)
                continue

            self.nodes[path].append(lesson)

            # Build task-type index from the last segment
            parts = path.split("/")
            if len(parts) >= 3:
                task_type = parts[2]
                self.task_index[task_type].add(path)
            # Also index by domain for partial matches
            if len(parts) >= 2:
                domain = parts[1]
                self.task_index[f"_domain:{domain}"].add(path)

            # Build secondary category index
            for sec_cat in getattr(lesson, "secondary_categories", []):
                self._secondary_index[sec_cat.upper()].append(lesson)

    def get_rules_at(self, path: str) -> list[Lesson]:
        """Get rules at an exact path (no parent walk)."""
        return list(self.nodes.get(path, []))

    def get_rules_for_context(
        self,
        task_type: str,
        domain: str = "",
        *,
        category_filter: str = "",
        max_rules: int = 5,
    ) -> list[Lesson]:
        """Get rules for a context, walking up the tree from leaves to trunk.

        1. Look up candidate paths via task_index
        2. Walk up each path collecting rules (specific -> general)
        3. Include secondary category matches
        4. Sort by composite score with specificity tiebreaker
        5. Return top max_rules
        """
        candidates: list[tuple[int, Lesson]] = []  # (depth, lesson)

        # 1. Fast-path: get paths from task index
        paths = set(self.task_index.get(task_type, set()))

        # Also try domain-level paths
        if domain:
            paths |= self.task_index.get(f"_domain:{domain}", set())

        if not paths:
            # Fallback: use trunk-level (category) rules + flat pool
            for path, lessons in self.nodes.items():
                if "/" not in path and path != "_flat":  # trunk-level
                    for lesson in lessons:
                        candidates.append((_depth(path), lesson))
            for lesson in self.nodes.get("_flat", []):
                candidates.append((-1, lesson))
        else:
            # 2. Walk up each path collecting rules
            seen_ids: set[int] = set()
            for path in paths:
                node = path
                while node:
                    for lesson in self.nodes.get(node, []):
                        lid = id(lesson)
                        if lid not in seen_ids:
                            seen_ids.add(lid)
                            candidates.append((_depth(node), lesson))
                    node = _parent_path(node)

        # 3. Include secondary category matches
        if category_filter:
            for lesson in self._secondary_index.get(category_filter.upper(), []):
                if id(lesson) not in {id(c[1]) for c in candidates}:
                    candidates.append((_depth(lesson.path), lesson))

        # 4. Sort: higher confidence first, specificity as tiebreaker (deeper = better)
        candidates.sort(
            key=lambda pair: (
                -getattr(pair[1], "confidence", 0),  # primary: confidence desc
                -pair[0],  # tiebreaker: depth desc (more specific wins)
            )
        )

        return [lesson for _, lesson in candidates[:max_rules]]

    def get_tree_structure(self, prefix: str = "") -> dict:
        """Return the tree as a nested dict for browsing/export.

        Args:
            prefix: Only return subtree under this path. Empty = full tree.
        """
        result: dict = {}
        for path, lessons in sorted(self.nodes.items()):
            if path == "_flat":
                continue
            if prefix and not path.startswith(prefix):
                continue
            parts = path.split("/")
            node = result
            for part in parts:
                if part not in node:
                    node[part] = {"_rules": [], "_children": {}}
                node = node[part]["_children"] if part != parts[-1] else node[part]
            if isinstance(node, dict) and "_rules" in node:
                node["_rules"] = [
                    {
                        "description": l.description,
                        "confidence": l.confidence,
                        "state": l.state.value,
                        "path": l.path,
                    }
                    for l in lessons
                ]
        return result
