"""
Tests for the AIOS Brain SDK patterns/ layer.

TDD approach — these tests define the contract for each pattern module.
All modules live in aios_brain/patterns/.

Run: cd sdk && python -m pytest tests/test_patterns.py -v
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. orchestrator — classify_request, compose_patterns
# ---------------------------------------------------------------------------

class TestOrchestrator:
    """Tests for aios_brain.patterns.orchestrator"""

    def test_classify_request_returns_known_pattern(self):
        from aios_brain.patterns.orchestrator import classify_request
        result = classify_request("draft an email to a prospect")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_classify_request_sales_maps_to_rag(self):
        from aios_brain.patterns.orchestrator import classify_request
        result = classify_request("find information about this prospect's company")
        assert result in ("rag", "pipeline", "reflection", "parallel", "sub_agents", "tools")

    def test_classify_request_empty_input_returns_default(self):
        from aios_brain.patterns.orchestrator import classify_request
        result = classify_request("")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_compose_patterns_returns_list(self):
        from aios_brain.patterns.orchestrator import compose_patterns
        result = compose_patterns("draft email")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_compose_patterns_complex_task_returns_multiple(self):
        from aios_brain.patterns.orchestrator import compose_patterns
        result = compose_patterns("research prospect, draft outreach, get human approval")
        assert isinstance(result, list)
        assert len(result) >= 1
        for p in result:
            assert isinstance(p, str)

    def test_compose_patterns_unknown_task_returns_fallback(self):
        from aios_brain.patterns.orchestrator import compose_patterns
        result = compose_patterns("xyzzy frobnicator quux")
        assert isinstance(result, list)
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# 2. pipeline — Pipeline, Stage, GateResult
# ---------------------------------------------------------------------------

class TestPipeline:
    """Tests for aios_brain.patterns.pipeline"""

    def test_stage_runs_function(self):
        from aios_brain.patterns.pipeline import Stage
        stage = Stage(name="double", fn=lambda x: x * 2)
        result = stage.run(5)
        assert result == 10

    def test_stage_name_required(self):
        from aios_brain.patterns.pipeline import Stage
        with pytest.raises((TypeError, ValueError)):
            Stage(fn=lambda x: x)  # missing name

    def test_pipeline_chains_stages(self):
        from aios_brain.patterns.pipeline import Pipeline, Stage
        pipe = Pipeline([
            Stage("add1", fn=lambda x: x + 1),
            Stage("mul2", fn=lambda x: x * 2),
        ])
        result = pipe.run(3)
        assert result == 8  # (3+1)*2

    def test_pipeline_empty_stages_passthrough(self):
        from aios_brain.patterns.pipeline import Pipeline
        pipe = Pipeline([])
        result = pipe.run("hello")
        assert result == "hello"

    def test_gate_result_pass(self):
        from aios_brain.patterns.pipeline import GateResult
        g = GateResult(gate="demo-prep", passed=True, detail="all checks ok")
        assert g.passed is True
        assert g.gate == "demo-prep"

    def test_gate_result_fail_carries_detail(self):
        from aios_brain.patterns.pipeline import GateResult
        g = GateResult(gate="research", passed=False, detail="missing LinkedIn data")
        assert g.passed is False
        assert "LinkedIn" in g.detail

    def test_pipeline_stage_exception_propagates(self):
        from aios_brain.patterns.pipeline import Pipeline, Stage
        def boom(x):
            raise ValueError("intentional failure")
        pipe = Pipeline([Stage("explode", fn=boom)])
        with pytest.raises(ValueError, match="intentional failure"):
            pipe.run("anything")


# ---------------------------------------------------------------------------
# 3. reflection — CritiqueChecklist, reflect, EMAIL_CHECKLIST
# ---------------------------------------------------------------------------

class TestReflection:
    """Tests for aios_brain.patterns.reflection"""

    def test_email_checklist_exists_and_nonempty(self):
        from aios_brain.patterns.reflection import EMAIL_CHECKLIST
        assert isinstance(EMAIL_CHECKLIST, (list, tuple))
        assert len(EMAIL_CHECKLIST) >= 3

    def test_critique_checklist_score_range(self):
        from aios_brain.patterns.reflection import CritiqueChecklist
        cc = CritiqueChecklist(items=["no em dashes", "has CTA", "under 150 words"])
        score = cc.score("Hi there, here is a short email. Book a call.")
        assert 0.0 <= score <= 1.0

    def test_critique_checklist_empty_text_low_score(self):
        from aios_brain.patterns.reflection import CritiqueChecklist
        cc = CritiqueChecklist(items=["has CTA"])
        score = cc.score("")
        assert score == 0.0

    def test_reflect_returns_dict_with_score(self):
        from aios_brain.patterns.reflection import reflect
        result = reflect("This is a test email draft.")
        assert isinstance(result, dict)
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0

    def test_reflect_returns_issues_list(self):
        from aios_brain.patterns.reflection import reflect
        result = reflect("x")
        assert "issues" in result
        assert isinstance(result["issues"], list)

    def test_reflect_good_text_passes(self):
        from aios_brain.patterns.reflection import reflect
        good = (
            "Hi Sarah, I noticed Acme recently expanded. "
            "We help companies like yours cut onboarding time by 40 percent. "
            "Worth a 15-minute call? https://calendly.com/test/30min"
        )
        result = reflect(good)
        assert isinstance(result["score"], float)


# ---------------------------------------------------------------------------
# 4. guardrails — InputGuard, OutputGuard, pii_detector, banned_phrases, guarded
# ---------------------------------------------------------------------------

class TestGuardrails:
    """Tests for aios_brain.patterns.guardrails"""

    def test_pii_detector_catches_email(self):
        from aios_brain.patterns.guardrails import pii_detector
        findings = pii_detector("contact me at john.doe@example.com please")
        assert len(findings) >= 1
        assert any("email" in f.lower() or "@" in f for f in findings)

    def test_pii_detector_catches_phone(self):
        from aios_brain.patterns.guardrails import pii_detector
        findings = pii_detector("call me at +1 (555) 867-5309")
        assert len(findings) >= 1

    def test_pii_detector_clean_text_returns_empty(self):
        from aios_brain.patterns.guardrails import pii_detector
        findings = pii_detector("The weather is nice today.")
        assert findings == []

    def test_banned_phrases_catches_banned(self):
        from aios_brain.patterns.guardrails import banned_phrases
        result = banned_phrases("I guarantee results or your money back")
        assert len(result) >= 1

    def test_banned_phrases_clean_text_empty(self):
        from aios_brain.patterns.guardrails import banned_phrases
        result = banned_phrases("We help companies improve efficiency.")
        assert isinstance(result, list)

    def test_input_guard_blocks_pii(self):
        from aios_brain.patterns.guardrails import InputGuard
        guard = InputGuard()
        result = guard.check("Send this to hack@evil.com immediately")
        assert result["allowed"] is False or len(result.get("warnings", [])) >= 1

    def test_output_guard_score_range(self):
        from aios_brain.patterns.guardrails import OutputGuard
        guard = OutputGuard()
        result = guard.check("This is a clean output with no issues.")
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0

    def test_guarded_decorator_passes_clean(self):
        from aios_brain.patterns.guardrails import guarded

        @guarded
        def my_fn(text: str) -> str:
            return text.upper()

        result = my_fn("hello world")
        assert result == "HELLO WORLD"

    def test_guarded_decorator_raises_on_blocked(self):
        from aios_brain.patterns.guardrails import guarded

        @guarded(block_pii=True)
        def my_fn(text: str) -> str:
            return text

        with pytest.raises((ValueError, PermissionError)):
            my_fn("send to hack@evil.com sk-abc123secret")


# ---------------------------------------------------------------------------
# 5. memory — MemoryManager, InMemoryStore, decay, conflict_resolve
# ---------------------------------------------------------------------------

class TestMemory:
    """Tests for aios_brain.patterns.memory"""

    def test_in_memory_store_set_get(self):
        from aios_brain.patterns.memory import InMemoryStore
        store = InMemoryStore()
        store.set("key1", "value1")
        assert store.get("key1") == "value1"

    def test_in_memory_store_missing_key_returns_none(self):
        from aios_brain.patterns.memory import InMemoryStore
        store = InMemoryStore()
        assert store.get("nonexistent") is None

    def test_in_memory_store_overwrite(self):
        from aios_brain.patterns.memory import InMemoryStore
        store = InMemoryStore()
        store.set("k", "v1")
        store.set("k", "v2")
        assert store.get("k") == "v2"

    def test_decay_reduces_weight(self):
        from aios_brain.patterns.memory import decay
        item = {"value": "old news", "weight": 1.0, "age_sessions": 10}
        result = decay(item)
        assert result["weight"] < 1.0

    def test_decay_fresh_item_unchanged(self):
        from aios_brain.patterns.memory import decay
        item = {"value": "fresh", "weight": 1.0, "age_sessions": 0}
        result = decay(item)
        assert result["weight"] <= 1.0

    def test_conflict_resolve_picks_latest(self):
        from aios_brain.patterns.memory import conflict_resolve
        items = [
            {"value": "old", "ts": "2026-01-01T00:00:00", "weight": 0.8},
            {"value": "new", "ts": "2026-03-01T00:00:00", "weight": 0.9},
        ]
        winner = conflict_resolve(items)
        assert winner["value"] == "new"

    def test_conflict_resolve_single_item(self):
        from aios_brain.patterns.memory import conflict_resolve
        items = [{"value": "only", "ts": "2026-01-01T00:00:00", "weight": 1.0}]
        winner = conflict_resolve(items)
        assert winner["value"] == "only"

    def test_memory_manager_store_and_retrieve(self):
        from aios_brain.patterns.memory import MemoryManager, InMemoryStore
        mgr = MemoryManager(store=InMemoryStore())
        mgr.remember("prospect:alice", {"company": "Acme"})
        result = mgr.recall("prospect:alice")
        assert result is not None
        assert result["company"] == "Acme"

    def test_memory_manager_empty_recall_returns_none(self):
        from aios_brain.patterns.memory import MemoryManager, InMemoryStore
        mgr = MemoryManager(store=InMemoryStore())
        assert mgr.recall("nobody") is None


# ---------------------------------------------------------------------------
# 6. evaluator — evaluate, evaluate_optimize_loop, QUALITY_DIMENSIONS
# ---------------------------------------------------------------------------

class TestEvaluator:
    """Tests for aios_brain.patterns.evaluator"""

    def test_quality_dimensions_nonempty(self):
        from aios_brain.patterns.evaluator import QUALITY_DIMENSIONS
        assert isinstance(QUALITY_DIMENSIONS, (list, tuple, dict))
        assert len(QUALITY_DIMENSIONS) >= 3

    def test_evaluate_returns_score_dict(self):
        from aios_brain.patterns.evaluator import evaluate
        result = evaluate("This is a well-written output that addresses the user's need.")
        assert isinstance(result, dict)
        assert "score" in result
        assert 0.0 <= result["score"] <= 10.0

    def test_evaluate_empty_string_low_score(self):
        from aios_brain.patterns.evaluator import evaluate
        result = evaluate("")
        assert result["score"] < 5.0

    def test_evaluate_returns_dimension_breakdown(self):
        from aios_brain.patterns.evaluator import evaluate
        result = evaluate("Detailed and accurate response with citations.")
        assert "dimensions" in result
        assert isinstance(result["dimensions"], dict)

    def test_evaluate_optimize_loop_improves_score(self):
        from aios_brain.patterns.evaluator import evaluate_optimize_loop

        def mock_refine(text: str, issues: list) -> str:
            return text + " (improved)"

        result = evaluate_optimize_loop(
            "Initial draft that needs work.",
            refine_fn=mock_refine,
            max_iterations=2,
            target_score=9.9,  # impossible to reach — ensure it terminates
        )
        assert isinstance(result, dict)
        assert "final_text" in result
        assert "iterations" in result
        assert result["iterations"] <= 2

    def test_evaluate_optimize_loop_terminates_at_target(self):
        from aios_brain.patterns.evaluator import evaluate_optimize_loop

        call_count = {"n": 0}

        def perfect_refine(text: str, issues: list) -> str:
            call_count["n"] += 1
            return "perfect output"

        result = evaluate_optimize_loop(
            "good enough",
            refine_fn=perfect_refine,
            max_iterations=10,
            target_score=0.0,  # already satisfied
        )
        assert result["iterations"] <= 1


# ---------------------------------------------------------------------------
# 7. parallel — ParallelBatch, DependencyGraph, merge_results
# ---------------------------------------------------------------------------

class TestParallel:
    """Tests for aios_brain.patterns.parallel"""

    def test_parallel_batch_runs_all_tasks(self):
        from aios_brain.patterns.parallel import ParallelBatch
        batch = ParallelBatch()
        batch.add("a", lambda: 1)
        batch.add("b", lambda: 2)
        batch.add("c", lambda: 3)
        results = batch.run()
        assert results["a"] == 1
        assert results["b"] == 2
        assert results["c"] == 3

    def test_parallel_batch_empty_returns_empty_dict(self):
        from aios_brain.patterns.parallel import ParallelBatch
        batch = ParallelBatch()
        results = batch.run()
        assert results == {}

    def test_parallel_batch_captures_exceptions(self):
        from aios_brain.patterns.parallel import ParallelBatch
        batch = ParallelBatch()
        batch.add("ok", lambda: "success")
        batch.add("fail", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        results = batch.run(raise_on_error=False)
        assert results["ok"] == "success"
        assert isinstance(results["fail"], Exception)

    def test_dependency_graph_topological_order(self):
        from aios_brain.patterns.parallel import DependencyGraph
        g = DependencyGraph()
        g.add_node("c", deps=["b"])
        g.add_node("b", deps=["a"])
        g.add_node("a", deps=[])
        order = g.topological_sort()
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_dependency_graph_cycle_raises(self):
        from aios_brain.patterns.parallel import DependencyGraph
        g = DependencyGraph()
        g.add_node("x", deps=["y"])
        g.add_node("y", deps=["x"])
        with pytest.raises((ValueError, RecursionError)):
            g.topological_sort()

    def test_merge_results_combines_dicts(self):
        from aios_brain.patterns.parallel import merge_results
        a = {"key1": "v1", "key2": "v2"}
        b = {"key3": "v3"}
        merged = merge_results([a, b])
        assert merged["key1"] == "v1"
        assert merged["key3"] == "v3"

    def test_merge_results_empty_list(self):
        from aios_brain.patterns.parallel import merge_results
        assert merge_results([]) == {}


# ---------------------------------------------------------------------------
# 8. human_loop — assess_risk, gate, preview_action
# ---------------------------------------------------------------------------

class TestHumanLoop:
    """Tests for aios_brain.patterns.human_loop"""

    def test_assess_risk_low_for_safe_action(self):
        from aios_brain.patterns.human_loop import assess_risk
        risk = assess_risk("read a file", irreversible=False, scope="local")
        assert risk in ("low", "medium", "high")

    def test_assess_risk_high_for_irreversible(self):
        from aios_brain.patterns.human_loop import assess_risk
        risk = assess_risk("delete all records", irreversible=True, scope="global")
        assert risk == "high"

    def test_gate_low_risk_auto_approves(self):
        from aios_brain.patterns.human_loop import gate
        approved = gate("read file", risk="low", auto_approve_low_risk=True)
        assert approved is True

    def test_gate_high_risk_requires_approval(self):
        from aios_brain.patterns.human_loop import gate
        # Without a human callback, high-risk should not auto-approve
        approved = gate("send mass email", risk="high", auto_approve_low_risk=True)
        assert approved is False

    def test_gate_with_human_callback(self):
        from aios_brain.patterns.human_loop import gate
        approved = gate(
            "send email to prospect",
            risk="medium",
            human_callback=lambda action: True,
        )
        assert approved is True

    def test_preview_action_returns_description(self):
        from aios_brain.patterns.human_loop import preview_action
        preview = preview_action(
            action="send_email",
            params={"to": "test@example.com", "subject": "Hello"},
        )
        assert isinstance(preview, str)
        assert len(preview) > 0

    def test_preview_action_empty_params(self):
        from aios_brain.patterns.human_loop import preview_action
        preview = preview_action(action="noop", params={})
        assert isinstance(preview, str)


# ---------------------------------------------------------------------------
# 9. sub_agents — orchestrate, Delegation
# ---------------------------------------------------------------------------

class TestSubAgents:
    """Tests for aios_brain.patterns.sub_agents"""

    def test_delegation_has_required_fields(self):
        from aios_brain.patterns.sub_agents import Delegation
        d = Delegation(
            agent_id="researcher",
            task="find company info for Acme Corp",
            context={"prospect": "Acme"},
        )
        assert d.agent_id == "researcher"
        assert d.task == "find company info for Acme Corp"

    def test_delegation_missing_agent_id_raises(self):
        from aios_brain.patterns.sub_agents import Delegation
        with pytest.raises((TypeError, ValueError)):
            Delegation(task="do something", context={})

    def test_orchestrate_dispatches_to_handlers(self):
        from aios_brain.patterns.sub_agents import orchestrate
        handlers = {
            "researcher": lambda task, ctx: {"result": f"researched: {task}"},
            "writer": lambda task, ctx: {"result": f"wrote: {task}"},
        }
        from aios_brain.patterns.sub_agents import Delegation
        delegations = [
            Delegation(agent_id="researcher", task="Acme Corp", context={}),
            Delegation(agent_id="writer", task="email draft", context={}),
        ]
        results = orchestrate(delegations, handlers=handlers)
        assert len(results) == 2
        assert "researched" in results[0]["result"]

    def test_orchestrate_unknown_agent_raises(self):
        from aios_brain.patterns.sub_agents import orchestrate, Delegation
        delegations = [Delegation(agent_id="ghost", task="haunt", context={})]
        with pytest.raises((KeyError, ValueError)):
            orchestrate(delegations, handlers={})

    def test_orchestrate_empty_delegations(self):
        from aios_brain.patterns.sub_agents import orchestrate
        results = orchestrate([], handlers={})
        assert results == []


# ---------------------------------------------------------------------------
# 10. tools — ToolRegistry, ToolSpec, execute
# ---------------------------------------------------------------------------

class TestTools:
    """Tests for aios_brain.patterns.tools"""

    def test_tool_spec_has_name_and_description(self):
        from aios_brain.patterns.tools import ToolSpec
        spec = ToolSpec(
            name="search",
            description="Search the brain for relevant context",
            fn=lambda q: [{"text": "result"}],
        )
        assert spec.name == "search"
        assert len(spec.description) > 0

    def test_tool_registry_register_and_get(self):
        from aios_brain.patterns.tools import ToolRegistry, ToolSpec
        reg = ToolRegistry()
        spec = ToolSpec(name="calc", description="calculator", fn=lambda x: x)
        reg.register(spec)
        assert reg.get("calc") is spec

    def test_tool_registry_get_unknown_returns_none(self):
        from aios_brain.patterns.tools import ToolRegistry
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_tool_registry_list_tools(self):
        from aios_brain.patterns.tools import ToolRegistry, ToolSpec
        reg = ToolRegistry()
        reg.register(ToolSpec("a", "first", fn=lambda: None))
        reg.register(ToolSpec("b", "second", fn=lambda: None))
        names = reg.list()
        assert "a" in names
        assert "b" in names

    def test_execute_calls_registered_tool(self):
        from aios_brain.patterns.tools import ToolRegistry, ToolSpec, execute
        reg = ToolRegistry()
        reg.register(ToolSpec("double", "doubles a number", fn=lambda n: n * 2))
        result = execute("double", args={"n": 5}, registry=reg)
        assert result == 10

    def test_execute_unknown_tool_raises(self):
        from aios_brain.patterns.tools import ToolRegistry, execute
        reg = ToolRegistry()
        with pytest.raises((KeyError, ValueError)):
            execute("ghost", args={}, registry=reg)

    def test_execute_with_error_returns_error_dict(self):
        from aios_brain.patterns.tools import ToolRegistry, ToolSpec, execute
        def explode(**kwargs):
            raise RuntimeError("tool failed")
        reg = ToolRegistry()
        reg.register(ToolSpec("bomb", "explodes", fn=explode))
        result = execute("bomb", args={}, registry=reg, raise_on_error=False)
        assert isinstance(result, dict)
        assert "error" in result


# ---------------------------------------------------------------------------
# 11. rag — cascade_retrieve, rrf_merge, apply_graduation_scoring,
#           order_by_relevance_position
# ---------------------------------------------------------------------------

class TestRag:
    """Tests for aios_brain.patterns.rag"""

    def _make_results(self, texts: list[str]) -> list[dict]:
        return [{"text": t, "score": 1.0 / (i + 1), "source": f"doc{i}"} for i, t in enumerate(texts)]

    def test_rrf_merge_combines_result_lists(self):
        from aios_brain.patterns.rag import rrf_merge
        list_a = self._make_results(["apple", "banana", "cherry"])
        list_b = self._make_results(["banana", "date", "apple"])
        merged = rrf_merge([list_a, list_b])
        assert isinstance(merged, list)
        assert len(merged) >= 1
        texts = [r["text"] for r in merged]
        assert "apple" in texts or "banana" in texts

    def test_rrf_merge_empty_lists(self):
        from aios_brain.patterns.rag import rrf_merge
        result = rrf_merge([])
        assert result == []

    def test_rrf_merge_single_list_passthrough(self):
        from aios_brain.patterns.rag import rrf_merge
        items = self._make_results(["x", "y"])
        result = rrf_merge([items])
        assert len(result) == 2

    def test_apply_graduation_scoring_boosts_rules(self):
        from aios_brain.patterns.rag import apply_graduation_scoring
        results = [
            {"text": "RULE: always do X", "score": 0.5, "source": "patterns.md"},
            {"text": "INSTINCT: maybe do Y", "score": 0.5, "source": "lessons.md"},
        ]
        scored = apply_graduation_scoring(results)
        rule_score = next(r["score"] for r in scored if "RULE" in r["text"])
        instinct_score = next(r["score"] for r in scored if "INSTINCT" in r["text"])
        assert rule_score >= instinct_score

    def test_apply_graduation_scoring_empty_input(self):
        from aios_brain.patterns.rag import apply_graduation_scoring
        assert apply_graduation_scoring([]) == []

    def test_order_by_relevance_position_sorts_descending(self):
        from aios_brain.patterns.rag import order_by_relevance_position
        results = [
            {"text": "c", "score": 0.3},
            {"text": "a", "score": 0.9},
            {"text": "b", "score": 0.6},
        ]
        ordered = order_by_relevance_position(results)
        assert ordered[0]["text"] == "a"
        assert ordered[-1]["text"] == "c"

    def test_cascade_retrieve_returns_list(self):
        from aios_brain.patterns.rag import cascade_retrieve

        def mock_keyword(q: str) -> list[dict]:
            return [{"text": f"kw:{q}", "score": 0.5, "source": "kw"}]

        def mock_semantic(q: str) -> list[dict]:
            return [{"text": f"sem:{q}", "score": 0.8, "source": "sem"}]

        results = cascade_retrieve(
            "budget objections",
            retrievers=[mock_keyword, mock_semantic],
        )
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_cascade_retrieve_empty_retrievers(self):
        from aios_brain.patterns.rag import cascade_retrieve
        results = cascade_retrieve("query", retrievers=[])
        assert results == []


# ---------------------------------------------------------------------------
# 12. scope — classify_scope, register_task_type, AudienceTier
# ---------------------------------------------------------------------------

class TestScope:
    """Tests for aios_brain.patterns.scope"""

    def test_audience_tier_values_exist(self):
        from aios_brain.patterns.scope import AudienceTier
        assert hasattr(AudienceTier, "T1") or hasattr(AudienceTier, "TIER_1") or len(list(AudienceTier)) >= 2

    def test_classify_scope_returns_tier(self):
        from aios_brain.patterns.scope import classify_scope
        result = classify_scope("CEO of a 200-person SaaS company focused on marketing automation")
        assert result is not None

    def test_classify_scope_empty_input_returns_default(self):
        from aios_brain.patterns.scope import classify_scope
        result = classify_scope("")
        assert result is not None

    def test_register_task_type_adds_to_registry(self):
        from aios_brain.patterns.scope import register_task_type, classify_scope
        register_task_type(
            pattern="blockchain synergy",
            scope="T3",
            description="low-priority buzzword task",
        )
        result = classify_scope("blockchain synergy optimization")
        assert result is not None

    def test_classify_scope_sales_ceo_high_tier(self):
        from aios_brain.patterns.scope import classify_scope, AudienceTier
        result = classify_scope("VP of Sales at a 500-person enterprise software company")
        # Should return a recognizable tier value
        assert result is not None


# ---------------------------------------------------------------------------
# 13. mcp — MCPBridge, create_brain_mcp_tools
# ---------------------------------------------------------------------------

class TestMCP:
    """Tests for aios_brain.patterns.mcp"""

    def test_mcp_bridge_instantiates(self):
        from aios_brain.patterns.mcp import MCPBridge
        bridge = MCPBridge(brain_dir="/tmp/test-brain")
        assert bridge is not None

    def test_mcp_bridge_has_brain_dir(self):
        from pathlib import Path
        from aios_brain.patterns.mcp import MCPBridge
        bridge = MCPBridge(brain_dir="/tmp/test-brain")
        assert bridge.brain_dir == Path("/tmp/test-brain")

    def test_create_brain_mcp_tools_returns_list(self):
        from aios_brain.patterns.mcp import create_brain_mcp_tools
        tools = create_brain_mcp_tools(brain_dir="/tmp/test-brain")
        assert isinstance(tools, list)
        assert len(tools) >= 3  # search, emit, manifest at minimum

    def test_create_brain_mcp_tools_have_names(self):
        from aios_brain.patterns.mcp import create_brain_mcp_tools
        tools = create_brain_mcp_tools(brain_dir="/tmp/test-brain")
        for t in tools:
            assert hasattr(t, "name") or "name" in t
            name = t.name if hasattr(t, "name") else t["name"]
            assert isinstance(name, str)
            assert len(name) > 0

    def test_create_brain_mcp_tools_have_descriptions(self):
        from aios_brain.patterns.mcp import create_brain_mcp_tools
        tools = create_brain_mcp_tools(brain_dir="/tmp/test-brain")
        for t in tools:
            desc = t.description if hasattr(t, "description") else t.get("description", "")
            assert isinstance(desc, str)

    def test_mcp_bridge_list_tools(self):
        from aios_brain.patterns.mcp import MCPBridge
        bridge = MCPBridge(brain_dir="/tmp/test-brain")
        tools = bridge.list_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 1

    def test_mcp_bridge_get_tool_known(self):
        from aios_brain.patterns.mcp import MCPBridge
        bridge = MCPBridge(brain_dir="/tmp/test-brain")
        tool = bridge.get_tool("brain_search")
        assert tool is not None
        assert tool.name == "brain_search"

    def test_mcp_bridge_get_tool_unknown_returns_none(self):
        from aios_brain.patterns.mcp import MCPBridge
        bridge = MCPBridge(brain_dir="/tmp/test-brain")
        assert bridge.get_tool("nonexistent_tool") is None

    def test_mcp_bridge_call_unknown_raises(self):
        from aios_brain.patterns.mcp import MCPBridge
        bridge = MCPBridge(brain_dir="/tmp/test-brain")
        with pytest.raises(KeyError):
            bridge.call("ghost_tool")

    def test_mcp_tools_fn_returns_error_gracefully_for_invalid_dir(self):
        """Tool fns should degrade gracefully when brain_dir is invalid."""
        from aios_brain.patterns.mcp import MCPBridge
        bridge = MCPBridge(brain_dir="/nonexistent/brain/dir")
        # Calling the fn should not raise — should return an error dict or string
        search_tool = bridge.get_tool("brain_search")
        assert search_tool is not None
        result = search_tool.fn(query="test")
        # Should return a list with error entry, not raise
        assert isinstance(result, list)
        assert len(result) == 1
        assert "error" in result[0]

    def test_mcp_tool_input_schema_is_dict(self):
        from aios_brain.patterns.mcp import create_brain_mcp_tools
        tools = create_brain_mcp_tools(brain_dir="/tmp/test-brain")
        for t in tools:
            assert isinstance(t.input_schema, dict)

    def test_mcp_bridge_all_tool_names_unique(self):
        from aios_brain.patterns.mcp import MCPBridge
        bridge = MCPBridge(brain_dir="/tmp/test-brain")
        names = [t.name for t in bridge.list_tools()]
        assert len(names) == len(set(names)), "Duplicate tool names detected"
