# Hierarchical Rule Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hierarchical tree structure to the Gradata rule engine — Rosch category → domain → task_type → rule — with auto-climb, fast-path retrieval, background consolidation agent, and export API.

**Architecture:** Add `path` and tree metadata fields to the Lesson dataclass. Create `rule_tree.py` as the tree engine (build, query, climb, contract). Modify `rule_engine.py` to use tree-based retrieval with task-type index fallback. Add background consolidation to `session_close` hook. Export API on Brain class.

**Tech Stack:** Python 3.12, SQLite (system.db), existing Gradata SDK patterns

---

## File Structure

| File | Purpose | Action |
|------|---------|--------|
| `src/gradata/rules/rule_tree.py` | RuleTree class: build, query, climb, contract, index | Create |
| `tests/test_rule_tree.py` | Tree operations tests | Create |
| `src/gradata/_types.py` | Add `path`, `secondary_categories`, `climb_count`, `last_climb_session` to Lesson | Modify |
| `src/gradata/_migrations.py` | Add migration for path-related columns | Modify |
| `src/gradata/enhancements/self_improvement.py` | Place new rules at correct tree path | Modify |
| `src/gradata/rules/rule_engine.py` | Tree-based retrieval in `apply_rules` | Modify |
| `src/gradata/brain.py` | Add `browse()` and `export()` methods | Modify |
| `src/gradata/_export_brain.py` | Add Obsidian/JSON tree export formatters | Modify |

---

## Task 1: Add Tree Fields to Lesson Dataclass

**Files:**
- Modify: `src/gradata/_types.py:138-170`
- Test: `tests/test_rule_tree.py` (new)

- [ ] **Step 1: Write the failing test**

```python
"""Tests for hierarchical rule tree."""
import pytest
from gradata._types import Lesson, LessonState


class TestLessonTreeFields:
    def test_lesson_has_path_field(self):
        lesson = Lesson(
            date="2026-04-11", state=LessonState.INSTINCT,
            confidence=0.50, category="TONE",
            description="Be casual with VPs",
        )
        assert lesson.path == ""

    def test_lesson_has_secondary_categories(self):
        lesson = Lesson(
            date="2026-04-11", state=LessonState.INSTINCT,
            confidence=0.50, category="TONE",
            description="No em dashes",
            secondary_categories=["FORMAT"],
        )
        assert lesson.secondary_categories == ["FORMAT"]

    def test_lesson_has_climb_tracking(self):
        lesson = Lesson(
            date="2026-04-11", state=LessonState.INSTINCT,
            confidence=0.50, category="TONE",
            description="Be direct",
        )
        assert lesson.climb_count == 0
        assert lesson.last_climb_session == 0
        assert lesson.tree_level == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/test_rule_tree.py::TestLessonTreeFields -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'path'` (or similar)

- [ ] **Step 3: Add fields to Lesson dataclass**

In `src/gradata/_types.py`, add these fields after `metadata` (line ~169):

```python
    # ── Hierarchical Rule Tree fields ──────────────────────────────────
    path: str = ""  # Tree path: "CATEGORY/domain/task_type"
    secondary_categories: list[str] = field(default_factory=list)  # Multi-category rules
    climb_count: int = 0  # Total times this rule climbed (max 3)
    last_climb_session: int = 0  # Session when last climb occurred
    tree_level: int = 0  # Current depth: 0=leaf, 1=branch, 2=trunk
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/test_rule_tree.py::TestLessonTreeFields -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/gradata/_types.py tests/test_rule_tree.py
git commit -m "$(cat <<'EOF'
feat(rule-tree): add path, secondary_categories, climb fields to Lesson

Co-Authored-By: Gradata <noreply@gradata.ai>
EOF
)"
```

---

## Task 2: Build RuleTree Core — Build and Query

**Files:**
- Create: `src/gradata/rules/rule_tree.py`
- Test: `tests/test_rule_tree.py` (append)

- [ ] **Step 1: Write failing tests for tree build and query**

Append to `tests/test_rule_tree.py`:

```python
from gradata.rules.rule_tree import RuleTree, build_path


class TestBuildPath:
    def test_full_path(self):
        assert build_path("TONE", "sales", "email_draft") == "TONE/sales/email_draft"

    def test_no_task_type(self):
        assert build_path("TONE", "sales", "") == "TONE/sales"

    def test_no_domain(self):
        assert build_path("TONE", "", "") == "TONE"

    def test_empty_all(self):
        assert build_path("", "", "") == ""

    def test_normalizes_lowercase(self):
        assert build_path("Tone", "Sales", "Email_Draft") == "TONE/sales/email_draft"


class TestRuleTreeBuild:
    def _make_lessons(self):
        return [
            Lesson(date="2026-01-01", state=LessonState.RULE, confidence=0.95,
                   category="TONE", description="Be casual",
                   path="TONE/sales/email_draft"),
            Lesson(date="2026-01-02", state=LessonState.PATTERN, confidence=0.70,
                   category="TONE", description="Match energy",
                   path="TONE/sales/demo_prep"),
            Lesson(date="2026-01-03", state=LessonState.RULE, confidence=0.92,
                   category="ACCURACY", description="Cite sources",
                   path="ACCURACY/sales/email_draft"),
            Lesson(date="2026-01-04", state=LessonState.RULE, confidence=0.91,
                   category="TONE", description="Be direct everywhere",
                   path="TONE/sales"),  # climbed to branch level
        ]

    def test_build_tree(self):
        tree = RuleTree(self._make_lessons())
        assert len(tree.nodes) > 0

    def test_query_by_path(self):
        tree = RuleTree(self._make_lessons())
        rules = tree.get_rules_at("TONE/sales/email_draft")
        assert len(rules) == 1
        assert rules[0].description == "Be casual"

    def test_query_walks_up(self):
        tree = RuleTree(self._make_lessons())
        # Query leaf — should get leaf rule + parent rule
        rules = tree.get_rules_for_context("email_draft", "sales")
        descriptions = [r.description for r in rules]
        assert "Be casual" in descriptions  # leaf
        assert "Be direct everywhere" in descriptions  # parent (climbed)

    def test_query_unknown_task_falls_back(self):
        tree = RuleTree(self._make_lessons())
        rules = tree.get_rules_for_context("unknown_task", "sales")
        # Should still find branch-level and trunk-level rules
        descriptions = [r.description for r in rules]
        assert "Be direct everywhere" in descriptions

    def test_task_index_built(self):
        tree = RuleTree(self._make_lessons())
        assert "email_draft" in tree.task_index
        assert "demo_prep" in tree.task_index


class TestRuleTreeSecondaryCategories:
    def test_secondary_category_surfaces(self):
        lessons = [
            Lesson(date="2026-01-01", state=LessonState.RULE, confidence=0.90,
                   category="TONE", description="No em dashes",
                   path="TONE/sales/email_draft",
                   secondary_categories=["FORMAT"]),
        ]
        tree = RuleTree(lessons)
        # Query for FORMAT — should find the rule via secondary
        rules = tree.get_rules_for_context("email_draft", "sales", category_filter="FORMAT")
        assert len(rules) == 1
        assert rules[0].description == "No em dashes"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/test_rule_tree.py -v -k "not Climb"`
Expected: FAIL — `ModuleNotFoundError: No module named 'gradata.rules.rule_tree'`

- [ ] **Step 3: Implement rule_tree.py**

Create `src/gradata/rules/rule_tree.py`:

```python
"""
Hierarchical Rule Tree — organize rules as Rosch category → domain → task_type.
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
        2. Walk up each path collecting rules (specific → general)
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
                if id(lesson) not in {id(l) for _, l in candidates}:
                    candidates.append((_depth(lesson.path), lesson))

        # 4. Sort: higher confidence first, specificity as tiebreaker (deeper = better)
        candidates.sort(key=lambda pair: (
            -getattr(pair[1], "confidence", 0),  # primary: confidence desc
            -pair[0],  # tiebreaker: depth desc (more specific wins)
        ))

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
                    {"description": l.description, "confidence": l.confidence,
                     "state": l.state.value, "path": l.path}
                    for l in lessons
                ]
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/test_rule_tree.py -v -k "not Climb"`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/gradata/rules/rule_tree.py tests/test_rule_tree.py
git commit -m "$(cat <<'EOF'
feat(rule-tree): RuleTree core — build, query, task-type index, secondary categories

Co-Authored-By: Gradata <noreply@gradata.ai>
EOF
)"
```

---

## Task 3: Auto-Climb and Anti-Climb with Damping

**Files:**
- Modify: `src/gradata/rules/rule_tree.py`
- Test: `tests/test_rule_tree.py` (append)

- [ ] **Step 1: Write failing tests for climb mechanics**

Append to `tests/test_rule_tree.py`:

```python
class TestAutoClimb:
    def test_climb_trigger_two_siblings(self):
        lesson = Lesson(
            date="2026-01-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Be concise",
            path="TONE/sales/email_draft", climb_count=0, last_climb_session=0,
        )
        tree = RuleTree([lesson])
        # Simulate fires in sibling branches
        fired_in = {"TONE/sales/email_draft", "TONE/sales/demo_prep"}
        result = tree.evaluate_climb(lesson, fired_in, current_session=10)
        assert result is True
        assert lesson.path == "TONE/sales"
        assert lesson.climb_count == 1
        assert lesson.tree_level == 1

    def test_climb_respects_dwell_time(self):
        lesson = Lesson(
            date="2026-01-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Be concise",
            path="TONE/sales", climb_count=1, last_climb_session=8, tree_level=1,
        )
        tree = RuleTree([lesson])
        fired_in = {"TONE/sales", "TONE/engineering"}
        # Session 10 is only 2 sessions after last climb (need 5)
        result = tree.evaluate_climb(lesson, fired_in, current_session=10)
        assert result is False
        assert lesson.path == "TONE/sales"  # unchanged

    def test_climb_cap_at_three(self):
        lesson = Lesson(
            date="2026-01-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Be concise",
            path="TONE/sales", climb_count=3, last_climb_session=1, tree_level=1,
        )
        tree = RuleTree([lesson])
        fired_in = {"TONE/sales", "TONE/engineering"}
        result = tree.evaluate_climb(lesson, fired_in, current_session=20)
        assert result is False  # cap reached

    def test_anti_climb_contracts(self):
        lesson = Lesson(
            date="2026-01-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Be concise",
            path="TONE/sales", climb_count=1, tree_level=1,
        )
        tree = RuleTree([lesson])
        result = tree.evaluate_contract(lesson, contradictions_at_level=2, current_session=15)
        assert result is True
        assert lesson.path == "TONE/sales/email_draft" or lesson.tree_level == 0

    def test_anti_climb_needs_two_contradictions(self):
        lesson = Lesson(
            date="2026-01-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Be concise",
            path="TONE/sales", climb_count=1, tree_level=1,
        )
        tree = RuleTree([lesson])
        result = tree.evaluate_contract(lesson, contradictions_at_level=1, current_session=15)
        assert result is False  # need 2+
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/test_rule_tree.py::TestAutoClimb -v`
Expected: FAIL — `AttributeError: 'RuleTree' has no attribute 'evaluate_climb'`

- [ ] **Step 3: Add climb/contract methods to RuleTree**

Add to `src/gradata/rules/rule_tree.py`:

```python
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
        sibling_fires = {p for p in fired_in_paths if _parent_path(p) == parent and p != lesson.path}

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/test_rule_tree.py::TestAutoClimb -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/gradata/rules/rule_tree.py tests/test_rule_tree.py
git commit -m "$(cat <<'EOF'
feat(rule-tree): auto-climb + anti-climb with oscillation damping

5-session dwell, 3-climb cap, 2-contradiction contract threshold.

Co-Authored-By: Gradata <noreply@gradata.ai>
EOF
)"
```

---

## Task 4: Add Migration for Path Column

**Files:**
- Modify: `src/gradata/_migrations.py`
- Modify: `src/gradata/enhancements/self_improvement.py` (path in `parse_lessons` and `format_lesson`)
- Test: Run existing tests to ensure backward compat

- [ ] **Step 1: Add migration SQL**

In `src/gradata/_migrations.py`, append to `_MIGRATIONS` list:

```python
    # Hierarchical rule tree: path column for tree organization
    "ALTER TABLE lesson_transitions ADD COLUMN path TEXT DEFAULT ''",
```

- [ ] **Step 2: Add path serialization to lesson parser**

In `src/gradata/enhancements/self_improvement.py`, in the `parse_lessons` function's metadata-line loop (around line 333-389), add handling for the `Path:` line:

```python
            elif meta_line.startswith("Path:"):
                path = meta_line[len("Path:"):].strip()
```

And add `path` variable initialization before the loop (around line 328):

```python
        path = ""
```

And include `path=path` in the Lesson constructor call (around line 391-405).

In `format_lesson()`, add the Path line to the metadata output.

- [ ] **Step 3: Add path assignment in `_create_lesson`**

In `self_improvement.py`, where new lessons are created, add path computation:

```python
from gradata.rules.rule_tree import build_path

# In _create_lesson or wherever Lesson() is constructed:
path = build_path(category, scope.domain if scope else "", scope.task_type if scope else "")
```

- [ ] **Step 4: Run full test suite**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/ -x -q --tb=short`
Expected: 1934+ pass, 0 fail

- [ ] **Step 5: Commit**

```bash
git add src/gradata/_migrations.py src/gradata/enhancements/self_improvement.py
git commit -m "$(cat <<'EOF'
feat(rule-tree): migration + path serialization in lesson parser

New lessons get tree path from category/domain/task_type.
Existing lessons backfill via migration.

Co-Authored-By: Gradata <noreply@gradata.ai>
EOF
)"
```

---

## Task 5: Wire Tree-Based Retrieval into Rule Engine

**Files:**
- Modify: `src/gradata/rules/rule_engine.py`
- Test: Run existing `tests/test_rule_engine_v2.py`

- [ ] **Step 1: Write failing test for tree retrieval**

Append to `tests/test_rule_tree.py`:

```python
class TestTreeRetrieval:
    def test_tree_retrieval_prefers_specific(self):
        """More specific (deeper) rules win tiebreaks over broader rules."""
        lessons = [
            Lesson(date="2026-01-01", state=LessonState.RULE, confidence=0.90,
                   category="TONE", description="General tone rule",
                   path="TONE"),
            Lesson(date="2026-01-02", state=LessonState.RULE, confidence=0.90,
                   category="TONE", description="Sales-specific tone",
                   path="TONE/sales/email_draft"),
        ]
        tree = RuleTree(lessons)
        rules = tree.get_rules_for_context("email_draft", "sales", max_rules=2)
        # Same confidence — specific should come first
        assert rules[0].description == "Sales-specific tone"

    def test_tree_retrieval_confidence_beats_specificity(self):
        """Higher confidence beats deeper specificity."""
        lessons = [
            Lesson(date="2026-01-01", state=LessonState.RULE, confidence=0.95,
                   category="TONE", description="High confidence broad",
                   path="TONE"),
            Lesson(date="2026-01-02", state=LessonState.PATTERN, confidence=0.65,
                   category="TONE", description="Low confidence specific",
                   path="TONE/sales/email_draft"),
        ]
        tree = RuleTree(lessons)
        rules = tree.get_rules_for_context("email_draft", "sales", max_rules=2)
        assert rules[0].description == "High confidence broad"
```

- [ ] **Step 2: Run test to verify passes** (should already pass from Task 2's implementation)

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/test_rule_tree.py::TestTreeRetrieval -v`

- [ ] **Step 3: Add tree initialization to rule_engine.py**

In `src/gradata/rules/rule_engine.py`, add a function that builds a RuleTree from lessons and uses it for retrieval:

```python
from gradata.rules.rule_tree import RuleTree

def apply_rules_with_tree(
    lessons: list[Lesson],
    scope: RuleScope,
    *,
    max_rules: int = 5,
    event_bus: EventBus | None = None,
    rule_graph: RuleGraph | None = None,
) -> list[AppliedRule]:
    """Apply rules using hierarchical tree retrieval.

    Falls back to flat scoring if no lessons have paths.
    """
    # Check if any lessons have paths
    has_paths = any(l.path for l in lessons)
    if not has_paths:
        # Fallback: use existing flat apply_rules
        return apply_rules(lessons, scope, max_rules=max_rules,
                          event_bus=event_bus, rule_graph=rule_graph)

    tree = RuleTree(lessons)
    candidates = tree.get_rules_for_context(
        task_type=scope.task_type,
        domain=scope.domain,
        max_rules=max_rules * 2,  # get extra, let formatting trim
    )

    # Format as AppliedRule objects (reuse existing formatting)
    applied = []
    for lesson in candidates[:max_rules]:
        rule_id = f"{lesson.category}:{hash(lesson.description) % 10000:04d}"
        instruction = f"<rule confidence=\"{lesson.confidence:.2f}\">{lesson.category}: {lesson.description}</rule>"
        applied.append(AppliedRule(
            rule_id=rule_id,
            lesson=lesson,
            relevance=1.0,  # tree already filtered for relevance
            instruction=instruction,
        ))
    return applied
```

- [ ] **Step 4: Run full test suite**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/ -x -q --tb=short`
Expected: All pass — this is additive, doesn't change existing `apply_rules`

- [ ] **Step 5: Commit**

```bash
git add src/gradata/rules/rule_engine.py tests/test_rule_tree.py
git commit -m "$(cat <<'EOF'
feat(rule-tree): wire tree retrieval into rule_engine (opt-in, falls back to flat)

Co-Authored-By: Gradata <noreply@gradata.ai>
EOF
)"
```

---

## Task 6: Browse and Export API on Brain

**Files:**
- Modify: `src/gradata/brain.py`
- Modify: `src/gradata/_export_brain.py`
- Test: `tests/test_rule_tree.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_rule_tree.py`:

```python
import json
import tempfile
from pathlib import Path


class TestTreeExport:
    def _make_lessons(self):
        return [
            Lesson(date="2026-01-01", state=LessonState.RULE, confidence=0.95,
                   category="TONE", description="Be casual with VPs",
                   path="TONE/sales/email_draft"),
            Lesson(date="2026-01-02", state=LessonState.PATTERN, confidence=0.70,
                   category="ACCURACY", description="Always cite sources",
                   path="ACCURACY/sales/email_draft"),
        ]

    def test_export_json(self, tmp_path):
        from gradata.rules.rule_tree import RuleTree, export_tree_json
        tree = RuleTree(self._make_lessons())
        output = tmp_path / "tree.json"
        export_tree_json(tree, output)
        data = json.loads(output.read_text())
        assert "TONE" in data
        assert "ACCURACY" in data

    def test_export_obsidian(self, tmp_path):
        from gradata.rules.rule_tree import RuleTree, export_tree_obsidian
        tree = RuleTree(self._make_lessons())
        vault = tmp_path / "vault"
        export_tree_obsidian(tree, vault)
        # Check folder structure
        assert (vault / "TONE" / "sales" / "email_draft").is_dir()
        # Check rule file exists
        md_files = list((vault / "TONE" / "sales" / "email_draft").glob("*.md"))
        assert len(md_files) >= 1
        # Check frontmatter
        content = md_files[0].read_text()
        assert "confidence:" in content
        assert "Be casual with VPs" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/test_rule_tree.py::TestTreeExport -v`
Expected: FAIL — `ImportError: cannot import name 'export_tree_json'`

- [ ] **Step 3: Add export functions to rule_tree.py**

Append to `src/gradata/rules/rule_tree.py`:

```python
# ── Export Functions ──────────────────────────────────────────────────


def export_tree_json(tree: RuleTree, output_path: Path) -> None:
    """Export the tree as a JSON file."""
    import json
    from pathlib import Path as _Path

    output_path = _Path(output_path)
    structure = tree.get_tree_structure()
    output_path.write_text(json.dumps(structure, indent=2, default=str), encoding="utf-8")


def export_tree_obsidian(tree: RuleTree, vault_path: Path) -> None:
    """Export the tree as an Obsidian vault (folders + .md files).

    Each rule becomes a .md file with YAML frontmatter.
    Each tree node becomes a folder with an _index.md.
    """
    from pathlib import Path as _Path

    vault_path = _Path(vault_path)
    vault_path.mkdir(parents=True, exist_ok=True)

    for path, lessons in sorted(tree.nodes.items()):
        if path == "_flat":
            continue

        # Create folder
        folder = vault_path / path.replace("/", "/")
        folder.mkdir(parents=True, exist_ok=True)

        # Write each rule as a .md file
        for i, lesson in enumerate(lessons):
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
                content += f"\n## Also applies to\n"
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

# {path.split('/')[-1]}

{len(lessons)} rules at this level.
"""
        (folder / "_index.md").write_text(index_content, encoding="utf-8")
```

- [ ] **Step 4: Run tests**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/test_rule_tree.py::TestTreeExport -v`
Expected: PASS

- [ ] **Step 5: Add browse() and export() to Brain class**

In `src/gradata/brain.py`, add methods:

```python
    def browse(self, path: str = "") -> dict:
        """Browse the hierarchical rule tree.

        Args:
            path: Subtree path to browse. Empty = full tree.

        Returns:
            Nested dict representing the tree structure.
        """
        from gradata.rules.rule_tree import RuleTree
        lessons = self._load_lessons()
        tree = RuleTree(lessons)
        return tree.get_tree_structure(prefix=path)

    def export(self, format: str = "json", path: str = "./export") -> Path:
        """Export the brain's rule tree to an external format.

        Args:
            format: One of "json", "obsidian", "markdown"
            path: Output path (file for json, directory for obsidian/markdown)

        Returns:
            Path to the exported file/directory.
        """
        from gradata.rules.rule_tree import RuleTree, export_tree_json, export_tree_obsidian
        lessons = self._load_lessons()
        tree = RuleTree(lessons)
        output = Path(path)

        if format == "json":
            export_tree_json(tree, output)
        elif format == "obsidian":
            export_tree_obsidian(tree, output)
        else:
            export_tree_json(tree, output)  # default to JSON

        return output
```

- [ ] **Step 6: Run full test suite**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/ -x -q --tb=short`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add src/gradata/rules/rule_tree.py src/gradata/brain.py tests/test_rule_tree.py
git commit -m "$(cat <<'EOF'
feat(rule-tree): browse() + export() API — JSON and Obsidian vault export

Co-Authored-By: Gradata <noreply@gradata.ai>
EOF
)"
```

---

## Task 7: Background Consolidation Agent (REM Sleep Pattern)

**Files:**
- Modify: `src/gradata/hooks/session_close.py`
- Modify: `src/gradata/rules/rule_tree.py` (add `consolidate()`)
- Test: `tests/test_rule_tree.py` (append)

- [ ] **Step 1: Write failing test for consolidation**

Append to `tests/test_rule_tree.py`:

```python
class TestConsolidation:
    def test_consolidate_evaluates_climbs(self):
        """After a session, consolidation checks which rules should climb."""
        lessons = [
            Lesson(date="2026-01-01", state=LessonState.RULE, confidence=0.92,
                   category="TONE", description="Be concise",
                   path="TONE/sales/email_draft", climb_count=0, last_climb_session=0),
        ]
        tree = RuleTree(lessons)
        # Simulate: rule fired in email_draft (home) + demo_prep (sibling)
        session_fires = {
            "TONE/sales/email_draft": [lessons[0]],
            "TONE/sales/demo_prep": [lessons[0]],
        }
        results = tree.consolidate(session_fires, current_session=10)
        assert results["climbed"] == 1

    def test_consolidate_no_action_when_stable(self):
        lessons = [
            Lesson(date="2026-01-01", state=LessonState.RULE, confidence=0.92,
                   category="TONE", description="Be concise",
                   path="TONE/sales/email_draft", climb_count=0, last_climb_session=0),
        ]
        tree = RuleTree(lessons)
        # Only fired in home path — no climb
        session_fires = {
            "TONE/sales/email_draft": [lessons[0]],
        }
        results = tree.consolidate(session_fires, current_session=10)
        assert results["climbed"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/test_rule_tree.py::TestConsolidation -v`
Expected: FAIL — `AttributeError: 'RuleTree' has no attribute 'consolidate'`

- [ ] **Step 3: Add consolidate() method**

Add to `RuleTree` in `rule_tree.py`:

```python
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
        for path, lessons in session_fires.items():
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
                    if count >= self.CONTRACT_MIN_CONTRADICTIONS:
                        if self.evaluate_contract(lesson, count, current_session):
                            contracted += 1

        return {"climbed": climbed, "contracted": contracted, "unchanged": unchanged}
```

- [ ] **Step 4: Wire into session_close hook**

Read `src/gradata/hooks/session_close.py` and add a call to tree consolidation at the end of the session close process. The hook should:

1. Load current lessons
2. Build RuleTree
3. Collect session fires from events (query events table for current session's RULE_FIRED events)
4. Call `tree.consolidate()`
5. Save updated lesson paths back to lessons.md

This should be non-blocking — if the tree has no paths, skip consolidation.

- [ ] **Step 5: Run tests**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/test_rule_tree.py -v`
Expected: All PASS

- [ ] **Step 6: Run full suite**

Run: `cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && python -m pytest tests/ -x -q --tb=short`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add src/gradata/rules/rule_tree.py src/gradata/hooks/session_close.py tests/test_rule_tree.py
git commit -m "$(cat <<'EOF'
feat(rule-tree): background consolidation agent — post-session climb/contract evaluation

REM sleep pattern: after each session, evaluate which rules should
climb (proven across siblings) or contract (contradicted at level).

Co-Authored-By: Gradata <noreply@gradata.ai>
EOF
)"
```
