"""
Tests for the 6 features stolen from SuperMemory and EverMemOS.
================================================================

Steal 3: MCP Tools (correct, recall, manifest)
Steal 4: Correction Detector
Steal 5: Rule Conflict Detection
Steal 6: Learning Graph

Steals 1-2 are design docs (no code to test).
"""

import json
import re
import tempfile
from pathlib import Path

import pytest

from gradata._types import Lesson, LessonState, CorrectionType, RuleTransferScope


# =========================================================================
# STEAL 3: MCP Tools
# =========================================================================


class TestMCPToolCorrect:
    """Test the correct() MCP tool."""

    def test_identical_text_returns_as_is(self):
        from gradata.mcp_tools import correct

        result = correct("hello world", "hello world")
        assert result["severity"] == "as-is"
        assert result["edit_distance"] < 0.02
        assert result["lesson_created"] is False

    def test_empty_inputs(self):
        from gradata.mcp_tools import correct

        result = correct("", "")
        assert result["severity"] == "as-is"
        assert result["lesson_created"] is False

    def test_minor_edit(self):
        from gradata.mcp_tools import correct

        result = correct("Hello world", "Hello brave world")
        assert result["severity"] in ("minor", "moderate")
        assert result["edit_distance"] > 0.0
        assert "category" in result
        assert "summary_stats" in result

    def test_major_edit(self):
        from gradata.mcp_tools import correct

        result = correct(
            "This is the original draft with lots of content that should be completely rewritten.",
            "Completely different text with nothing in common at all from the first version.",
        )
        assert result["severity"] in ("major", "discarded", "moderate")
        assert result["edit_distance"] > 0.2

    def test_category_override(self):
        from gradata.mcp_tools import correct

        result = correct("draft", "final", category="ACCURACY")
        assert result["category"] == "ACCURACY"

    def test_auto_detect_formatting(self):
        from gradata.mcp_tools import correct

        result = correct(
            "Use **bold** for emphasis and em dash for lists",
            "Use plain text for emphasis and colon for lists",
        )
        assert result["category"] == "FORMATTING"

    def test_auto_detect_accuracy(self):
        from gradata.mcp_tools import correct

        result = correct(
            "The API returns an error code 500",
            "The API returns an incorrect status code 500",
        )
        assert result["category"] == "ACCURACY"

    def test_result_has_all_keys(self):
        from gradata.mcp_tools import correct

        result = correct("alpha", "beta")
        required_keys = {"severity", "edit_distance", "compression_distance",
                         "category", "summary_stats", "lesson_created"}
        assert required_keys.issubset(result.keys())


class TestMCPToolRecall:
    """Test the recall() MCP tool."""

    def test_no_lessons_returns_empty(self):
        from gradata.mcp_tools import recall

        result = recall("write an email", lessons_path="/nonexistent/path")
        assert result == "<brain-rules/>"

    def test_with_lessons_file(self, tmp_path):
        from gradata.mcp_tools import recall

        lessons_file = tmp_path / "lessons.md"
        lessons_file.write_text(
            "[2026-03-01] [RULE:0.95] DRAFTING: Never use revolutionize in cold emails\n"
            "[2026-03-01] [PATTERN:0.72] PROCESS: Verify prospect identity before drafting\n"
            "[2026-03-01] [INSTINCT:0.35] TONE: Use casual tone for follow-ups\n",
            encoding="utf-8",
        )

        result = recall("write cold email", lessons_path=str(lessons_file), max_rules=5)
        assert "<brain-rules>" in result
        assert "DRAFTING" in result
        # INSTINCT should not appear (below PATTERN threshold)
        assert "INSTINCT" not in result

    def test_max_rules_limit(self, tmp_path):
        from gradata.mcp_tools import recall

        lines = []
        for i in range(20):
            lines.append(f"[2026-03-01] [RULE:0.9{i % 10}] CAT{i}: Rule number {i} about email writing\n")

        lessons_file = tmp_path / "lessons.md"
        lessons_file.write_text("".join(lines), encoding="utf-8")

        result = recall("email writing", lessons_path=str(lessons_file), max_rules=3)
        # Count actual rule lines (excluding XML tags)
        rule_lines = [l for l in result.strip().split("\n") if l.startswith("[")]
        assert len(rule_lines) <= 3

    def test_relevance_ranking(self, tmp_path):
        from gradata.mcp_tools import recall

        lessons_file = tmp_path / "lessons.md"
        lessons_file.write_text(
            "[2026-03-01] [RULE:0.95] DRAFTING: Never use AI tells in cold emails\n"
            "[2026-03-01] [RULE:0.90] PROCESS: Always check calendar before scheduling\n"
            "[2026-03-01] [RULE:0.88] DRAFTING: Keep email subject lines under 50 chars\n",
            encoding="utf-8",
        )

        result = recall("write cold email subject", lessons_path=str(lessons_file))
        assert "<brain-rules>" in result
        # Email-related rules should rank higher
        assert "email" in result.lower()


class TestMCPToolManifest:
    """Test the manifest() MCP tool."""

    def test_returns_all_keys(self):
        from gradata.mcp_tools import manifest

        result = manifest()
        required_keys = {"correction_rate", "categories_extinct", "compound_score",
                         "rules_count", "meta_rules_count", "sessions_trained",
                         "maturity_phase", "lessons_active", "lessons_graduated"}
        assert required_keys.issubset(result.keys())

    def test_compound_score_range(self):
        from gradata.mcp_tools import manifest

        result = manifest()
        assert 0.0 <= result["compound_score"] <= 10.0

    def test_categories_extinct_is_list(self):
        from gradata.mcp_tools import manifest

        result = manifest()
        assert isinstance(result["categories_extinct"], list)

    def test_with_lessons(self, tmp_path):
        from gradata.mcp_tools import manifest

        lessons_file = tmp_path / "lessons.md"
        lessons_file.write_text(
            "[2026-03-01] [RULE:0.95] DRAFTING: Never use revolutionize\n"
            "[2026-03-01] [RULE:0.92] DRAFTING: Keep emails under 200 words\n"
            "[2026-03-01] [PATTERN:0.72] PROCESS: Verify identity first\n"
            "[2026-03-01] [INSTINCT:0.35] TONE: Casual follow-ups\n",
            encoding="utf-8",
        )

        result = manifest(lessons_path=str(lessons_file))
        assert result["rules_count"] >= 2  # 2 RULE + 1 PATTERN
        assert result["lessons_graduated"] >= 2
        assert result["compound_score"] > 0.0

    def test_extinct_categories(self, tmp_path):
        from gradata.mcp_tools import manifest

        lessons_file = tmp_path / "lessons.md"
        lessons_file.write_text(
            "[2026-03-01] [RULE:0.95] FORMATTING: No em dashes\n"
            "[2026-03-01] [RULE:0.92] FORMATTING: Use colons\n"
            "[2026-03-01] [INSTINCT:0.35] DRAFTING: Something new\n",
            encoding="utf-8",
        )

        result = manifest(lessons_path=str(lessons_file))
        assert "FORMATTING" in result["categories_extinct"]
        assert "DRAFTING" not in result["categories_extinct"]


# =========================================================================
# STEAL 4: Correction Detector
# =========================================================================


class TestCorrectionDetector:
    """Test passive correction detection."""

    def test_explicit_negation(self):
        from gradata.correction_detector import detect_correction

        is_corr, conf = detect_correction("No, not like that")
        assert is_corr is True
        assert conf >= 0.80

    def test_prohibition(self):
        from gradata.correction_detector import detect_correction

        is_corr, conf = detect_correction("Don't use em dashes in emails")
        assert is_corr is True
        assert conf >= 0.85

    def test_wrong_label(self):
        from gradata.correction_detector import detect_correction

        is_corr, conf = detect_correction("That's incorrect, the API key is different")
        assert is_corr is True
        assert conf >= 0.80

    def test_stop_directive(self):
        from gradata.correction_detector import detect_correction

        is_corr, conf = detect_correction("Stop using bold in the middle of paragraphs")
        assert is_corr is True
        assert conf >= 0.85

    def test_implicit_redirect(self):
        from gradata.correction_detector import detect_correction

        is_corr, conf = detect_correction("Actually, I wanted it shorter")
        assert is_corr is True
        assert conf >= 0.50

    def test_implicit_should_be(self):
        from gradata.correction_detector import detect_correction

        is_corr, conf = detect_correction("It should be more concise")
        assert is_corr is True
        assert conf >= 0.50

    def test_not_a_correction(self):
        from gradata.correction_detector import detect_correction

        is_corr, conf = detect_correction("Looks great, ship it!")
        assert is_corr is False
        assert conf < 0.50

    def test_empty_text(self):
        from gradata.correction_detector import detect_correction

        is_corr, conf = detect_correction("")
        assert is_corr is False
        assert conf == 0.0

    def test_none_like_empty(self):
        from gradata.correction_detector import detect_correction

        is_corr, conf = detect_correction("   ")
        assert is_corr is False
        assert conf == 0.0

    def test_multiple_signals_compound(self):
        from gradata.correction_detector import detect_correction

        # Multiple correction signals should compound confidence
        is_corr, conf = detect_correction(
            "No, that's wrong. Don't use those words. Make it shorter."
        )
        assert is_corr is True
        assert conf >= 0.90

    def test_prior_reference(self):
        from gradata.correction_detector import detect_correction

        is_corr, conf = detect_correction("I told you to use colons, not dashes")
        assert is_corr is True
        assert conf >= 0.70

    def test_redo_request(self):
        from gradata.correction_detector import detect_correction

        is_corr, conf = detect_correction("Rewrite this completely")
        assert is_corr is True
        assert conf >= 0.80

    def test_degree_correction(self):
        from gradata.correction_detector import detect_correction

        is_corr, conf = detect_correction("This is too verbose for a cold email")
        assert is_corr is True
        assert conf >= 0.70


class TestCorrectionContext:
    """Test rich correction context extraction."""

    def test_extract_prohibition_changes(self):
        from gradata.correction_detector import extract_correction_context

        ctx = extract_correction_context("Don't use em dashes in the email")
        assert ctx.is_correction is True
        assert "prohibition" in ctx.signals
        assert any("em dashes" in c for c in ctx.implied_changes)

    def test_extract_change_instruction(self):
        from gradata.correction_detector import extract_correction_context

        ctx = extract_correction_context("Change this to something shorter")
        assert ctx.is_correction is True
        assert len(ctx.signal_details) > 0

    def test_extract_degree_changes(self):
        from gradata.correction_detector import extract_correction_context

        ctx = extract_correction_context("This is too formal for a follow-up")
        assert ctx.is_correction is True
        assert any("formal" in c for c in ctx.implied_changes)

    def test_empty_context(self):
        from gradata.correction_detector import extract_correction_context

        ctx = extract_correction_context("")
        assert ctx.is_correction is False
        assert ctx.confidence == 0.0
        assert ctx.signals == []

    def test_draft_comparison(self):
        from gradata.correction_detector import extract_correction_context

        draft = "Subject: Revolutionize Your Business with AI-Powered Insights"
        user = "Actually, make it shorter. Subject: Quick question about your ad spend"

        ctx = extract_correction_context(user, assistant_draft=draft)
        assert ctx.is_correction is True


# =========================================================================
# STEAL 5: Rule Conflict Detection
# =========================================================================


class TestRuleConflicts:
    """Test rule relationship classification."""

    def _make_lesson(self, desc: str, *, category: str = "DRAFTING",
                     state: LessonState = LessonState.RULE,
                     confidence: float = 0.90) -> Lesson:
        return Lesson(
            date="2026-03-01",
            state=state,
            confidence=confidence,
            category=category,
            description=desc,
        )

    def test_updates_detection(self):
        from gradata.enhancements.rule_conflicts import detect_rule_conflict, RuleRelation

        new = self._make_lesson("Always avoid using formal tone in emails")
        existing = [
            self._make_lesson("Always use formal tone in emails"),
        ]

        relation, target = detect_rule_conflict(new, existing)
        assert relation == RuleRelation.UPDATES
        assert target is not None

    def test_extends_detection(self):
        from gradata.enhancements.rule_conflicts import detect_rule_conflict, RuleRelation

        new = self._make_lesson("Use colons instead of em dashes in email subject lines")
        existing = [
            self._make_lesson("Use colons instead of em dashes in email body text"),
        ]

        relation, target = detect_rule_conflict(new, existing)
        assert relation == RuleRelation.EXTENDS
        assert target is not None

    def test_derives_detection(self):
        from gradata.enhancements.rule_conflicts import detect_rule_conflict, RuleRelation

        new = self._make_lesson("Use colons instead of em dashes in email paragraphs")
        existing = [
            self._make_lesson("Use colons instead of em dashes in email subject lines"),
            self._make_lesson("Use colons instead of em dashes in email bullet points"),
            self._make_lesson("Use colons instead of em dashes in email headers"),
        ]

        relation, target = detect_rule_conflict(new, existing)
        # All same category with high keyword overlap -> DERIVES or EXTENDS
        assert relation in (RuleRelation.DERIVES, RuleRelation.EXTENDS)

    def test_independent_detection(self):
        from gradata.enhancements.rule_conflicts import detect_rule_conflict, RuleRelation

        new = self._make_lesson("Always verify prospect company size before outreach")
        existing = [
            self._make_lesson("Use colons not em dashes in emails"),
        ]

        relation, target = detect_rule_conflict(new, existing)
        assert relation == RuleRelation.INDEPENDENT
        assert target is None

    def test_empty_existing_rules(self):
        from gradata.enhancements.rule_conflicts import detect_rule_conflict, RuleRelation

        new = self._make_lesson("Some new rule")
        relation, target = detect_rule_conflict(new, [])
        assert relation == RuleRelation.INDEPENDENT

    def test_classify_all_relations(self):
        from gradata.enhancements.rule_conflicts import classify_all_relations, RuleRelation

        new = self._make_lesson("Use short email subject lines for cold outreach")
        existing = [
            self._make_lesson("Keep email subject lines under fifty characters"),
            self._make_lesson("Always verify prospect identity before drafting"),
            self._make_lesson("Use formal tone in cold outreach emails"),
        ]

        results = classify_all_relations(new, existing)
        assert isinstance(results, list)
        # Should have at least one result (the subject line rule is similar)
        # Results are sorted by similarity descending


class TestRuleRelationEnum:
    """Test RuleRelation enum values."""

    def test_all_values(self):
        from gradata.enhancements.rule_conflicts import RuleRelation

        assert RuleRelation.UPDATES.value == "updates"
        assert RuleRelation.EXTENDS.value == "extends"
        assert RuleRelation.DERIVES.value == "derives"
        assert RuleRelation.INDEPENDENT.value == "independent"


# =========================================================================
# STEAL 6: Learning Graph
# =========================================================================


class TestLearningGraph:
    """Test the graph data model and builder."""

    def _make_lessons(self) -> list[Lesson]:
        return [
            Lesson(date="2026-03-01", state=LessonState.RULE, confidence=0.95,
                   category="DRAFTING", description="Never use revolutionize"),
            Lesson(date="2026-03-01", state=LessonState.RULE, confidence=0.92,
                   category="DRAFTING", description="Keep emails under 200 words"),
            Lesson(date="2026-03-01", state=LessonState.PATTERN, confidence=0.72,
                   category="PROCESS", description="Verify prospect identity"),
            Lesson(date="2026-03-01", state=LessonState.INSTINCT, confidence=0.35,
                   category="TONE", description="Casual follow-up tone"),
            Lesson(date="2026-03-01", state=LessonState.PATTERN, confidence=0.68,
                   category="FORMATTING", description="No em dashes in email"),
        ]

    def test_build_graph_nodes(self):
        from gradata.graph import build_learning_graph

        lessons = self._make_lessons()
        nodes, edges = build_learning_graph(lessons)

        assert len(nodes) == 5
        # Check node types
        types = {n.type for n in nodes}
        assert "rule" in types
        assert "lesson" in types

    def test_build_graph_edges(self):
        from gradata.graph import build_learning_graph

        lessons = self._make_lessons()
        nodes, edges = build_learning_graph(lessons)

        # Should have graduation edges within DRAFTING category
        edge_relations = {e.relation for e in edges}
        assert len(edges) > 0

    def test_build_graph_with_meta_rules(self):
        from gradata.graph import build_learning_graph

        lessons = self._make_lessons()
        meta_rules = [
            {
                "id": "meta_formatting",
                "principle": "The user values minimal clean formatting",
                "source_categories": ["FORMATTING", "DRAFTING"],
                "source_lesson_ids": [],
                "confidence": 0.88,
                "created_session": 42,
            }
        ]

        nodes, edges = build_learning_graph(lessons, meta_rules)

        # Should have meta-rule node
        meta_nodes = [n for n in nodes if n.type == "meta_rule"]
        assert len(meta_nodes) == 1
        assert meta_nodes[0].id == "meta_formatting"
        assert meta_nodes[0].size == 1.5  # Meta-rules are larger

    def test_to_json(self):
        from gradata.graph import build_learning_graph, to_json

        lessons = self._make_lessons()
        nodes, edges = build_learning_graph(lessons)
        json_str = to_json(nodes, edges)

        data = json.loads(json_str)
        assert "nodes" in data
        assert "links" in data  # D3 convention
        assert len(data["nodes"]) == 5

    def test_to_mermaid(self):
        from gradata.graph import build_learning_graph, to_mermaid

        lessons = self._make_lessons()
        nodes, edges = build_learning_graph(lessons)
        mermaid = to_mermaid(nodes, edges)

        assert mermaid.startswith("graph TD")
        assert "lesson_0" in mermaid

    def test_write_graph(self, tmp_path):
        from gradata.graph import build_learning_graph, write_graph

        lessons = self._make_lessons()
        nodes, edges = build_learning_graph(lessons)

        output_path = tmp_path / "graph.json"
        result = write_graph(nodes, edges, output_path)

        assert result.exists()
        data = json.loads(result.read_text(encoding="utf-8"))
        assert len(data["nodes"]) == 5

    def test_empty_lessons(self):
        from gradata.graph import build_learning_graph

        nodes, edges = build_learning_graph([])
        assert nodes == []
        assert edges == []

    def test_node_size_scaling(self):
        from gradata.graph import build_learning_graph

        lessons = [
            Lesson(date="2026-03-01", state=LessonState.RULE, confidence=0.99,
                   category="DRAFTING", description="High confidence rule",
                   fire_count=10),
            Lesson(date="2026-03-01", state=LessonState.INSTINCT, confidence=0.20,
                   category="DRAFTING", description="Low confidence instinct",
                   fire_count=0),
        ]

        nodes, _ = build_learning_graph(lessons)
        assert nodes[0].size > nodes[1].size  # Higher confidence = larger


class TestGraphDataclasses:
    """Test GraphNode and GraphEdge dataclasses."""

    def test_graph_node_defaults(self):
        from gradata.graph import GraphNode

        node = GraphNode(id="test", type="lesson", label="Test", confidence=0.5)
        assert node.session == 0
        assert node.category == ""
        assert node.state == ""
        assert node.size == 1.0

    def test_graph_edge_defaults(self):
        from gradata.graph import GraphEdge

        edge = GraphEdge(source="a", target="b", relation="extends")
        assert edge.weight == 1.0


# =========================================================================
# Cross-module integration tests
# =========================================================================


class TestIntegration:
    """Test that all new modules import cleanly and work together."""

    def test_all_imports(self):
        from gradata.mcp_tools import correct, recall, manifest
        from gradata.correction_detector import detect_correction, extract_correction_context
        from gradata.enhancements.rule_conflicts import detect_rule_conflict, RuleRelation
        from gradata.graph import build_learning_graph, GraphNode, GraphEdge, to_json

    def test_correction_to_graph_flow(self):
        """Simulate: detect correction -> log it -> build graph."""
        from gradata.correction_detector import detect_correction
        from gradata.mcp_tools import correct
        from gradata.graph import build_learning_graph

        # Step 1: Detect correction
        is_corr, conf = detect_correction("No, don't use bold in the email body")
        assert is_corr is True

        # Step 2: Log the correction
        result = correct(
            "Please find the **attached proposal** for your review.",
            "Please find the attached proposal for your review.",
            category="FORMATTING",
        )
        assert result["category"] == "FORMATTING"

        # Step 3: Build graph with the lesson
        lesson = Lesson(
            date="2026-03-27",
            state=LessonState.INSTINCT,
            confidence=0.30,
            category="FORMATTING",
            description="No bold in email body text",
        )
        nodes, edges = build_learning_graph([lesson])
        assert len(nodes) == 1
        assert nodes[0].category == "FORMATTING"

    def test_conflict_detection_to_graph_flow(self):
        """Simulate: new correction -> check conflicts -> build graph with edges."""
        from gradata.enhancements.rule_conflicts import classify_all_relations, RuleRelation
        from gradata.graph import build_learning_graph, GraphEdge

        existing = [
            Lesson(date="2026-03-01", state=LessonState.RULE, confidence=0.95,
                   category="DRAFTING", description="Always keep emails concise and short"),
            Lesson(date="2026-03-01", state=LessonState.RULE, confidence=0.90,
                   category="DRAFTING", description="Use direct subject lines in cold emails"),
        ]

        new_lesson = Lesson(
            date="2026-03-27", state=LessonState.INSTINCT, confidence=0.30,
            category="DRAFTING", description="Keep cold emails under three sentences",
        )

        # Check relations
        relations = classify_all_relations(new_lesson, existing)

        # Build graph
        all_lessons = existing + [new_lesson]
        nodes, edges = build_learning_graph(all_lessons)
        assert len(nodes) == 3
