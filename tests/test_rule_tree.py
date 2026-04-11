"""Tests for hierarchical rule tree."""

import pytest
from gradata._types import Lesson, LessonState


class TestLessonTreeFields:
    def test_lesson_has_path_field(self):
        lesson = Lesson(
            date="2026-04-11",
            state=LessonState.INSTINCT,
            confidence=0.50,
            category="TONE",
            description="Be casual with VPs",
        )
        assert lesson.path == ""

    def test_lesson_has_secondary_categories(self):
        lesson = Lesson(
            date="2026-04-11",
            state=LessonState.INSTINCT,
            confidence=0.50,
            category="TONE",
            description="No em dashes",
            secondary_categories=["FORMAT"],
        )
        assert lesson.secondary_categories == ["FORMAT"]

    def test_lesson_has_climb_tracking(self):
        lesson = Lesson(
            date="2026-04-11",
            state=LessonState.INSTINCT,
            confidence=0.50,
            category="TONE",
            description="Be direct",
        )
        assert lesson.climb_count == 0
        assert lesson.last_climb_session == 0
        assert lesson.tree_level == 0


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
            Lesson(
                date="2026-01-01",
                state=LessonState.RULE,
                confidence=0.95,
                category="TONE",
                description="Be casual",
                path="TONE/sales/email_draft",
            ),
            Lesson(
                date="2026-01-02",
                state=LessonState.PATTERN,
                confidence=0.70,
                category="TONE",
                description="Match energy",
                path="TONE/sales/demo_prep",
            ),
            Lesson(
                date="2026-01-03",
                state=LessonState.RULE,
                confidence=0.92,
                category="ACCURACY",
                description="Cite sources",
                path="ACCURACY/sales/email_draft",
            ),
            Lesson(
                date="2026-01-04",
                state=LessonState.RULE,
                confidence=0.91,
                category="TONE",
                description="Be direct everywhere",
                path="TONE/sales",
            ),  # climbed to branch level
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
            Lesson(
                date="2026-01-01",
                state=LessonState.RULE,
                confidence=0.90,
                category="TONE",
                description="No em dashes",
                path="TONE/sales/email_draft",
                secondary_categories=["FORMAT"],
            ),
        ]
        tree = RuleTree(lessons)
        # Query for FORMAT — should find the rule via secondary
        rules = tree.get_rules_for_context("email_draft", "sales", category_filter="FORMAT")
        assert len(rules) >= 1
        assert rules[0].description == "No em dashes"


class TestAutoClimb:
    def test_climb_trigger_two_siblings(self):
        lesson = Lesson(
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.92,
            category="TONE",
            description="Be concise",
            path="TONE/sales/email_draft",
            climb_count=0,
            last_climb_session=0,
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
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.92,
            category="TONE",
            description="Be concise",
            path="TONE/sales",
            climb_count=1,
            last_climb_session=8,
            tree_level=1,
        )
        tree = RuleTree([lesson])
        fired_in = {"TONE/sales", "TONE/engineering"}
        # Session 10 is only 2 sessions after last climb (need 5)
        result = tree.evaluate_climb(lesson, fired_in, current_session=10)
        assert result is False
        assert lesson.path == "TONE/sales"  # unchanged

    def test_climb_cap_at_three(self):
        lesson = Lesson(
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.92,
            category="TONE",
            description="Be concise",
            path="TONE/sales",
            climb_count=3,
            last_climb_session=1,
            tree_level=1,
        )
        tree = RuleTree([lesson])
        fired_in = {"TONE/sales", "TONE/engineering"}
        result = tree.evaluate_climb(lesson, fired_in, current_session=20)
        assert result is False  # cap reached

    def test_anti_climb_contracts(self):
        lesson = Lesson(
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.92,
            category="TONE",
            description="Be concise",
            path="TONE/sales",
            climb_count=1,
            tree_level=1,
        )
        tree = RuleTree([lesson])
        result = tree.evaluate_contract(lesson, contradictions_at_level=2, current_session=15)
        assert result is True
        assert lesson.tree_level == 0

    def test_anti_climb_needs_two_contradictions(self):
        lesson = Lesson(
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.92,
            category="TONE",
            description="Be concise",
            path="TONE/sales",
            climb_count=1,
            tree_level=1,
        )
        tree = RuleTree([lesson])
        result = tree.evaluate_contract(lesson, contradictions_at_level=1, current_session=15)
        assert result is False  # need 2+


class TestTreeRetrieval:
    def test_tree_retrieval_prefers_specific(self):
        """More specific (deeper) rules win tiebreaks over broader rules."""
        lessons = [
            Lesson(
                date="2026-01-01",
                state=LessonState.RULE,
                confidence=0.90,
                category="TONE",
                description="General tone rule",
                path="TONE",
            ),
            Lesson(
                date="2026-01-02",
                state=LessonState.RULE,
                confidence=0.90,
                category="TONE",
                description="Sales-specific tone",
                path="TONE/sales/email_draft",
            ),
        ]
        tree = RuleTree(lessons)
        rules = tree.get_rules_for_context("email_draft", "sales", max_rules=2)
        # Same confidence — specific should come first
        assert rules[0].description == "Sales-specific tone"

    def test_tree_retrieval_confidence_beats_specificity(self):
        """Higher confidence beats deeper specificity."""
        lessons = [
            Lesson(
                date="2026-01-01",
                state=LessonState.RULE,
                confidence=0.95,
                category="TONE",
                description="High confidence broad",
                path="TONE",
            ),
            Lesson(
                date="2026-01-02",
                state=LessonState.PATTERN,
                confidence=0.65,
                category="TONE",
                description="Low confidence specific",
                path="TONE/sales/email_draft",
            ),
        ]
        tree = RuleTree(lessons)
        rules = tree.get_rules_for_context("email_draft", "sales", max_rules=2)
        assert rules[0].description == "High confidence broad"


import json
from pathlib import Path


class TestTreeExport:
    def _make_lessons(self):
        return [
            Lesson(
                date="2026-01-01",
                state=LessonState.RULE,
                confidence=0.95,
                category="TONE",
                description="Be casual with VPs",
                path="TONE/sales/email_draft",
            ),
            Lesson(
                date="2026-01-02",
                state=LessonState.PATTERN,
                confidence=0.70,
                category="ACCURACY",
                description="Always cite sources",
                path="ACCURACY/sales/email_draft",
            ),
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
        # Check frontmatter in a non-index file
        rule_files = [f for f in md_files if f.name != "_index.md"]
        assert len(rule_files) >= 1
        content = rule_files[0].read_text()
        assert "confidence:" in content
        assert "Be casual with VPs" in content
