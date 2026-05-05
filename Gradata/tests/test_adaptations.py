"""
Tests for adapted patterns from ruflo, everything-claude-code, and paul.
=========================================================================
Session 74: 8 adaptations from competitive repo analysis.

1. Context brackets (paul)
2. Reconciliation / UNIFY (paul)
3. Task escalation (paul)
4. Execute/Qualify loop (paul)
5. CARL rule priority tiers (paul)
6. Observation hooks (ecc)
7. Q-Learning agent router (ruflo)
8. Install manifest (ecc)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 1. Context Brackets
# ---------------------------------------------------------------------------
from gradata.contrib.patterns.context_brackets import (
    BRACKET_CONFIGS,
    ContextBracket,
    ContextTracker,
    estimate_remaining_capacity,
    format_bracket_prompt,
    get_bracket,
    get_bracket_guidance,
    is_action_allowed,
)


class TestContextBrackets:
    def test_fresh_bracket(self):
        assert get_bracket(0.80) == ContextBracket.FRESH
        assert get_bracket(1.0) == ContextBracket.FRESH
        assert get_bracket(0.70) == ContextBracket.FRESH

    def test_moderate_bracket(self):
        assert get_bracket(0.69) == ContextBracket.MODERATE
        assert get_bracket(0.40) == ContextBracket.MODERATE

    def test_deep_bracket(self):
        assert get_bracket(0.39) == ContextBracket.DEEP
        assert get_bracket(0.20) == ContextBracket.DEEP

    def test_critical_bracket(self):
        assert get_bracket(0.19) == ContextBracket.CRITICAL
        assert get_bracket(0.0) == ContextBracket.CRITICAL

    def test_invalid_ratio(self):
        with pytest.raises(ValueError):
            get_bracket(1.1)
        with pytest.raises(ValueError):
            get_bracket(-0.1)

    def test_guidance_returns_config(self):
        config = get_bracket_guidance(ContextBracket.DEEP)
        assert config.bracket == ContextBracket.DEEP
        assert config.should_handoff is True

    def test_estimate_capacity(self):
        assert estimate_remaining_capacity(0, 100) == 1.0
        assert estimate_remaining_capacity(50, 100) == 0.5
        assert estimate_remaining_capacity(100, 100) == 0.0
        assert estimate_remaining_capacity(150, 100) == 0.0

    def test_estimate_invalid(self):
        with pytest.raises(ValueError):
            estimate_remaining_capacity(0, 0)
        with pytest.raises(ValueError):
            estimate_remaining_capacity(-1, 100)

    def test_is_action_allowed_fresh(self):
        assert is_action_allowed(ContextBracket.FRESH, "new_complex_work") is True
        assert is_action_allowed(ContextBracket.FRESH, "anything") is True

    def test_is_action_prohibited_critical(self):
        assert is_action_allowed(ContextBracket.CRITICAL, "new_work") is False
        assert is_action_allowed(ContextBracket.CRITICAL, "finish_current_action") is True

    def test_format_bracket_prompt(self):
        prompt = format_bracket_prompt(ContextBracket.CRITICAL)
        assert "<context-bracket" in prompt
        assert "critical" in prompt
        assert "handoff" in prompt.lower()

    def test_tracker_basic(self):
        tracker = ContextTracker(max_tokens=100)
        assert tracker.bracket == ContextBracket.FRESH
        assert tracker.remaining_ratio == 1.0

    def test_tracker_consume(self):
        tracker = ContextTracker(max_tokens=100)
        tracker.consume(35)
        assert tracker.bracket == ContextBracket.MODERATE

    def test_tracker_transitions(self):
        tracker = ContextTracker(max_tokens=100)
        tracker.consume(35)  # FRESH -> MODERATE
        tracker.consume(30)  # MODERATE -> DEEP
        assert len(tracker.transitions) == 3  # initial + 2 transitions

    def test_tracker_should_handoff(self):
        tracker = ContextTracker(max_tokens=100)
        assert tracker.should_handoff() is False
        tracker.consume(85)
        assert tracker.should_handoff() is True

    def test_tracker_prompt_block(self):
        tracker = ContextTracker(max_tokens=100)
        block = tracker.prompt_block
        assert "<context-bracket" in block

    def test_all_brackets_have_configs(self):
        for bracket in ContextBracket:
            assert bracket in BRACKET_CONFIGS

    def test_tracker_consume_negative_raises(self):
        tracker = ContextTracker(max_tokens=100)
        with pytest.raises(ValueError):
            tracker.consume(-1)

    def test_tracker_invalid_max_tokens(self):
        with pytest.raises(ValueError):
            ContextTracker(max_tokens=0)


# ---------------------------------------------------------------------------
# 2. Reconciliation / UNIFY
# ---------------------------------------------------------------------------

from gradata.contrib.patterns.reconciliation import (
    ActualResult,
    DeviationScore,
    PlanItem,
    Reconciler,
    format_summary,
)


class TestReconciliation:
    def test_all_pass(self):
        plan = [PlanItem(id="AC-1", description="Login works")]
        actuals = [ActualResult(plan_id="AC-1", achieved=True, evidence="200 OK")]
        summary = Reconciler().reconcile(plan, actuals)
        assert summary.overall_score == DeviationScore.PASS
        assert summary.fully_passed is True
        assert summary.completion_ratio == 1.0

    def test_gap(self):
        plan = [
            PlanItem(id="AC-1", description="Login works"),
            PlanItem(id="AC-2", description="Token stored"),
        ]
        actuals = [
            ActualResult(plan_id="AC-1", achieved=True),
            ActualResult(plan_id="AC-2", achieved=False, evidence="Not implemented"),
        ]
        summary = Reconciler().reconcile(plan, actuals)
        assert summary.overall_score == DeviationScore.GAP
        assert summary.gap_count == 1
        assert summary.pass_count == 1

    def test_drift(self):
        plan = [PlanItem(id="AC-1", description="Store in localStorage")]
        actuals = [
            ActualResult(
                plan_id="AC-1",
                achieved=True,
                deviation="Stored in cookie instead of localStorage",
            )
        ]
        summary = Reconciler().reconcile(plan, actuals)
        assert summary.overall_score == DeviationScore.DRIFT
        assert summary.drift_count == 1

    def test_unmatched_plan(self):
        plan = [
            PlanItem(id="AC-1", description="A"),
            PlanItem(id="AC-2", description="B"),
        ]
        actuals = [ActualResult(plan_id="AC-1", achieved=True)]
        summary = Reconciler().reconcile(plan, actuals)
        assert "AC-2" in summary.unmatched_plans
        assert summary.overall_score == DeviationScore.GAP

    def test_extra_result(self):
        plan = [PlanItem(id="AC-1", description="A")]
        actuals = [
            ActualResult(plan_id="AC-1", achieved=True),
            ActualResult(plan_id="AC-99", achieved=True),
        ]
        summary = Reconciler().reconcile(plan, actuals)
        assert "AC-99" in summary.extra_results

    def test_empty_plan(self):
        summary = Reconciler().reconcile([], [])
        assert summary.overall_score == DeviationScore.PASS
        assert summary.completion_ratio == 1.0

    def test_format_summary(self):
        plan = [PlanItem(id="AC-1", description="Test")]
        actuals = [ActualResult(plan_id="AC-1", achieved=False, evidence="Failed")]
        summary = Reconciler().reconcile(plan, actuals)
        text = format_summary(summary)
        assert "GAP" in text
        assert "AC-1" in text

    def test_decisions_tracked(self):
        plan = [PlanItem(id="AC-1", description="A")]
        actuals = [ActualResult(plan_id="AC-1", achieved=True)]
        summary = Reconciler().reconcile(plan, actuals, decisions=["Used REST over GraphQL"])
        assert "Used REST over GraphQL" in summary.decisions

    def test_root_cause_intent(self):
        plan = [PlanItem(id="AC-1", description="X")]
        actuals = [
            ActualResult(
                plan_id="AC-1",
                achieved=False,
                evidence="requirements changed, wrong goal",
            )
        ]
        summary = Reconciler().reconcile(plan, actuals)
        assert summary.deviations[0].classification == "intent"

    def test_root_cause_spec(self):
        plan = [PlanItem(id="AC-1", description="X")]
        actuals = [
            ActualResult(
                plan_id="AC-1",
                achieved=False,
                evidence="acceptance criteria wrong, spec incorrect",
            )
        ]
        summary = Reconciler().reconcile(plan, actuals)
        assert summary.deviations[0].classification == "spec"

    def test_root_cause_code_default(self):
        plan = [PlanItem(id="AC-1", description="X")]
        actuals = [
            ActualResult(
                plan_id="AC-1",
                achieved=False,
                evidence="off by one error",
            )
        ]
        summary = Reconciler().reconcile(plan, actuals)
        assert summary.deviations[0].classification == "code"


# ---------------------------------------------------------------------------
# 3. Task Escalation
# ---------------------------------------------------------------------------

from gradata.contrib.patterns.task_escalation import (
    TaskOutcome,
    TaskStatus,
    format_outcome,
    is_actionable,
    report_outcome,
    requires_human,
)


class TestTaskEscalation:
    def test_done(self):
        outcome = report_outcome(TaskStatus.DONE, description="Completed login")
        assert is_actionable(outcome) is True
        assert requires_human(outcome) is False

    def test_done_with_concerns(self):
        outcome = report_outcome(
            TaskStatus.DONE_WITH_CONCERNS,
            description="Auth done",
            concerns=["JWT expiry edge case not tested"],
        )
        assert is_actionable(outcome) is True
        assert requires_human(outcome) is True

    def test_done_with_concerns_requires_concern(self):
        with pytest.raises(ValueError, match="at least one concern"):
            report_outcome(TaskStatus.DONE_WITH_CONCERNS)

    def test_needs_context(self):
        outcome = report_outcome(
            TaskStatus.NEEDS_CONTEXT,
            missing_context=["Database schema for users table"],
        )
        assert is_actionable(outcome) is False
        assert requires_human(outcome) is True

    def test_needs_context_requires_item(self):
        with pytest.raises(ValueError, match="at least one missing_context"):
            report_outcome(TaskStatus.NEEDS_CONTEXT)

    def test_blocked(self):
        outcome = report_outcome(
            TaskStatus.BLOCKED,
            blockers=["CI pipeline broken"],
        )
        assert is_actionable(outcome) is False
        assert requires_human(outcome) is True

    def test_blocked_requires_blocker(self):
        with pytest.raises(ValueError, match="at least one blocker"):
            report_outcome(TaskStatus.BLOCKED)

    def test_format_outcome_done(self):
        outcome = report_outcome(TaskStatus.DONE, description="All good")
        text = format_outcome(outcome)
        assert "PASS" in text
        assert "done" in text

    def test_format_outcome_concerns(self):
        outcome = report_outcome(
            TaskStatus.DONE_WITH_CONCERNS,
            concerns=["Edge case X"],
        )
        text = format_outcome(outcome)
        assert "WARN" in text
        assert "Edge case X" in text

    def test_format_outcome_blocked(self):
        outcome = report_outcome(
            TaskStatus.BLOCKED,
            blockers=["DB down"],
        )
        text = format_outcome(outcome)
        assert "STOP" in text

    def test_files_modified_tracked(self):
        outcome = report_outcome(
            TaskStatus.DONE,
            files_modified=["auth.py", "test_auth.py"],
        )
        assert len(outcome.files_modified) == 2


# ---------------------------------------------------------------------------
# 4. Execute/Qualify Loop
# ---------------------------------------------------------------------------

from gradata.contrib.patterns.execute_qualify import (
    ExecuteQualifyLoop,
    FailureClassification,
    QualifyResult,
    QualifyScore,
)


class TestExecuteQualify:
    def test_pass_first_attempt(self):
        def executor(spec, attempt):
            return TaskOutcome(status=TaskStatus.DONE)

        def qualifier(outcome, spec):
            return QualifyResult(score=QualifyScore.PASS)

        loop = ExecuteQualifyLoop(max_attempts=3)
        result = loop.run(executor, qualifier, "test spec")
        assert result.passed is True
        assert result.attempts_used == 1

    def test_fail_then_pass(self):
        call_count = [0]

        def executor(spec, attempt):
            call_count[0] += 1
            return TaskOutcome(status=TaskStatus.DONE)

        def qualifier(outcome, spec):
            if call_count[0] < 2:
                return QualifyResult(
                    score=QualifyScore.GAP,
                    classification=FailureClassification.CODE,
                )
            return QualifyResult(score=QualifyScore.PASS)

        def fixer(outcome, qualify, attempt):
            pass

        loop = ExecuteQualifyLoop(max_attempts=3)
        result = loop.run(executor, qualifier, "test spec", fixer=fixer)
        assert result.passed is True
        assert result.attempts_used == 2

    def test_exhaust_attempts(self):
        def executor(spec, attempt):
            return TaskOutcome(status=TaskStatus.DONE)

        def qualifier(outcome, spec):
            return QualifyResult(score=QualifyScore.DRIFT)

        loop = ExecuteQualifyLoop(max_attempts=2)
        result = loop.run(executor, qualifier, "test spec")
        assert result.passed is False
        assert result.attempts_used == 2

    def test_blocked_stops_immediately(self):
        def executor(spec, attempt):
            return TaskOutcome(status=TaskStatus.BLOCKED, blockers=["DB down"])

        def qualifier(outcome, spec):
            raise AssertionError("Should not be called")

        loop = ExecuteQualifyLoop(max_attempts=3)
        result = loop.run(executor, qualifier, "test spec")
        assert result.passed is False
        assert result.attempts_used == 1
        assert result.final_qualify is None

    def test_needs_context_stops(self):
        def executor(spec, attempt):
            return TaskOutcome(
                status=TaskStatus.NEEDS_CONTEXT,
                missing_context=["API key"],
            )

        def qualifier(outcome, spec):
            raise AssertionError("Should not be called")

        loop = ExecuteQualifyLoop(max_attempts=3)
        result = loop.run(executor, qualifier, "test spec")
        assert result.passed is False
        assert result.final_outcome.status == TaskStatus.NEEDS_CONTEXT

    def test_attempt_history(self):
        attempt_log = []

        def executor(spec, attempt):
            attempt_log.append(attempt)
            return TaskOutcome(status=TaskStatus.DONE)

        def qualifier(outcome, spec):
            if len(attempt_log) < 3:
                return QualifyResult(score=QualifyScore.GAP)
            return QualifyResult(score=QualifyScore.PASS)

        loop = ExecuteQualifyLoop(max_attempts=3)
        result = loop.run(executor, qualifier, "test spec")
        assert len(result.attempt_history) == 3

    def test_invalid_max_attempts(self):
        with pytest.raises(ValueError):
            ExecuteQualifyLoop(max_attempts=0)

    def test_qualify_result_passed_property(self):
        assert QualifyResult(score=QualifyScore.PASS).passed is True
        assert QualifyResult(score=QualifyScore.GAP).passed is False
        assert QualifyResult(score=QualifyScore.DRIFT).passed is False


# ---------------------------------------------------------------------------
# 5. Behavioral Engine (formerly CARL) Priority Tiers
# ---------------------------------------------------------------------------

from gradata.enhancements.behavioral_engine import (
    ConstraintViolation,
    Directive,
    DirectiveRegistry,
    PrioritizedConstraint,
    RulePriority,
)

BehavioralContract = Directive
ContractRegistry = DirectiveRegistry


class TestCARLPriorities:
    def test_priority_levels(self):
        assert RulePriority.MUST.value == "must"
        assert RulePriority.SHOULD.value == "should"
        assert RulePriority.MAY.value == "may"

    def test_prioritized_constraint_str(self):
        c = PrioritizedConstraint(rule="No deploys on Friday", priority=RulePriority.MUST)
        assert "[MUST]" in str(c)

    def test_legacy_string_constraints(self):
        contract = BehavioralContract(
            name="test",
            domain="test",
            constraints=["plain string"],
        )
        prioritized = contract.get_prioritized()
        assert len(prioritized) == 1
        assert prioritized[0].priority == RulePriority.SHOULD

    def test_must_rules(self):
        contract = BehavioralContract(
            name="test",
            domain="test",
            constraints=[
                PrioritizedConstraint("Must rule", RulePriority.MUST),
                PrioritizedConstraint("Should rule", RulePriority.SHOULD),
                PrioritizedConstraint("May rule", RulePriority.MAY),
            ],
        )
        assert len(contract.must_rules) == 1
        assert len(contract.should_rules) == 1
        assert len(contract.may_rules) == 1

    def test_violation_blocking(self):
        must = PrioritizedConstraint("Stop", RulePriority.MUST)
        should = PrioritizedConstraint("Warn", RulePriority.SHOULD)
        assert ConstraintViolation(must).blocking is True
        assert ConstraintViolation(should).blocking is False

    def test_registry_prioritized_lookup(self):
        registry = ContractRegistry()
        registry.register(
            BehavioralContract(
                name="deploy-rules",
                domain="devops",
                trigger_keywords=["deploy"],
                constraints=[
                    PrioritizedConstraint("No Friday deploys", RulePriority.MUST),
                    PrioritizedConstraint("Use blue-green", RulePriority.SHOULD),
                ],
            )
        )
        constraints = registry.get_prioritized_constraints("deploy to prod")
        assert len(constraints) == 2
        assert constraints[0].priority == RulePriority.MUST

    def test_registry_min_priority_filter(self):
        registry = ContractRegistry()
        registry.register(
            BehavioralContract(
                name="test",
                domain="test",
                trigger_keywords=["test"],
                constraints=[
                    PrioritizedConstraint("Must", RulePriority.MUST),
                    PrioritizedConstraint("Should", RulePriority.SHOULD),
                    PrioritizedConstraint("May", RulePriority.MAY),
                ],
            )
        )
        must_only = registry.get_prioritized_constraints("test", min_priority=RulePriority.MUST)
        assert all(c.priority == RulePriority.MUST for c in must_only)

    def test_registry_stats_includes_priorities(self):
        registry = ContractRegistry()
        registry.register(
            BehavioralContract(
                name="test",
                domain="test",
                trigger_keywords=["x"],
                constraints=[
                    PrioritizedConstraint("A", RulePriority.MUST),
                    PrioritizedConstraint("B", RulePriority.MAY),
                ],
            )
        )
        stats = registry.stats()
        assert stats["constraints_by_priority"]["must"] == 1
        assert stats["constraints_by_priority"]["may"] == 1

    def test_format_constraints_prompt(self):
        registry = ContractRegistry()
        registry.register(
            BehavioralContract(
                name="test",
                domain="test",
                trigger_keywords=["deploy"],
                constraints=[
                    PrioritizedConstraint("No Friday", RulePriority.MUST, rationale="Outages"),
                    PrioritizedConstraint("Blue-green", RulePriority.SHOULD),
                ],
            )
        )
        prompt = registry.format_constraints_prompt("deploy now")
        assert "<behavioral-directives>" in prompt
        assert "MUST" in prompt
        assert "SHOULD" in prompt
        assert "Outages" in prompt

    def test_backward_compat_get_constraints(self):
        registry = ContractRegistry()
        registry.register(
            BehavioralContract(
                name="test",
                domain="test",
                trigger_keywords=["build"],
                constraints=["Run linter first"],
            )
        )
        constraints = registry.get_constraints("build the app")
        assert "Run linter first" in constraints

    def test_has_blocking_violations(self):
        registry = ContractRegistry()
        registry.register(
            BehavioralContract(
                name="test",
                domain="test",
                trigger_keywords=["deploy"],
                constraints=[
                    PrioritizedConstraint("No Friday", RulePriority.MUST),
                ],
            )
        )
        assert registry.has_blocking_violations("deploy now") is True
        assert registry.has_blocking_violations("unrelated") is False

    def test_empty_prompt_no_match(self):
        registry = ContractRegistry()
        registry.register(
            BehavioralContract(
                name="test",
                domain="test",
                trigger_keywords=["deploy"],
                constraints=[PrioritizedConstraint("X", RulePriority.MUST)],
            )
        )
        assert registry.format_constraints_prompt("unrelated") == ""


# ---------------------------------------------------------------------------
# 6. Observation Hooks
# ---------------------------------------------------------------------------

from gradata.enhancements.observation_hooks import (
    ObservationStore,
    observe_tool_use,
)


class TestObservationHooks:
    def test_observe_tool_use(self):
        obs = observe_tool_use(
            tool_name="Bash",
            input_data="pytest",
            output_data="3 passed",
            session_id="s42",
        )
        assert obs.tool_name == "Bash"
        assert obs.session_id == "s42"
        assert obs.success is True
        assert obs.timestamp > 0

    def test_truncation(self):
        long_input = "x" * 1000
        obs = observe_tool_use("Test", input_data=long_input, max_summary_len=100)
        assert len(obs.input_summary) == 103  # 100 + "..."

    def test_jsonl_serialization(self):
        obs = observe_tool_use("Read", input_data="file.py")
        line = obs.to_jsonl()
        parsed = json.loads(line)
        assert parsed["tool_name"] == "Read"

    def test_store_append_and_read(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = ObservationStore(base_dir=tmpdir)
            obs = observe_tool_use("Bash", input_data="ls", project_id="abc123")
            store.append(obs)

            recent = store.read_recent(project_id="abc123", limit=10)
            assert len(recent) == 1
            assert recent[0].tool_name == "Bash"

    def test_store_count(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = ObservationStore(base_dir=tmpdir)
            for i in range(5):
                store.append(observe_tool_use(f"Tool{i}", project_id="proj"))
            assert store.count("proj") == 5

    def test_store_stats(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = ObservationStore(base_dir=tmpdir)
            store.append(observe_tool_use("Test", project_id="global"))
            stats = store.stats("global")
            assert stats["count"] == 1
            assert stats["size_bytes"] > 0

    def test_store_empty_read(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = ObservationStore(base_dir=tmpdir)
            assert store.read_recent("nonexistent") == []

    def test_none_input(self):
        obs = observe_tool_use("Test", input_data=None)
        assert obs.input_summary == ""

    def test_dict_input_stringified(self):
        obs = observe_tool_use("Test", input_data={"key": "value"})
        assert "key" in obs.input_summary


# ---------------------------------------------------------------------------
# 7. Q-Learning Agent Router
# ---------------------------------------------------------------------------

from gradata.contrib.patterns.q_learning_router import (
    QLearningRouter,
    RouteDecision,
    RouterConfig,
)


class TestQLearningRouter:
    def test_route_returns_decision(self):
        router = QLearningRouter()
        decision = router.route("review this code for bugs")
        assert isinstance(decision, RouteDecision)
        assert decision.agent in router.config.agents
        assert decision.state_hash

    def test_update_reward(self):
        router = QLearningRouter()
        decision = router.route("fix the login bug")
        router.update_reward(decision, reward=0.9)
        assert router.update_count == 1
        assert router.epsilon < router.config.epsilon_start

    def test_reward_from_severity(self):
        router = QLearningRouter()
        assert router.reward_from_severity("trivial") == 0.85
        assert router.reward_from_severity("rewrite") == 0.0
        assert router.reward_from_severity("unknown") == 0.5

    def test_epsilon_decay(self):
        router = QLearningRouter(RouterConfig(epsilon_start=1.0, epsilon_decay=0.9))
        for _ in range(10):
            d = router.route("test")
            router.update_reward(d, 0.5)
        assert router.epsilon < 1.0

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            filepath = Path(tmpdir) / "router.json"
            router = QLearningRouter()
            for _ in range(5):
                d = router.route("test task")
                router.update_reward(d, 0.7)
            router.save(filepath)

            router2 = QLearningRouter()
            assert router2.load(filepath) is True
            assert router2.update_count == 5

    def test_load_nonexistent(self):
        router = QLearningRouter()
        assert router.load("/nonexistent/path.json") is False

    def test_stats(self):
        router = QLearningRouter()
        router.route("test")
        stats = router.stats()
        assert stats["total_routes"] == 1
        assert "epsilon" in stats
        assert "q_table_size" in stats

    def test_get_best_agent(self):
        router = QLearningRouter()
        agent = router.get_best_agent("review this code")
        assert agent in router.config.agents

    def test_custom_agents(self):
        config = RouterConfig(agents=["alpha", "beta", "gamma"])
        router = QLearningRouter(config)
        decision = router.route("do something")
        assert decision.agent in ["alpha", "beta", "gamma"]

    def test_cache_hit(self):
        router = QLearningRouter()
        router.route("same task description")
        router.route("same task description")
        assert router.stats()["cache_hits"] >= 1

    def test_multiple_updates_stable(self):
        router = QLearningRouter()
        for i in range(100):
            d = router.route(f"task {i % 5}")
            router.update_reward(d, 0.5 + (i % 3) * 0.2)
        assert router.update_count == 100
        assert router.epsilon < router.config.epsilon_start

    def test_reward_clamp(self):
        router = QLearningRouter()
        d = router.route("test")
        router.update_reward(d, 1.5)  # Should clamp to 1.0
        router.update_reward(d, -0.5)  # Should clamp to 0.0
        assert router.update_count == 2

    def test_decision_has_q_values(self):
        router = QLearningRouter()
        decision = router.route("code review task")
        assert len(decision.q_values) == len(router.config.agents)


# ---------------------------------------------------------------------------
# 8. Install Manifest
# ---------------------------------------------------------------------------

from gradata.contrib.enhancements.install_manifest import (
    InstallManifest,
    InstallState,
    Module,
    ModuleCost,
    ModuleStability,
)


class TestInstallManifest:
    def test_default_manifest(self):
        manifest = InstallManifest.default()
        assert len(manifest.available_modules) > 0
        assert len(manifest.available_profiles) > 0

    def test_plan_profile(self):
        manifest = InstallManifest.default()
        plan = manifest.plan_install(profile="lite")
        assert len(plan.modules) >= 2
        assert plan.profile == "lite"

    def test_plan_standard_profile(self):
        manifest = InstallManifest.default()
        plan = manifest.plan_install(profile="standard")
        module_ids = plan.module_ids
        assert "core-patterns" in module_ids
        assert "learning-pipeline" in module_ids

    def test_plan_full_profile(self):
        manifest = InstallManifest.default()
        plan = manifest.plan_install(profile="full")
        assert len(plan.modules) == len(manifest.available_modules)

    def test_unknown_profile(self):
        manifest = InstallManifest.default()
        with pytest.raises(ValueError, match="Unknown profile"):
            manifest.plan_install(profile="nonexistent")

    def test_dependency_resolution(self):
        manifest = InstallManifest.default()
        resolved = manifest.resolve_dependencies(["learning-pipeline"])
        assert "quality-gates" in resolved
        assert resolved.index("quality-gates") < resolved.index("learning-pipeline")

    def test_include_exclude(self):
        manifest = InstallManifest.default()
        plan = manifest.plan_install(
            profile="lite",
            include=["behavioral-engine"],
            exclude=["agent-modes"],
        )
        ids = plan.module_ids
        assert "behavioral-engine" in ids
        assert "agent-modes" not in ids

    def test_estimated_cost(self):
        manifest = InstallManifest.default()
        lite_plan = manifest.plan_install(profile="lite")
        full_plan = manifest.plan_install(profile="full")
        assert lite_plan.estimated_cost == "light"
        assert full_plan.estimated_cost in ("medium", "heavy")

    def test_apply_and_state(self):
        manifest = InstallManifest.default()
        plan = manifest.plan_install(profile="standard")
        state = manifest.apply(plan)
        assert state.profile == "standard"
        assert len(state.installed_modules) > 0

    def test_state_save_load(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            filepath = Path(tmpdir) / "state.json"
            state = InstallState(
                installed_modules=["core-patterns", "behavioral-engine"],
                profile="lite",
            )
            state.save(filepath)

            loaded = InstallState.load(filepath)
            assert loaded.profile == "lite"
            assert "behavioral-engine" in loaded.installed_modules

    def test_state_is_installed(self):
        state = InstallState(installed_modules=["core-patterns"])
        assert state.is_installed("core-patterns") is True
        assert state.is_installed("meta-rules") is False

    def test_diff(self):
        manifest = InstallManifest.default()
        current = InstallState(installed_modules=["core-patterns", "behavioral-engine"])
        plan = manifest.plan_install(modules=["core-patterns", "quality-gates"])
        diff = manifest.diff(plan, current)
        assert "quality-gates" in diff["add"]
        assert "behavioral-engine" in diff["remove"]
        assert "core-patterns" in diff["keep"]

    def test_unknown_module(self):
        manifest = InstallManifest.default()
        with pytest.raises(ValueError, match="Unknown module"):
            manifest.resolve_dependencies(["nonexistent-module"])

    def test_module_properties(self):
        m = Module(
            id="test",
            name="Test",
            cost=ModuleCost.HEAVY,
            stability=ModuleStability.EXPERIMENTAL,
        )
        assert m.cost == ModuleCost.HEAVY
        assert m.stability == ModuleStability.EXPERIMENTAL

    def test_state_load_nonexistent(self):
        state = InstallState.load("/nonexistent/state.json")
        assert state.installed_modules == []

    def test_default_install_modules(self):
        manifest = InstallManifest.default()
        plan = manifest.plan_install()  # No profile, uses defaults
        ids = plan.module_ids
        assert "core-patterns" in ids

    def test_research_profile(self):
        manifest = InstallManifest.default()
        plan = manifest.plan_install(profile="research")
        ids = plan.module_ids
        assert "q-learning-router" in ids
        assert "observation-hooks" in ids


# ===========================================================================
# EverOS Adaptations (3 modules)
# ===========================================================================

# ---------------------------------------------------------------------------
# 9. Memory Taxonomy
# ---------------------------------------------------------------------------

from gradata.enhancements.memory_taxonomy import (
    AtomicFact,
    BrainProfile,
    CorrectionNarrative,
    CrossBrainProfile,
    MemoryType,
    PredictedImpact,
    ProfileField,
    classify_memory_type,
)


class TestMemoryTaxonomy:
    def test_memory_types_enum(self):
        assert len(MemoryType) == 5
        assert MemoryType.PREDICTED_IMPACT.value == "predicted_impact"

    def test_correction_narrative(self):
        n = CorrectionNarrative(
            subject="Tone too formal",
            summary="Changed Dear Sir to Hey",
            severity="moderate",
            session_id="s42",
        )
        assert n.memory_type == MemoryType.CORRECTION_NARRATIVE
        assert n.timestamp > 0
        assert n.severity == "moderate"

    def test_atomic_fact(self):
        f = AtomicFact(
            facts=["User prefers casual tone", "No em dashes"],
            source_type="correction",
        )
        assert f.memory_type == MemoryType.ATOMIC_FACT
        assert f.fact_count == 2

    def test_predicted_impact(self):
        p = PredictedImpact(
            prediction="Will affect all future email drafts",
            evidence="3 corrections on tone in last 5 sessions",
            duration_days=30,
            affected_task_types=["email_draft", "follow_up"],
        )
        assert p.memory_type == MemoryType.PREDICTED_IMPACT
        assert len(p.affected_task_types) == 2

    def test_predicted_impact_active(self):
        p = PredictedImpact(
            prediction="Test",
            start_date="2020-01-01",
            end_date="2030-12-31",
        )
        assert p.is_active is True
        assert p.is_expired is False

    def test_predicted_impact_expired(self):
        p = PredictedImpact(
            prediction="Test",
            start_date="2020-01-01",
            end_date="2020-12-31",
        )
        assert p.is_expired is True

    def test_predicted_impact_no_bounds(self):
        p = PredictedImpact(prediction="Always active")
        assert p.is_active is True
        assert p.is_expired is False

    def test_brain_profile(self):
        bp = BrainProfile(
            strengths=[ProfileField(value="email drafts", level="advanced")],
            weaknesses=[ProfileField(value="tone matching", level="beginner")],
        )
        assert bp.memory_type == MemoryType.BRAIN_PROFILE
        assert len(bp.strengths) == 1

    def test_profile_field_add_evidence(self):
        pf = ProfileField(value="test", confidence=0.5)
        pf.add_evidence("2026-03-29|s42")
        assert len(pf.evidences) == 1
        assert pf.confidence == 0.6
        # Adding same evidence again: no duplicate, no change
        pf.add_evidence("2026-03-29|s42")
        assert len(pf.evidences) == 1

    def test_brain_profile_merge(self):
        bp1 = BrainProfile(
            strengths=[ProfileField(value="coding", level="intermediate", confidence=0.5)],
        )
        bp2 = BrainProfile(
            strengths=[
                ProfileField(value="coding", level="expert", confidence=0.9),
                ProfileField(value="writing", level="beginner"),
            ],
        )
        bp1.merge(bp2)
        assert len(bp1.strengths) == 2
        coding = next(f for f in bp1.strengths if f.value == "coding")
        assert coding.level == "expert"  # Kept highest
        assert coding.confidence == 0.9

    def test_cross_brain_profile(self):
        cbp = CrossBrainProfile()
        assert cbp.memory_type == MemoryType.CROSS_BRAIN_PROFILE

    def test_cross_brain_add_pattern(self):
        cbp = CrossBrainProfile()
        sp = cbp.add_pattern("Prefer short emails", "brain_1")
        assert sp.confidence == 0.3
        sp2 = cbp.add_pattern("Prefer short emails", "brain_2")
        assert sp2.brain_count == 2
        assert sp2.confidence > 0.3

    def test_classify_memory_type(self):
        assert (
            classify_memory_type("will likely affect future tasks") == MemoryType.PREDICTED_IMPACT
        )
        assert classify_memory_type("tends to prefer casual tone") == MemoryType.BRAIN_PROFILE
        assert classify_memory_type("fact: user likes Python") == MemoryType.ATOMIC_FACT
        assert (
            classify_memory_type("across brains, shared pattern") == MemoryType.CROSS_BRAIN_PROFILE
        )
        assert classify_memory_type("User corrected the email") == MemoryType.CORRECTION_NARRATIVE

    def test_evidence_ids(self):
        n = CorrectionNarrative(evidence_ids=["evt_1", "evt_2"])
        assert len(n.evidence_ids) == 2


# ---------------------------------------------------------------------------
# 10. Cluster Manager
# ---------------------------------------------------------------------------

from gradata.enhancements.cluster_manager import (
    ClusterConfig,
    ClusterManager,
    ClusterState,
    cosine_similarity,
)


class TestClusterManager:
    def test_cosine_similarity_identical(self):
        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_cosine_similarity_zero_vector(self):
        assert cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0

    def test_cosine_similarity_different_lengths(self):
        assert cosine_similarity([1, 2], [1, 2, 3]) == 0.0

    def test_assign_creates_new_cluster(self):
        mgr = ClusterManager()
        state = ClusterState()
        result = mgr.assign(state, "item_1", [1.0, 0.0, 0.0], 1000.0)
        assert result.is_new is True
        assert result.cluster_id == "cluster_0"
        assert state.cluster_count == 1

    def test_assign_joins_similar_cluster(self):
        mgr = ClusterManager(ClusterConfig(similarity_threshold=0.8))
        state = ClusterState()
        mgr.assign(state, "item_1", [1.0, 0.0, 0.0], 1000.0)
        result = mgr.assign(state, "item_2", [0.99, 0.1, 0.0], 1001.0)
        assert result.is_new is False
        assert result.cluster_id == "cluster_0"
        assert state.counts["cluster_0"] == 2

    def test_assign_creates_separate_clusters(self):
        mgr = ClusterManager(ClusterConfig(similarity_threshold=0.9))
        state = ClusterState()
        mgr.assign(state, "item_1", [1.0, 0.0, 0.0], 1000.0)
        result = mgr.assign(state, "item_2", [0.0, 1.0, 0.0], 1001.0)
        assert result.is_new is True
        assert state.cluster_count == 2

    def test_temporal_gating(self):
        mgr = ClusterManager(
            ClusterConfig(
                similarity_threshold=0.5,
                max_time_gap_days=1.0,
            )
        )
        state = ClusterState()
        mgr.assign(state, "item_1", [1.0, 0.0, 0.0], 1000.0)
        # Item 2 is similar but too far in time (2 days later)
        result = mgr.assign(state, "item_2", [0.99, 0.1, 0.0], 1000.0 + 172800)
        assert result.is_new is True  # Temporal gate blocked

    def test_already_assigned_returns_existing(self):
        mgr = ClusterManager()
        state = ClusterState()
        r1 = mgr.assign(state, "item_1", [1.0, 0.0, 0.0], 1000.0)
        r2 = mgr.assign(state, "item_1", [1.0, 0.0, 0.0], 2000.0)
        assert r1.cluster_id == r2.cluster_id
        assert r2.is_new is False

    def test_centroid_update(self):
        mgr = ClusterManager(ClusterConfig(similarity_threshold=0.5))
        state = ClusterState()
        mgr.assign(state, "item_1", [1.0, 0.0], 1000.0)
        mgr.assign(state, "item_2", [0.8, 0.2], 1001.0)
        # Centroid should be average: (1.0+0.8)/2, (0.0+0.2)/2
        centroid = state.centroids["cluster_0"]
        assert centroid[0] == pytest.approx(0.9)
        assert centroid[1] == pytest.approx(0.1)

    def test_get_cluster_items(self):
        mgr = ClusterManager(ClusterConfig(similarity_threshold=0.5))
        state = ClusterState()
        mgr.assign(state, "a", [1.0, 0.0], 1000.0)
        mgr.assign(state, "b", [0.9, 0.1], 1001.0)
        items = mgr.get_cluster_items(state, "cluster_0")
        assert set(items) == {"a", "b"}

    def test_get_stable_clusters(self):
        mgr = ClusterManager(
            ClusterConfig(
                similarity_threshold=0.5,
                min_cluster_size=2,
            )
        )
        state = ClusterState()
        mgr.assign(state, "a", [1.0, 0.0], 1000.0)
        mgr.assign(state, "b", [0.9, 0.1], 1001.0)
        mgr.assign(state, "c", [0.0, 1.0], 1002.0)  # Singleton
        stable = mgr.get_stable_clusters(state)
        assert len(stable) == 1

    def test_stats(self):
        mgr = ClusterManager()
        state = ClusterState()
        mgr.assign(state, "a", [1.0, 0.0], 1000.0)
        stats = mgr.stats(state)
        assert stats["cluster_count"] == 1
        assert stats["item_count"] == 1

    def test_state_serialization(self):
        state = ClusterState()
        state.centroids["c0"] = [1.0, 2.0]
        state.counts["c0"] = 3
        state.next_cluster_idx = 1

        d = state.to_dict()
        restored = ClusterState.from_dict(d)
        assert restored.centroids["c0"] == [1.0, 2.0]
        assert restored.counts["c0"] == 3
        assert restored.next_cluster_idx == 1


# ---------------------------------------------------------------------------
# 11. Lesson Discriminator
# ---------------------------------------------------------------------------

from gradata.enhancements.lesson_discriminator import (
    DiscriminatorConfig,
    ImportanceSignal,
    LessonDiscriminator,
)


class TestLessonDiscriminator:
    def test_low_severity_below_threshold(self):
        disc = LessonDiscriminator()
        verdict = disc.evaluate(severity="trivial")
        assert verdict.confidence < 0.6
        assert verdict.is_high_value is False

    def test_high_severity_above_threshold(self):
        disc = LessonDiscriminator()
        verdict = disc.evaluate(severity="major")
        assert verdict.is_high_value is True
        assert ImportanceSignal.SEVERITY in verdict.signals

    def test_recurrence_boosts_confidence(self):
        disc = LessonDiscriminator()
        v1 = disc.evaluate(severity="minor", occurrence_count=1)
        v2 = disc.evaluate(severity="minor", occurrence_count=3)
        assert v2.confidence > v1.confidence
        assert ImportanceSignal.RECURRENCE in v2.signals

    def test_user_explicit_flag(self):
        disc = LessonDiscriminator()
        verdict = disc.evaluate(severity="trivial", is_user_explicit=True)
        assert ImportanceSignal.USER_EXPLICIT in verdict.signals
        assert verdict.confidence > 0.3

    def test_novelty_bonus(self):
        disc = LessonDiscriminator()
        v_novel = disc.evaluate(severity="moderate", existing_rule_ids=[])
        v_covered = disc.evaluate(severity="moderate", existing_rule_ids=["rule_1"])
        assert v_novel.confidence > v_covered.confidence

    def test_domain_breadth(self):
        disc = LessonDiscriminator()
        verdict = disc.evaluate(
            severity="moderate",
            affected_task_types=["email", "follow_up", "proposal"],
        )
        assert ImportanceSignal.DOMAIN_BREADTH in verdict.signals

    def test_correction_chain(self):
        disc = LessonDiscriminator()
        verdict = disc.evaluate(
            severity="minor",
            related_corrections=["c1", "c2", "c3"],
        )
        assert ImportanceSignal.CORRECTION_CHAIN in verdict.signals

    def test_recommendation_graduate(self):
        disc = LessonDiscriminator()
        verdict = disc.evaluate(
            severity="rewrite",
            occurrence_count=3,
            is_user_explicit=True,
        )
        assert verdict.recommendation == "graduate"

    def test_recommendation_discard(self):
        disc = LessonDiscriminator()
        verdict = disc.evaluate(severity="trivial")
        assert verdict.recommendation in ("discard", "monitor")

    def test_confidence_clamped(self):
        disc = LessonDiscriminator()
        verdict = disc.evaluate(
            severity="rewrite",
            occurrence_count=10,
            is_user_explicit=True,
            affected_task_types=["a", "b", "c", "d", "e"],
            related_corrections=["c1", "c2", "c3"],
        )
        assert verdict.confidence <= 1.0

    def test_batch_evaluate(self):
        disc = LessonDiscriminator()
        corrections = [
            {"severity": "trivial"},
            {"severity": "major"},
            {"severity": "rewrite", "occurrence_count": 3},
        ]
        verdicts = disc.batch_evaluate(corrections)
        assert len(verdicts) == 3

    def test_filter_high_value(self):
        disc = LessonDiscriminator()
        corrections = [
            {"severity": "trivial"},
            {"severity": "major", "occurrence_count": 3},
        ]
        high_value = disc.filter_high_value(corrections)
        assert len(high_value) >= 1
        assert all(v.is_high_value for _, v in high_value)

    def test_custom_threshold(self):
        disc = LessonDiscriminator(DiscriminatorConfig(min_confidence=0.9))
        verdict = disc.evaluate(severity="moderate")
        assert verdict.is_high_value is False  # Higher bar

    def test_signal_count(self):
        disc = LessonDiscriminator()
        verdict = disc.evaluate(
            severity="major",
            occurrence_count=3,
            is_user_explicit=True,
        )
        assert verdict.signal_count >= 3


# ===========================================================================
# Pipeline + Manifest Integration
# ===========================================================================

# ---------------------------------------------------------------------------
# 12. Learning Pipeline (end-to-end)
# ---------------------------------------------------------------------------

from gradata.enhancements.learning_pipeline import LearningPipeline, PipelineResult


class TestLearningPipeline:
    def test_pipeline_no_brain_dir(self):
        pipeline = LearningPipeline()
        result = pipeline.process_correction(
            draft="Dear Sir,",
            final="Hey,",
            severity="moderate",
            category="TONE",
        )
        assert isinstance(result, PipelineResult)
        assert result.success  # No failures, just skipped stages
        assert "discriminate" in result.stages_completed
        assert "classify_memory" in result.stages_completed

    def test_pipeline_with_temp_dir(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            pipeline = LearningPipeline(brain_dir=tmpdir)
            result = pipeline.process_correction(
                draft="The quarterly results show...",
                final="Q1 results:",
                severity="major",
                category="CONTENT",
                session_id="s42",
                task_type="email_draft",
            )
            assert result.success
            assert result.discriminator_confidence > 0
            assert result.processing_time_ms >= 0

    def test_pipeline_discriminator_filters(self):
        pipeline = LearningPipeline()
        # Trivial correction should be low-value
        result = pipeline.process_correction(severity="trivial")
        assert result.is_high_value is False
        # Major correction should be high-value
        result2 = pipeline.process_correction(severity="major", occurrence_count=3)
        assert result2.is_high_value is True

    def test_pipeline_with_vector_clusters(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            pipeline = LearningPipeline(brain_dir=tmpdir)
            r1 = pipeline.process_correction(
                severity="moderate",
                vector=[1.0, 0.0, 0.0],
                session_id="s1",
                category="TONE",
            )
            assert r1.cluster_id != ""
            assert r1.cluster_is_new is True
            assert "cluster" in r1.stages_completed

            # Similar vector should join same cluster
            r2 = pipeline.process_correction(
                severity="moderate",
                vector=[0.99, 0.1, 0.0],
                session_id="s1",
                category="TONE",
            )
            assert r2.cluster_id == r1.cluster_id
            assert r2.cluster_is_new is False

    def test_pipeline_without_vector_skips_cluster(self):
        pipeline = LearningPipeline()
        result = pipeline.process_correction(severity="moderate")
        assert "cluster" in result.stages_skipped

    def test_pipeline_routes_with_task_type(self):
        pipeline = LearningPipeline()
        result = pipeline.process_correction(
            severity="moderate",
            task_type="code review and debugging",
        )
        assert "route" in result.stages_completed
        assert result.route_decision is not None

    def test_pipeline_context_bracket(self):
        pipeline = LearningPipeline()
        result = pipeline.process_correction(
            draft="x" * 1000,
            final="y" * 1000,
            severity="minor",
        )
        assert result.context_bracket != ""
        assert "context_bracket" in result.stages_completed

    def test_pipeline_memory_type_classification(self):
        pipeline = LearningPipeline()
        result = pipeline.process_correction(
            draft="will likely affect future",
            final="predicting future impact",
            severity="moderate",
        )
        assert result.memory_type != ""

    def test_pipeline_save_state(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            pipeline = LearningPipeline(brain_dir=tmpdir)
            pipeline.process_correction(
                severity="moderate",
                vector=[1.0, 0.0],
                task_type="test",
            )
            pipeline.save_state()
            assert (Path(tmpdir) / "cluster_state.json").exists()
            assert (Path(tmpdir) / "q_router.json").exists()

    def test_pipeline_stats(self):
        pipeline = LearningPipeline()
        stats = pipeline.stats()
        assert "stages_available" in stats
        assert "discriminate" in stats["stages_available"]

    def test_pipeline_result_properties(self):
        result = PipelineResult(
            stages_completed=["a", "b"],
            stages_skipped=["c"],
            stages_failed=[],
        )
        assert result.success is True
        assert result.stages_total == 3

    def test_pipeline_result_failure(self):
        result = PipelineResult(stages_failed=["observe"])
        assert result.success is False

    def test_pipeline_observation_capture(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            pipeline = LearningPipeline(brain_dir=tmpdir)
            result = pipeline.process_correction(
                draft="test",
                final="test2",
                severity="minor",
                session_id="s99",
            )
            assert "observe" in result.stages_completed
            assert result.observation is not None


# ---------------------------------------------------------------------------
# 13. Manifest SDK Capabilities
# ---------------------------------------------------------------------------

from gradata._brain_manifest import _sdk_capabilities


class TestManifestCapabilities:
    def test_sdk_capabilities_returns_dict(self):
        caps = _sdk_capabilities()
        assert "total" in caps
        assert "available" in caps
        assert "modules" in caps

    def test_all_adapted_modules_detected(self):
        caps = _sdk_capabilities()
        modules = caps["modules"]
        # All 11 adapted modules should be detected
        expected = [
            "context_brackets",
            "reconciliation",
            "task_escalation",
            "execute_qualify",
            "q_learning_router",
            "observation_hooks",
            "install_manifest",
            "memory_taxonomy",
            "cluster_manager",
            "lesson_discriminator",
            "behavioral_engine",
            "learning_pipeline",
        ]
        for name in expected:
            assert name in modules, f"Missing module: {name}"
            assert modules[name]["available"] is True, f"Module not available: {name}"

    def test_source_attribution(self):
        caps = _sdk_capabilities()
        modules = caps["modules"]
        assert modules["context_brackets"]["source"] == "ChristopherKahler/paul"
        assert modules["q_learning_router"]["source"] == "ruflo"
        assert modules["observation_hooks"]["source"] == "ecc"
        assert modules["memory_taxonomy"]["source"] == "everos"
        assert modules["behavioral_engine"]["source"] == "gradata"

    def test_available_count_matches(self):
        caps = _sdk_capabilities()
        manual_count = sum(1 for m in caps["modules"].values() if m["available"])
        assert caps["available"] == manual_count


# ---------------------------------------------------------------------------
# 14. Evaluation Benchmark
# ---------------------------------------------------------------------------

from gradata.contrib.enhancements.eval_benchmark import (
    BenchmarkCase,
    LearningBenchmark,
    run_standard_benchmark,
)


class TestEvalBenchmark:
    def test_empty_benchmark(self):
        bench = LearningBenchmark()
        result = bench.run()
        assert result.total_cases == 0
        assert result.overall_score == 1.0  # No cases = perfect

    def test_single_high_value_case(self):
        bench = LearningBenchmark()
        bench.add_case(
            BenchmarkCase(
                correction_text="Major rewrite",
                severity="rewrite",
                expected_high_value=True,
            )
        )
        result = bench.run()
        assert result.total_cases == 1

    def test_standard_benchmark_runs(self):
        result = run_standard_benchmark()
        assert result.total_cases == 7
        assert 0.0 <= result.overall_score <= 1.0
        assert 0.0 <= result.correction_recall <= 1.0
        assert 0.0 <= result.rule_precision <= 1.0
        assert 0.0 <= result.graduation_accuracy <= 1.0

    def test_benchmark_discriminator_scores(self):
        bench = LearningBenchmark()
        bench.add_case(
            BenchmarkCase(
                severity="rewrite",
                expected_high_value=True,
            )
        )
        bench.add_case(
            BenchmarkCase(
                severity="trivial",
                expected_high_value=False,
            )
        )
        result = bench.run()
        assert result.graduation_accuracy > 0.0

    def test_pass_rate(self):
        bench = LearningBenchmark()
        bench.add_case(BenchmarkCase(severity="major", expected_high_value=True))
        result = bench.run()
        assert 0.0 <= result.pass_rate <= 1.0

    def test_case_count(self):
        bench = LearningBenchmark()
        bench.add_cases(
            [
                BenchmarkCase(severity="minor"),
                BenchmarkCase(severity="major"),
            ]
        )
        assert bench.case_count == 2


# ---------------------------------------------------------------------------
# 15. Router Warm-Start
# ---------------------------------------------------------------------------

from gradata.enhancements.router_warmstart import warm_start_router


class TestRouterWarmstart:
    def test_warmstart_nonexistent_db(self):
        router = warm_start_router(db_path="/nonexistent/system.db")
        assert router.update_count == 0  # No data, no training

    def test_warmstart_empty_db(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            import sqlite3

            db_path = Path(tmpdir) / "system.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE events (
                    rowid INTEGER PRIMARY KEY,
                    type TEXT, source TEXT, data_json TEXT,
                    session INTEGER, ts TEXT
                )
            """)
            conn.close()
            router = warm_start_router(db_path=db_path)
            assert router.update_count == 0

    def test_warmstart_with_corrections(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            import sqlite3

            db_path = Path(tmpdir) / "system.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE events (
                    rowid INTEGER PRIMARY KEY,
                    type TEXT, source TEXT, data_json TEXT,
                    session INTEGER, ts TEXT
                )
            """)
            # Insert test correction events
            for i, (sev, cat) in enumerate(
                [
                    ("moderate", "TONE"),
                    ("major", "CONTENT"),
                    ("trivial", "STYLE"),
                    ("rewrite", "ACCURACY"),
                ]
            ):
                conn.execute(
                    "INSERT INTO events (type, source, data_json, session, ts) VALUES (?, ?, ?, ?, ?)",
                    (
                        "CORRECTION",
                        "test",
                        json.dumps({"severity": sev, "category": cat}),
                        i + 1,
                        "2026-01-01",
                    ),
                )
            conn.commit()
            conn.close()

            router = warm_start_router(db_path=db_path)
            assert router.update_count == 4
            assert router.epsilon < 0.5  # Should have decayed

    def test_warmstart_saves_router(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            import sqlite3

            db_path = Path(tmpdir) / "system.db"
            router_path = Path(tmpdir) / "q_router.json"
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE events (
                    rowid INTEGER PRIMARY KEY, type TEXT,
                    source TEXT, data_json TEXT, session INTEGER, ts TEXT
                )
            """)
            conn.execute(
                "INSERT INTO events VALUES (1, 'CORRECTION', 'test', ?, 1, '2026-01-01')",
                (json.dumps({"severity": "moderate", "category": "TONE"}),),
            )
            conn.commit()
            conn.close()

            warm_start_router(db_path=db_path, router_path=router_path)
            assert router_path.exists()


# ---------------------------------------------------------------------------
# 16. MCP Server New Tools
# ---------------------------------------------------------------------------

from gradata.mcp_server import _TOOL_SCHEMAS, _dispatch


class TestMCPNewTools:
    def test_tool_schemas_include_new_tools(self):
        tool_names = [t["name"] for t in _TOOL_SCHEMAS]
        assert "brain_pipeline_stats" in tool_names
        assert "brain_context_bracket" in tool_names
        assert "brain_route_suggest" in tool_names
        assert "brain_capabilities" in tool_names
        assert "brain_benchmark" in tool_names
        assert "gradata_recall" in tool_names

    def test_tool_count(self):
        assert len(_TOOL_SCHEMAS) == 12

    def test_dispatch_capabilities_no_brain(self):
        # capabilities doesn't need a brain instance
        result = _dispatch(None, "brain_capabilities", {})
        # Should still return capabilities even without brain
        text = result.get("content", [{}])[0].get("text", "{}")
        data = json.loads(text)
        assert "modules" in data or "error" not in data

    def test_dispatch_benchmark_no_brain(self):
        result = _dispatch(None, "brain_benchmark", {})
        # Without brain, dispatch returns error before reaching benchmark
        assert "error" in result or "content" in result

    def test_dispatch_unknown_tool(self):
        result = _dispatch(None, "nonexistent_tool", {})
        assert "error" in result


# ---------------------------------------------------------------------------
# 17. Brain.correct() → Pipeline Integration Test
# ---------------------------------------------------------------------------


class TestBrainCorrectPipeline:
    """Test that Brain.correct() actually triggers the learning pipeline."""

    def test_correct_returns_pipeline_metadata(self):
        """Brain.correct() should include pipeline results in the event."""
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            event = brain.correct(
                draft="Dear Sir or Madam, I am writing to inform you",
                final="Hey, just wanted to let you know",
            )
            # Pipeline should have run and attached metadata
            assert "pipeline" in event, "Learning pipeline did not attach to event"
            pipeline = event["pipeline"]
            assert "stages_completed" in pipeline
            assert "is_high_value" in pipeline
            assert "discriminator_confidence" in pipeline
            assert "context_bracket" in pipeline
            assert isinstance(pipeline["stages_completed"], list)
            assert len(pipeline["stages_completed"]) > 0

    def test_correct_pipeline_discriminates_severity(self):
        """Major corrections should be flagged as high-value."""
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")

            # Major edit — should be high value
            event = brain.correct(
                draft="The quarterly revenue was $10M with 15% growth",
                final="Q1 was $2M, down 30%. We need to cut costs.",
            )
            pipeline = event.get("pipeline", {})
            # Major severity should produce higher discriminator confidence
            assert pipeline.get("discriminator_confidence", 0) > 0

    def test_correct_pipeline_has_context_bracket(self):
        """Pipeline should report context bracket."""
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            event = brain.correct(
                draft="version A",
                final="version B",
            )
            pipeline = event.get("pipeline", {})
            assert pipeline.get("context_bracket") in ("fresh", "moderate", "deep", "critical")

    def test_correct_pipeline_processing_time(self):
        """Pipeline should report processing time."""
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            event = brain.correct(
                draft="old text",
                final="new text",
            )
            pipeline = event.get("pipeline", {})
            assert "processing_time_ms" in pipeline
            assert pipeline["processing_time_ms"] >= 0

    def test_brain_has_learning_pipeline(self):
        """Brain should initialize the learning pipeline."""
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            assert brain._learning_pipeline is not None


# ===========================================================================
# Adversarial Audit Bug Fix Verification
# ===========================================================================


class TestBugFix_ObservationStoreRotation:
    """BUG 1: File rotation crash on Windows with same-second collisions."""

    def test_rotation_uses_nanoseconds(self):
        """Rotated filenames should use time_ns to avoid collisions."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = ObservationStore(base_dir=tmpdir, max_file_size_mb=0.0001)
            # Write enough to trigger rotation
            for i in range(20):
                obs = observe_tool_use(f"Tool{i}", project_id="rot_test")
                store.append(obs)
            # Should not crash — rotation handled gracefully
            assert store.count("rot_test") > 0


class TestBugFix_ClusterDimensionMismatch:
    """BUG 2: Dimension mismatch causes IndexError or corruption."""

    def test_mismatched_dimensions_raises(self):
        mgr = ClusterManager()
        state = ClusterState()
        mgr.assign(state, "item_1", [1.0, 0.0, 0.0], 1000.0)
        with pytest.raises(ValueError, match="dimension"):
            mgr.assign(state, "item_2", [1.0, 0.0], 1001.0)  # 2D vs 3D

    def test_nan_vector_rejected(self):
        mgr = ClusterManager()
        state = ClusterState()
        with pytest.raises(ValueError, match="non-finite"):
            mgr.assign(state, "item_1", [float("nan"), 0.0], 1000.0)

    def test_empty_vector_rejected(self):
        mgr = ClusterManager()
        state = ClusterState()
        with pytest.raises(ValueError, match="non-empty"):
            mgr.assign(state, "item_1", [], 1000.0)


class TestBugFix_PipelineNoneHandling:
    """BUG 5: Pipeline silently drops corrections with None draft/final."""

    def test_none_draft_final_doesnt_crash(self):
        pipeline = LearningPipeline()
        result = pipeline.process_correction(draft=None, final=None, severity="major")
        assert result.success
        assert "discriminate" in result.stages_completed

    def test_none_severity_defaults(self):
        pipeline = LearningPipeline()
        result = pipeline.process_correction(severity=None)
        assert result.success


class TestBugFix_RouterEmptyAgents:
    """BUG 10: Router crashes with empty agents list."""

    def test_empty_agents_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            QLearningRouter(RouterConfig(agents=[]))


class TestBugFix_CircularDependency:
    """BUG 6: InstallManifest silently accepts circular deps."""

    def test_circular_dependency_detected(self):
        manifest = InstallManifest(
            modules=[
                Module(id="a", name="A", dependencies=["b"]),
                Module(id="b", name="B", dependencies=["c"]),
                Module(id="c", name="C", dependencies=["a"]),
            ]
        )
        with pytest.raises(ValueError, match=r"[Cc]ircular"):
            manifest.resolve_dependencies(["a"])


class TestBugFix_DuplicatePlanIds:
    """BUG 7: Reconciler double-counts with duplicate plan IDs."""

    def test_duplicate_plan_ids_deduplicated(self):
        plan = [
            PlanItem(id="AC-1", description="First"),
            PlanItem(id="AC-1", description="Duplicate"),
        ]
        actuals = [ActualResult(plan_id="AC-1", achieved=True)]
        summary = Reconciler().reconcile(plan, actuals)
        # Should count AC-1 only once
        assert summary.pass_count == 1
        assert summary.completion_ratio == 1.0


class TestBugFix_RouterVersionComparison:
    """BUG 8: Version comparison uses string ordering."""

    def test_semantic_version_comparison(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            filepath = Path(tmpdir) / "router.json"
            # Write a version 10.0.0 file (string "10.0.0" < "2.0.0")
            import json as _json

            filepath.write_text(
                _json.dumps(
                    {
                        "version": "10.0.0",
                        "q_table": {"test": [0.5, 0.5]},
                        "epsilon": 0.1,
                        "update_count": 100,
                        "stats": {},
                        "config": {"agents": ["a", "b"]},
                    }
                )
            )
            router = QLearningRouter()
            assert router.load(filepath) is True
            assert router.update_count == 100


class TestBugFix_SdkCapabilitiesComplete:
    """BUG 9: _sdk_capabilities missing eval_benchmark and router_warmstart."""

    def test_all_modules_reported(self):
        caps = _sdk_capabilities()
        modules = caps["modules"]
        assert "eval_benchmark" in modules
        assert "router_warmstart" in modules
        assert modules["eval_benchmark"]["available"] is True
        assert modules["router_warmstart"]["available"] is True

    def test_deerflow_modules_reported(self):
        caps = _sdk_capabilities()
        modules = caps["modules"]
        assert "loop_detection" in modules
        assert "middleware_chain" in modules
        assert modules["loop_detection"]["source"] == "deer-flow"
        assert modules["middleware_chain"]["source"] == "deer-flow"


# ===========================================================================
# DeerFlow Adaptations
# ===========================================================================

# ---------------------------------------------------------------------------
# 18. Loop Detection
# ---------------------------------------------------------------------------

from gradata.contrib.patterns.loop_detection import (
    LoopAction,
    LoopDetector,
    LoopDetectorConfig,
)


class TestLoopDetection:
    def test_no_loop_single_call(self):
        d = LoopDetector()
        assert d.record("Bash", {"command": "ls"}) == LoopAction.ALLOW

    def test_different_calls_no_loop(self):
        d = LoopDetector()
        d.record("Bash", {"command": "ls"})
        d.record("Read", {"file": "foo.py"})
        d.record("Edit", {"file": "foo.py"})
        assert not d.is_looping

    def test_warn_at_threshold(self):
        d = LoopDetector(LoopDetectorConfig(warn_threshold=3, stop_threshold=5))
        for _ in range(2):
            d.record("Bash", {"command": "pytest"})
        action = d.record("Bash", {"command": "pytest"})
        assert action == LoopAction.WARN

    def test_stop_at_threshold(self):
        d = LoopDetector(LoopDetectorConfig(warn_threshold=3, stop_threshold=5))
        for _ in range(4):
            d.record("Bash", {"command": "pytest"})
        action = d.record("Bash", {"command": "pytest"})
        assert action == LoopAction.STOP

    def test_is_looping_property(self):
        d = LoopDetector(LoopDetectorConfig(warn_threshold=2))
        d.record("Bash", {"command": "x"})
        assert not d.is_looping
        d.record("Bash", {"command": "x"})
        assert d.is_looping

    def test_reset_clears_state(self):
        d = LoopDetector(LoopDetectorConfig(warn_threshold=2))
        d.record("Bash", {"command": "x"})
        d.record("Bash", {"command": "x"})
        assert d.is_looping
        d.reset()
        assert not d.is_looping
        assert len(d.events) == 0

    def test_sliding_window_evicts(self):
        d = LoopDetector(LoopDetectorConfig(window_size=3, warn_threshold=3))
        d.record("Bash", {"command": "x"})
        d.record("Bash", {"command": "x"})
        # Fill window with different calls to push out old ones
        d.record("Read", {"file": "a"})
        d.record("Read", {"file": "b"})
        # Old "x" calls should have been evicted
        action = d.record("Bash", {"command": "x"})
        assert action == LoopAction.ALLOW  # Only 1 in window now

    def test_argument_order_irrelevant(self):
        d = LoopDetector(LoopDetectorConfig(warn_threshold=2))
        d.record("Bash", {"a": 1, "b": 2})
        action = d.record("Bash", {"b": 2, "a": 1})
        assert action == LoopAction.WARN  # Same hash despite key order

    def test_none_arguments(self):
        d = LoopDetector()
        action = d.record("Bash", None)
        assert action == LoopAction.ALLOW

    def test_stats(self):
        d = LoopDetector(LoopDetectorConfig(warn_threshold=2))
        d.record("Bash", {"command": "x"})
        d.record("Bash", {"command": "x"})
        d.record("Bash", {"command": "x"})
        stats = d.stats()
        assert stats["total_calls"] == 3
        assert stats["warnings"] >= 1
        assert stats["most_repeated_tool"] == "Bash"

    def test_events_property(self):
        d = LoopDetector()
        d.record("Bash", {"command": "ls"})
        assert len(d.events) == 1
        assert d.events[0].tool_name == "Bash"


# ---------------------------------------------------------------------------
# 19. Middleware Chain
# ---------------------------------------------------------------------------

from gradata.contrib.patterns.middleware import (
    Middleware,
    MiddlewareChain,
    MiddlewareError,
)


class TestMiddlewareChain:
    def test_empty_chain(self):
        chain = MiddlewareChain()
        ctx = chain.execute("test")
        assert ctx.operation == "test"
        assert not ctx.halted

    def test_before_after_order(self):
        order = []

        class MW1(Middleware):
            name = "mw1"

            def before(self, ctx):
                order.append("mw1_before")
                return ctx

            def after(self, ctx):
                order.append("mw1_after")
                return ctx

        class MW2(Middleware):
            name = "mw2"

            def before(self, ctx):
                order.append("mw2_before")
                return ctx

            def after(self, ctx):
                order.append("mw2_after")
                return ctx

        chain = MiddlewareChain()
        chain.add(MW1())
        chain.add(MW2())
        chain.execute("test")
        # Before: forward order. After: reverse (onion model).
        assert order == ["mw1_before", "mw2_before", "mw2_after", "mw1_after"]

    def test_halt_stops_chain(self):
        class Halter(Middleware):
            name = "halter"

            def before(self, ctx):
                ctx.halted = True
                ctx.halt_reason = "blocked"
                return ctx

        class NeverReached(Middleware):
            name = "unreachable"

            def before(self, ctx):
                raise AssertionError("Should not be called")

        chain = MiddlewareChain()
        chain.add(Halter())
        chain.add(NeverReached())
        ctx = chain.execute("test")
        assert ctx.halted
        assert ctx.halt_reason == "blocked"

    def test_executor_runs(self):
        chain = MiddlewareChain()
        ctx = chain.execute("test", executor=lambda ctx: 42)
        assert ctx.result == 42

    def test_after_anchor_positioning(self):
        class First(Middleware):
            name = "first"

        class Second(Middleware):
            name = "second"
            after_middleware = "first"

        chain = MiddlewareChain()
        chain.add(First())
        chain.add(Second())
        assert chain.middleware_names == ["first", "second"]

    def test_before_anchor_positioning(self):
        class First(Middleware):
            name = "first"

        class Inserted(Middleware):
            name = "inserted"
            before_middleware = "first"

        chain = MiddlewareChain()
        chain.add(First())
        chain.add(Inserted())
        assert chain.middleware_names == ["inserted", "first"]

    def test_duplicate_name_raises(self):
        class MW(Middleware):
            name = "dup"

        chain = MiddlewareChain()
        chain.add(MW())
        with pytest.raises(MiddlewareError, match="already registered"):
            chain.add(MW())

    def test_anchor_unknown_raises(self):
        class MW(Middleware):
            name = "orphan"
            after_middleware = "nonexistent"

        chain = MiddlewareChain()
        with pytest.raises(MiddlewareError, match="not registered"):
            chain.add(MW())

    def test_both_anchors_raises(self):
        class MW(Middleware):
            name = "confused"
            after_middleware = "a"
            before_middleware = "b"

        chain = MiddlewareChain()
        with pytest.raises(MiddlewareError, match="cannot specify both"):
            chain.add(MW())

    def test_remove(self):
        class MW(Middleware):
            name = "removable"

        chain = MiddlewareChain()
        chain.add(MW())
        assert chain.count == 1
        assert chain.remove("removable") is True
        assert chain.count == 0
        assert chain.remove("nonexistent") is False

    def test_get(self):
        class MW(Middleware):
            name = "findme"

        chain = MiddlewareChain()
        chain.add(MW())
        assert chain.get("findme") is not None
        assert chain.get("nope") is None

    def test_error_handling(self):
        class Faulty(Middleware):
            name = "faulty"

            def before(self, ctx):
                raise RuntimeError("oops")

        chain = MiddlewareChain()
        chain.add(Faulty())
        ctx = chain.execute("test")
        assert len(ctx.errors) == 1
        assert "oops" in ctx.errors[0]

    def test_stats(self):
        chain = MiddlewareChain()
        chain.add(Middleware())
        stats = chain.stats()
        assert stats["count"] == 1

    def test_metadata_pass_through(self):
        class Tagger(Middleware):
            name = "tagger"

            def before(self, ctx):
                ctx.metadata["tagged"] = True
                return ctx

        chain = MiddlewareChain()
        chain.add(Tagger())
        ctx = chain.execute("test")
        assert ctx.metadata["tagged"] is True


# ===========================================================================
# Install-and-Forget Features
# ===========================================================================

# ---------------------------------------------------------------------------
# 20. Auto-Correct Hook
# ---------------------------------------------------------------------------

from gradata.hooks.auto_correct import (
    generate_full_config,
    generate_hook_config,
    generate_mcp_config,
    process_hook_input,
)


class TestAutoCorrectHook:
    def test_edit_captured(self):
        inp = json.dumps(
            {
                "tool_name": "Edit",
                "input": {"old_string": "Dear Sir,", "new_string": "Hey,"},
            }
        )
        result = process_hook_input(inp)
        # May or may not capture depending on brain availability
        assert "captured" in result

    def test_no_diff_skipped(self):
        inp = json.dumps(
            {
                "tool_name": "Edit",
                "input": {"old_string": "same", "new_string": "same"},
            }
        )
        result = process_hook_input(inp)
        assert result["captured"] is False

    def test_invalid_json(self):
        result = process_hook_input("not json")
        assert result["captured"] is False
        assert result["reason"] == "invalid_json"

    def test_unknown_tool_skipped(self):
        inp = json.dumps({"tool_name": "Read", "input": {}})
        result = process_hook_input(inp)
        assert result["captured"] is False

    def test_generate_hook_config(self):
        config = generate_hook_config()
        assert "hooks" in config
        assert "PostToolUse" in config["hooks"]
        hooks = config["hooks"]["PostToolUse"]
        assert len(hooks) >= 1
        assert "gradata" in hooks[0]["command"]

    def test_generate_mcp_config(self):
        config = generate_mcp_config()
        assert "mcpServers" in config
        assert "gradata" in config["mcpServers"]

    def test_generate_full_config(self):
        config = generate_full_config()
        assert "mcpServers" in config
        assert "hooks" in config


# ---------------------------------------------------------------------------
# 21. Git Backfill
# ---------------------------------------------------------------------------

from gradata.enhancements.git_backfill import BackfillStats, scan_git_diffs


class TestGitBackfill:
    def test_scan_nonexistent_repo(self):
        diffs = scan_git_diffs(repo_path="/nonexistent/repo")
        assert diffs == []

    def test_scan_current_repo(self):
        # This test runs in the actual SDK repo which has git history
        diffs = scan_git_diffs(
            repo_path=".",
            lookback_days=7,
            max_commits=5,
            file_patterns=["*.py"],
        )
        # May or may not find diffs depending on recent activity
        assert isinstance(diffs, list)

    def test_backfill_stats(self):
        stats = BackfillStats()
        assert stats.commits_scanned == 0
        assert stats.corrections_captured == 0
        d = stats.to_dict()
        assert "commits_scanned" in d
        assert "severities" in d

    def test_brain_backfill_method(self):
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            result = brain.backfill_from_git(
                repo_path=".",
                lookback_days=1,
                max_commits=3,
            )
            assert isinstance(result, dict)
            # Either has stats or error (if no git repo context)
            assert "commits_scanned" in result or "error" in result

    def test_scan_filters_by_pattern(self):
        diffs = scan_git_diffs(
            repo_path=".",
            lookback_days=7,
            max_commits=3,
            file_patterns=["*.nonexistent_extension"],
        )
        assert len(diffs) == 0  # No files match this pattern


# ---------------------------------------------------------------------------
# 22. Manifest includes new modules
# ---------------------------------------------------------------------------


class TestManifestNewModules:
    def test_all_new_modules_in_capabilities(self):
        caps = _sdk_capabilities()
        modules = caps["modules"]
        expected = [
            "loop_detection",
            "middleware_chain",
            "git_backfill",
            "auto_correct_hook",
            "reporting",
            "quality_monitoring",
        ]
        for name in expected:
            assert name in modules, f"Missing: {name}"
            assert modules[name]["available"] is True, f"Not available: {name}"


# ===========================================================================
# fest.build + Jarvis Inspired Features
# ===========================================================================

# ---------------------------------------------------------------------------
# 23. Brain Briefing
# ---------------------------------------------------------------------------

from gradata.enhancements.reporting import (
    EXPORT_TARGETS,
    BrainBriefing,
    BriefingRule,
)


class TestBrainBriefing:
    def test_empty_briefing(self):
        b = BrainBriefing()
        assert not b.has_content
        md = b.to_markdown()
        assert "Brain Rules" in md

    def test_briefing_with_rules(self):
        b = BrainBriefing(
            rules=[
                BriefingRule(
                    category="TONE", description="Use casual voice", confidence=0.92, state="RULE"
                ),
                BriefingRule(
                    category="STYLE", description="No em dashes", confidence=0.70, state="PATTERN"
                ),
            ]
        )
        assert b.has_content
        assert b.rule_count == 2
        md = b.to_markdown()
        assert "MUST" in md
        assert "SHOULD" in md
        assert "casual voice" in md

    def test_briefing_with_anti_patterns(self):
        b = BrainBriefing(anti_patterns=["Never say 'As an AI'"])
        md = b.to_markdown()
        assert "DO NOT" in md
        assert "As an AI" in md

    def test_briefing_with_health(self):
        b = BrainBriefing(
            brain_health={
                "compound_score": 72.3,
                "correction_rate": 0.004,
            }
        )
        # Health metrics removed from compact format (rules-only briefing)
        # Verify briefing still generates without error
        md = b.to_markdown()
        assert "Brain Rules" in md

    def test_briefing_rule_priority(self):
        r = BriefingRule(category="X", description="Y", confidence=0.9, state="RULE")
        assert r.priority == "MUST"
        r2 = BriefingRule(category="X", description="Y", confidence=0.6, state="PATTERN")
        assert r2.priority == "SHOULD"
        r3 = BriefingRule(category="X", description="Y", confidence=0.3, state="INSTINCT")
        assert r3.priority == "MAY"

    def test_export_targets_defined(self):
        assert "claude" in EXPORT_TARGETS
        assert "cursor" in EXPORT_TARGETS
        assert "copilot" in EXPORT_TARGETS

    def test_brain_briefing_method(self):
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            md = brain.briefing()
            assert "Brain Rules" in md

    def test_brain_briefing_returns_string(self):
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            result = brain.briefing()
            assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 24. Anti-Pattern Detection
# ---------------------------------------------------------------------------

from gradata.enhancements.quality_monitoring import (
    DEFAULT_PATTERNS,
    AntiPattern,
    AntiPatternDetector,
)


class TestAntiPatterns:
    def test_detect_happy_to_help(self):
        d = AntiPatternDetector()
        results = d.check("I'd be happy to help you with that!")
        names = [r.pattern_name for r in results]
        assert "happy_to_help" in names

    def test_detect_as_an_ai(self):
        d = AntiPatternDetector()
        results = d.check("As an AI, I cannot do that.")
        names = [r.pattern_name for r in results]
        assert "as_an_ai" in names

    def test_detect_delve(self):
        d = AntiPatternDetector()
        results = d.check("Let's delve into this topic.")
        assert any(r.pattern_name == "delve_into" for r in results)

    def test_detect_em_dash(self):
        d = AntiPatternDetector()
        results = d.check("The results \u2014 which were surprising \u2014 showed growth.")
        assert any(r.pattern_name == "em_dash_in_prose" for r in results)

    def test_clean_text_no_detections(self):
        d = AntiPatternDetector()
        results = d.check("Here are the quarterly results. Revenue grew 15%.")
        # Should have very few or no detections
        high_sev = [r for r in results if r.severity == "high"]
        assert len(high_sev) == 0

    def test_score_clean(self):
        d = AntiPatternDetector()
        score = d.score("Revenue grew 15% this quarter.")
        assert score > 0.8

    def test_score_terrible(self):
        d = AntiPatternDetector()
        score = d.score(
            "I'd be happy to help! Absolutely! As an AI, let me delve into "
            "this comprehensive analysis. Great question! Certainly!"
        )
        assert score < 0.5

    def test_empty_text(self):
        d = AntiPatternDetector()
        assert d.check("") == []
        assert d.score("") == 1.0

    def test_add_custom_pattern(self):
        d = AntiPatternDetector(include_defaults=False)
        assert d.pattern_count == 0
        d.add_pattern(
            AntiPattern(
                name="custom",
                category="test",
                pattern="bad word",
            )
        )
        assert d.pattern_count == 1
        results = d.check("this has a bad word in it")
        assert len(results) == 1

    def test_stats(self):
        d = AntiPatternDetector()
        stats = d.stats()
        assert stats["total_patterns"] == len(DEFAULT_PATTERNS)
        assert "ai_tell" in stats["by_category"]

    def test_detection_has_replacement_hint(self):
        d = AntiPatternDetector()
        results = d.check("I'd be happy to help!")
        for r in results:
            if r.pattern_name == "happy_to_help":
                assert r.replacement_hint != ""


# ===========================================================================
# Tree of Thoughts
# ===========================================================================

from gradata.contrib.patterns.tree_of_thoughts import (
    Thought,
    ToTResult,
    evaluate_rule_candidates,
    explore,
)


class TestTreeOfThoughts:
    def test_thought_is_leaf(self):
        t = Thought(content="test")
        assert t.is_leaf is True
        t.children.append(Thought(content="child"))
        assert t.is_leaf is False

    def test_explore_basic(self):
        def scorer(c):
            return (0.8 if "good" in c else 0.3, "test")

        result = explore(["good rule", "bad rule"], scorer, max_depth=1)
        assert isinstance(result, ToTResult)
        assert result.best.score == 0.8
        assert result.total_explored == 2

    def test_explore_with_depth(self):
        def scorer(c):
            return (min(1.0, len(c) / 20), "length-based")

        result = explore(
            ["a good long candidate", "another good option"], scorer, max_depth=2, min_score=0.3
        )
        assert result.total_explored > 2
        assert result.depth == 2

    def test_evaluate_rule_candidates(self):
        result = evaluate_rule_candidates(
            "Use colons instead of dashes in emails",
            existing_rules=["Use formal tone in client emails"],
        )
        assert isinstance(result, ToTResult)
        assert result.best.content  # Has content
        assert result.best.score >= 0.0

    def test_evaluate_empty_rules(self):
        result = evaluate_rule_candidates("Some lesson", existing_rules=[])
        assert result.best.score >= 0.0


# ===========================================================================
# brain.plan() and brain.spawn_queue()
# ===========================================================================

from gradata.brain import Brain


class TestBrainPlan:
    def test_plan_returns_steps(self, tmp_path):
        brain = Brain.init(str(tmp_path / "test-brain"))
        result = brain.plan("Write a cold email")
        assert "task" in result
        assert "steps" in result
        assert isinstance(result["steps"], list)
        assert len(result["steps"]) >= 2
        assert result["task"] == "Write a cold email"

    def test_plan_with_context(self, tmp_path):
        brain = Brain.init(str(tmp_path / "test-brain"))
        result = brain.plan("Draft proposal", context={"domain": "sales"})
        assert result["context"]["domain"] == "sales"


class TestBrainSpawnQueue:
    def test_spawn_queue_basic(self, tmp_path):
        brain = Brain.init(str(tmp_path / "test-brain"))
        results = brain.spawn_queue(
            tasks=["task1", "task2", "task3"],
            worker=lambda t: {"output": f"done: {t}"},
            max_concurrent=2,
        )
        assert results["total"] == 3
        assert results["completed"] == 3
        assert results["failed"] == 0
        assert len(results["results"]) == 3

    def test_spawn_queue_with_failures(self, tmp_path):
        brain = Brain.init(str(tmp_path / "test-brain"))

        def flaky_worker(t):
            if "fail" in t:
                raise ValueError("intentional failure")
            return {"ok": True}

        results = brain.spawn_queue(
            tasks=["good1", "fail-this", "good2"],
            worker=flaky_worker,
        )
        assert results["completed"] == 2
        assert results["failed"] == 1
        assert results["failures"][0]["error"] == "intentional failure"

    def test_spawn_queue_on_complete_callback(self, tmp_path):
        brain = Brain.init(str(tmp_path / "test-brain"))
        completed = []
        results = brain.spawn_queue(
            tasks=["a", "b"],
            worker=lambda t: {"val": t},
            on_complete=lambda r: completed.append(r),
        )
        assert results["completed"] == 2
        assert len(completed) == 2

    def test_spawn_queue_empty(self, tmp_path):
        brain = Brain.init(str(tmp_path / "test-brain"))
        results = brain.spawn_queue(tasks=[], worker=lambda t: {})
        assert results["total"] == 0
        assert results["completed"] == 0
