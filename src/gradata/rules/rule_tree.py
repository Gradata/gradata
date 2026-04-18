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
    from .._types import Lesson

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

    # ── Auto-Climb ──────────────────────────────────────────────────────

    CLIMB_DWELL_SESSIONS = 5  # Min sessions at a level before climbing again
    CLIMB_MAX = 3  # Max total climbs per rule lifetime
    CONTRACT_MIN_CONTRADICTIONS = 2  # Contradictions needed to contract

    def evaluate_climb(
        self,
        lesson: Lesson,
        fired_in_paths: set[str],
        current_session: int,
    ) -> bool:
        """Check if a lesson should climb to its parent node.

        Climb trigger: rule fired successfully in 2+ sibling branches.
        Damping: 5-session dwell time, max 3 climbs lifetime.

        Returns True if climb happened, False otherwise. Mutates lesson in-place.
        """
        # Guard: climb cap
        if lesson.climb_count >= self.CLIMB_MAX:
            return False

        # Guard: dwell time
        if lesson.last_climb_session > 0:
            sessions_since = current_session - lesson.last_climb_session
            if sessions_since < self.CLIMB_DWELL_SESSIONS:
                return False

        # Guard: already at trunk (level 2, category-only path)
        if "/" not in lesson.path:
            return False

        # Check siblings: paths that share the same parent
        parent = _parent_path(lesson.path)
        sibling_fires = {
            p for p in fired_in_paths if _parent_path(p) == parent and p != lesson.path
        }

        if len(sibling_fires) < 1:  # need fires in at least 1 sibling (+ own = 2 total)
            return False

        # Climb: remove from current node, move to parent
        old_path = lesson.path
        if old_path in self.nodes:
            self.nodes[old_path] = [l for l in self.nodes[old_path] if l is not lesson]

        lesson.path = parent
        lesson.climb_count += 1
        lesson.last_climb_session = current_session
        lesson.tree_level = max(0, _depth(parent))

        self.nodes[parent].append(lesson)
        _log.info("Rule climbed: %s -> %s (climb #%d)", old_path, parent, lesson.climb_count)
        return True

    def evaluate_contract(
        self,
        lesson: Lesson,
        contradictions_at_level: int,
        current_session: int,
        original_task_type: str = "",
    ) -> bool:
        """Check if a climbed rule should contract back down.

        Contract trigger: 2+ contradictions at current level within recent sessions.
        Contracts down one level. Sets dwell cooldown.

        Returns True if contraction happened, False otherwise.
        """
        if contradictions_at_level < self.CONTRACT_MIN_CONTRADICTIONS:
            return False

        # Can't contract below level 0
        if lesson.tree_level <= 0:
            return False

        # Contract: move down one level
        old_path = lesson.path
        if old_path in self.nodes:
            self.nodes[old_path] = [l for l in self.nodes[old_path] if l is not lesson]

        # Reconstruct a child path using original_task_type or category default
        if original_task_type:
            new_path = f"{old_path}/{original_task_type}"
        else:
            new_path = f"{old_path}/_contracted"

        lesson.path = new_path
        lesson.tree_level = max(0, lesson.tree_level - 1)
        lesson.last_climb_session = current_session  # cooldown applies after contraction too

        self.nodes[new_path].append(lesson)
        _log.info("Rule contracted: %s -> %s", old_path, new_path)
        return True

    # ── Consolidation ───────────────────────────────────────────────────

    def consolidate(
        self,
        session_fires: dict[str, list[Lesson]],
        current_session: int,
        session_contradictions: dict[str, int] | None = None,
    ) -> dict[str, int]:
        """Post-session consolidation: evaluate climbs and contractions.

        Called by the session_close hook as a background task.

        Args:
            session_fires: Dict mapping path -> list of lessons that fired at that path
            current_session: Current session number
            session_contradictions: Dict mapping path -> count of contradictions

        Returns:
            Summary: {"climbed": N, "contracted": N, "unchanged": N}
        """
        climbed = 0
        contracted = 0
        unchanged = 0

        # Evaluate climbs: for each lesson, check if it fired in sibling paths
        evaluated: set[int] = set()
        for _path, lessons in session_fires.items():
            for lesson in lessons:
                lid = id(lesson)
                if lid in evaluated:
                    continue
                evaluated.add(lid)

                # Collect all paths this lesson fired in
                fired_in = {p for p, ls in session_fires.items() if lesson in ls}

                if self.evaluate_climb(lesson, fired_in, current_session):
                    climbed += 1
                else:
                    unchanged += 1

        # Evaluate contractions
        if session_contradictions:
            for path, count in session_contradictions.items():
                for lesson in list(self.nodes.get(path, [])):
                    if count >= self.CONTRACT_MIN_CONTRADICTIONS and self.evaluate_contract(
                        lesson, count, current_session
                    ):
                        contracted += 1

        return {"climbed": climbed, "contracted": contracted, "unchanged": unchanged}


# ── Export Functions ──────────────────────────────────────────────────


def export_tree_json(tree: RuleTree, output_path: Path) -> None:
    """Export the tree as a JSON file."""
    import json

    structure = tree.get_tree_structure()
    output_path.write_text(json.dumps(structure, indent=2, default=str), encoding="utf-8")


def export_tree_obsidian(tree: RuleTree, vault_path: Path) -> None:
    """Export the tree as an Obsidian vault (folders + .md files).

    Each rule becomes a .md file with YAML frontmatter.
    Each tree node becomes a folder with an _index.md.
    """
    vault_path = Path(vault_path)
    vault_path.mkdir(parents=True, exist_ok=True)

    for path, lessons in sorted(tree.nodes.items()):
        if path == "_flat":
            continue

        # Create folder
        folder = vault_path / path.replace("/", "/")
        folder.mkdir(parents=True, exist_ok=True)

        # Write each rule as a .md file
        for lesson in lessons:
            slug = lesson.description[:40].replace(" ", "_").replace("/", "-")
            slug = "".join(c for c in slug if c.isalnum() or c in "_-")
            filename = f"{slug}.md"

            content = f"""---
id: {lesson.category}_{hash(lesson.description) % 10000:04d}
confidence: {lesson.confidence}
state: {lesson.state.value}
path: {lesson.path}
fires: {lesson.fire_count}
misfires: {lesson.misfire_count}
climb_count: {lesson.climb_count}
tree_level: {lesson.tree_level}
---

{lesson.description}
"""
            if lesson.example_draft and lesson.example_corrected:
                content += f"""
## Evidence
- Draft: {lesson.example_draft}
- Corrected: {lesson.example_corrected}
"""
            if lesson.secondary_categories:
                content += "\n## Also applies to\n"
                for cat in lesson.secondary_categories:
                    content += f"- [[{cat}]]\n"

            (folder / filename).write_text(content, encoding="utf-8")

        # Write _index.md for the folder
        avg_conf = sum(l.confidence for l in lessons) / len(lessons) if lessons else 0
        index_content = f"""---
path: {path}
rule_count: {len(lessons)}
avg_confidence: {avg_conf:.2f}
---

# {path.split("/")[-1]}

{len(lessons)} rules at this level.
"""
        (folder / "_index.md").write_text(index_content, encoding="utf-8")
