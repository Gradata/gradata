"""
Tests for spawn.py extraction — route rules, agent loading, handoffs.

Validates the domain-agnostic orchestration functions extracted from
brain/scripts/spawn.py into the SDK patterns/ layer.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# 1. Route Rules (orchestrator.py)
# ---------------------------------------------------------------------------

class TestRouteRules:
    """Tests for register_route_rules() and route_by_keywords()."""

    def setup_method(self):
        """Reset route rules before each test."""
        from gradata.contrib.patterns.orchestrator import register_route_rules
        register_route_rules([], default_agent="general", replace=True)

    def test_route_by_keywords_returns_default_when_empty(self):
        from gradata.contrib.patterns.orchestrator import route_by_keywords
        assert route_by_keywords("some random task") == "general"

    def test_register_and_route_single_rule(self):
        from gradata.contrib.patterns.orchestrator import register_route_rules, route_by_keywords
        register_route_rules([
            (["research", "enrich"], "prospector"),
        ])
        assert route_by_keywords("Research this company") == "prospector"

    def test_route_case_insensitive(self):
        from gradata.contrib.patterns.orchestrator import register_route_rules, route_by_keywords
        register_route_rules([
            (["debug", "fix"], "debugger"),
        ])
        assert route_by_keywords("DEBUG the broken pipeline") == "debugger"
        assert route_by_keywords("Fix the error") == "debugger"

    def test_route_first_match_wins(self):
        from gradata.contrib.patterns.orchestrator import register_route_rules, route_by_keywords
        register_route_rules([
            (["check draft"], "critic"),
            (["draft", "write"], "writer"),
        ], replace=True)
        assert route_by_keywords("check draft of email") == "critic"
        assert route_by_keywords("draft an email") == "writer"

    def test_route_default_agent_override(self):
        from gradata.contrib.patterns.orchestrator import register_route_rules, route_by_keywords
        register_route_rules(
            [(["research"], "prospector")],
            default_agent="fallback-agent",
            replace=True,
        )
        assert route_by_keywords("unknown task xyz") == "fallback-agent"

    def test_register_replace_mode(self):
        from gradata.contrib.patterns.orchestrator import register_route_rules, route_by_keywords
        register_route_rules([(["alpha"], "agent-a")], replace=True)
        register_route_rules([(["beta"], "agent-b")], replace=True)
        # alpha rule should be gone after replace
        assert route_by_keywords("alpha task") != "agent-a"
        assert route_by_keywords("beta task") == "agent-b"

    def test_register_prepend_mode(self):
        from gradata.contrib.patterns.orchestrator import register_route_rules, route_by_keywords
        register_route_rules([(["task"], "agent-a")], replace=True)
        register_route_rules([(["task"], "agent-b")], replace=False)
        # Prepended rules take priority
        assert route_by_keywords("do this task") == "agent-b"

    def test_get_route_rules_returns_copy(self):
        from gradata.contrib.patterns.orchestrator import register_route_rules, get_route_rules
        register_route_rules([(["x"], "y")], replace=True)
        rules = get_route_rules()
        assert len(rules) == 1
        assert rules[0].keywords == ["x"]
        assert rules[0].agent == "y"
        # Mutating the copy should not affect the registry
        rules.clear()
        assert len(get_route_rules()) == 1

    def test_route_no_match_returns_default(self):
        from gradata.contrib.patterns.orchestrator import register_route_rules, route_by_keywords
        register_route_rules(
            [(["very-specific-keyword"], "special-agent")],
            default_agent="my-default",
            replace=True,
        )
        assert route_by_keywords("nothing matches here") == "my-default"

    def test_route_empty_description(self):
        from gradata.contrib.patterns.orchestrator import register_route_rules, route_by_keywords
        register_route_rules([(["x"], "y")], default_agent="d", replace=True)
        assert route_by_keywords("") == "d"

    def test_route_multi_word_keyword(self):
        from gradata.contrib.patterns.orchestrator import register_route_rules, route_by_keywords
        register_route_rules([
            (["linkedin message"], "writer"),
            (["linkedin"], "prospector"),
        ], replace=True)
        assert route_by_keywords("Send a linkedin message") == "writer"
        assert route_by_keywords("Search linkedin for leads") == "prospector"


# ---------------------------------------------------------------------------
# 2. Agent Definition Loading (sub_agents.py)
# ---------------------------------------------------------------------------

class TestLoadAgentDefinition:
    """Tests for load_agent_definition()."""

    def test_missing_file_returns_defaults(self, tmp_path):
        from gradata.contrib.patterns.sub_agents import load_agent_definition
        result = load_agent_definition("nonexistent", tmp_path)
        assert result["name"] == "nonexistent"
        assert "_warning" in result
        assert result["model"] == "sonnet"
        assert isinstance(result["tools"], list)
        assert len(result["system_prompt"]) > 0

    def test_plain_markdown_no_frontmatter(self, tmp_path):
        from gradata.contrib.patterns.sub_agents import load_agent_definition
        agent_file = tmp_path / "simple.md"
        agent_file.write_text("You are a simple agent.\nDo the thing.", encoding="utf-8")
        result = load_agent_definition("simple", tmp_path)
        assert result["name"] == "simple"
        assert result["system_prompt"] == "You are a simple agent.\nDo the thing."
        assert "_warning" not in result

    def test_frontmatter_parsed_correctly(self, tmp_path):
        from gradata.contrib.patterns.sub_agents import load_agent_definition
        agent_file = tmp_path / "research.md"
        agent_file.write_text(
            "---\n"
            "name: Research Agent\n"
            "description: Researches prospects\n"
            "model: opus\n"
            "tools:\n"
            "- Read\n"
            "- Grep\n"
            "- WebSearch\n"
            "---\n"
            "You are a research agent.\n"
            "Find all relevant information.",
            encoding="utf-8",
        )
        result = load_agent_definition("research", tmp_path)
        assert result["name"] == "Research Agent"
        assert result["description"] == "Researches prospects"
        assert result["model"] == "opus"
        assert result["tools"] == ["Read", "Grep", "WebSearch"]
        assert "You are a research agent." in result["system_prompt"]

    def test_empty_frontmatter(self, tmp_path):
        from gradata.contrib.patterns.sub_agents import load_agent_definition
        agent_file = tmp_path / "empty-fm.md"
        # Empty frontmatter (no key-value lines) — body is still parsed
        agent_file.write_text("---\nempty: true\n---\nJust the body.", encoding="utf-8")
        result = load_agent_definition("empty-fm", tmp_path)
        assert result["system_prompt"] == "Just the body."
        assert result["name"] == "empty-fm"

    def test_default_agent_definition_constant(self):
        from gradata.contrib.patterns.sub_agents import DEFAULT_AGENT_DEFINITION
        assert DEFAULT_AGENT_DEFINITION["model"] == "sonnet"
        assert isinstance(DEFAULT_AGENT_DEFINITION["tools"], list)


# ---------------------------------------------------------------------------
# 3. Handoff Management (sub_agents.py)
# ---------------------------------------------------------------------------

class TestHandoffs:
    """Tests for create_handoff() and read_handoff()."""

    def test_create_and_read_handoff(self, tmp_path):
        from gradata.contrib.patterns.sub_agents import create_handoff, read_handoff
        handoff_dir = tmp_path / "handoffs"
        path = create_handoff("task_001", "researcher", "Found 3 leads.", handoff_dir)
        assert Path(path).exists()
        assert "task_001_researcher.md" in path

        content = read_handoff("task_001", "researcher", handoff_dir)
        assert content == "Found 3 leads."

    def test_read_handoff_missing_file(self, tmp_path):
        from gradata.contrib.patterns.sub_agents import read_handoff
        content = read_handoff("missing_task", "ghost", tmp_path)
        assert content == ""

    def test_create_handoff_creates_directory(self, tmp_path):
        from gradata.contrib.patterns.sub_agents import create_handoff
        nested = tmp_path / "deep" / "nested" / "handoffs"
        path = create_handoff("t1", "agent", "output", nested)
        assert Path(path).exists()

    def test_handoff_overwrites_existing(self, tmp_path):
        from gradata.contrib.patterns.sub_agents import create_handoff, read_handoff
        handoff_dir = tmp_path / "handoffs"
        create_handoff("t1", "a", "first version", handoff_dir)
        create_handoff("t1", "a", "second version", handoff_dir)
        content = read_handoff("t1", "a", handoff_dir)
        assert content == "second version"

    def test_handoff_unicode_content(self, tmp_path):
        from gradata.contrib.patterns.sub_agents import create_handoff, read_handoff
        handoff_dir = tmp_path / "handoffs"
        create_handoff("t1", "a", "Hello from Tokyo", handoff_dir)
        content = read_handoff("t1", "a", handoff_dir)
        assert "Tokyo" in content


# ---------------------------------------------------------------------------
# 4. Agent Quality Scores (agent_graduation.py)
# ---------------------------------------------------------------------------

class TestComputeQualityScores:
    """Tests for AgentGraduationTracker.compute_quality_scores()."""

    def test_empty_tracker_returns_empty(self, tmp_path):
        from gradata.enhancements.graduation.agent_graduation import AgentGraduationTracker
        tracker = AgentGraduationTracker(tmp_path)
        scores = tracker.compute_quality_scores()
        assert scores["by_agent"] == {}
        assert scores["overall_pass_rate"] == 0
        assert scores["worst_agent"] is None
        assert scores["best_agent"] is None

    def test_scores_after_recording_outcomes(self, tmp_path):
        from gradata.enhancements.graduation.agent_graduation import AgentGraduationTracker
        tracker = AgentGraduationTracker(tmp_path)

        # Record 10 approvals for research agent
        for i in range(10):
            tracker.record_outcome("research", f"output {i}", "approved")

        scores = tracker.compute_quality_scores()
        assert "research" in scores["by_agent"]
        agent_scores = scores["by_agent"]["research"]
        assert agent_scores["total_verified"] == 10
        assert agent_scores["pass_rate"] == 1.0
        assert agent_scores["avg_score"] == 10.0  # 100% FDA -> 10.0
        assert agent_scores["reject_count"] == 0

    def test_scores_with_mixed_outcomes(self, tmp_path):
        from gradata.enhancements.graduation.agent_graduation import AgentGraduationTracker
        tracker = AgentGraduationTracker(tmp_path)

        # 7 approved, 2 edited, 1 rejected = 70% FDA, 90% acceptance
        for i in range(7):
            tracker.record_outcome("writer", f"output {i}", "approved")
        for i in range(2):
            tracker.record_outcome("writer", f"edited {i}", "edited", edits=f"fix {i}")
        tracker.record_outcome("writer", "rejected", "rejected", edits="bad output")

        scores = tracker.compute_quality_scores()
        writer = scores["by_agent"]["writer"]
        assert writer["total_verified"] == 10
        assert writer["pass_rate"] == 0.9   # 9/10 accepted or edited
        assert writer["avg_score"] == 7.0   # 7/10 FDA -> 7.0
        assert writer["reject_count"] == 1

    def test_best_worst_agent_selection(self, tmp_path):
        from gradata.enhancements.graduation.agent_graduation import AgentGraduationTracker
        tracker = AgentGraduationTracker(tmp_path)

        # Research: 100% FDA
        for i in range(5):
            tracker.record_outcome("research", f"r{i}", "approved")
        # Writer: 0% FDA (all edited)
        for i in range(5):
            tracker.record_outcome("writer", f"w{i}", "edited", edits=f"rewrite {i}")

        scores = tracker.compute_quality_scores()
        assert scores["best_agent"] == "research"
        assert scores["worst_agent"] == "writer"
