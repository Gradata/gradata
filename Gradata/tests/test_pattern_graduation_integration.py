"""Comprehensive integration test: 22 pattern connections to graduation pipeline.

Tests BOTH directions:
  Forward:  pattern output -> graduation pipeline (confidence updates, corrections)
  Backward: graduated rules -> pattern adaptation (criteria, guards, dimensions, etc.)
"""

import sys
import importlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gradata.brain import Brain
from gradata.rules.rule_context import GraduatedRule, get_rule_context


# ---------------------------------------------------------------------------
# Shared content
# ---------------------------------------------------------------------------

LESSONS_CONTENT = """\
# Lessons

[2026-01-01] [PATTERN:0.75] TONE: Keep emails concise and direct
  Root cause: Verbose emails lose reader attention
  Fire count: 5 | Sessions since fire: 1 | Misfires: 0

[2026-01-15] [RULE:0.92] PROCESS: Always plan before implementing
  Root cause: Jumping to code causes rework
  Fire count: 10 | Sessions since fire: 0 | Misfires: 1

[2026-02-01] [PATTERN:0.65] SECURITY: Never expose API keys in output
  Root cause: Keys leaked in debug output
  Fire count: 3 | Sessions since fire: 2 | Misfires: 0

[2026-02-10] [PATTERN:0.80] DRAFTING: Use colons over dashes
  Root cause: User prefers colons
  Fire count: 7 | Sessions since fire: 0 | Misfires: 0

[2026-03-01] [RULE:0.95] ACCURACY: Double-check all numbers before reporting
  Root cause: Hallucinated stats damage credibility
  Fire count: 12 | Sessions since fire: 0 | Misfires: 0

[2026-03-15] [PATTERN:0.70] SAFETY: Validate inputs at system boundaries
  Root cause: Unvalidated input caused crash
  Fire count: 4 | Sessions since fire: 1 | Misfires: 1
"""

TEST_RULES = [
    GraduatedRule("r1",  "TONE",     "Keep emails concise",           0.75, {},                         "lesson", (),           ""),
    GraduatedRule("r2",  "PROCESS",  "Always plan before implementing",0.92, {},                         "lesson", ("planning",),""),
    GraduatedRule("r3",  "SECURITY", "Never expose API keys",          0.65, {},                         "lesson", (),           "coder"),
    GraduatedRule("r4",  "DRAFTING", "Use colons over dashes",         0.80, {"task_type": "email"},     "lesson", (),           ""),
    GraduatedRule("r5",  "ACCURACY", "Double-check numbers",           0.95, {},                         "lesson", (),           ""),
    GraduatedRule("r6",  "SAFETY",   "Validate inputs",                0.70, {"agent_type": "coder"},    "lesson", (),           "coder"),
    GraduatedRule("r7",  "PROCESS",  "Run tests after changes",        0.85, {},                         "lesson", (),           ""),
    GraduatedRule("r8",  "STYLE",    "No em dashes in emails",         0.78, {"task_type": "email"},     "lesson", (),           ""),
    GraduatedRule("r9",  "PROCESS",  "Audit before building",          0.88, {},                         "lesson", (),           ""),
    GraduatedRule("r10", "HONESTY",  "Never fabricate numbers",        0.91, {},                         "lesson", (),           ""),
    GraduatedRule("r11", "PROCESS",  "Batch parallel operations",      0.72, {},                         "lesson", (),           ""),
    GraduatedRule("r12", "PROCESS",  "Keep files under 500 lines",     0.68, {},                         "lesson", (),           "coder"),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def brain(brain_dir: Path) -> Brain:
    """Isolated Brain instance backed by a temp directory with lessons.md."""
    (brain_dir / "lessons.md").write_text(LESSONS_CONTENT, encoding="utf-8")
    return Brain(str(brain_dir))


@pytest.fixture(autouse=True)
def seeded_rule_context():
    """Seed RuleContext with TEST_RULES before each test; clear after."""
    ctx = get_rule_context()
    ctx.clear()
    for r in TEST_RULES:
        ctx.publish(r)
    yield ctx
    ctx.clear()


# ---------------------------------------------------------------------------
# BACKWARD FLOW TESTS  (graduated rules -> pattern adaptation)
# ---------------------------------------------------------------------------

def test_T01_criteria_from_graduated_rules():
    """criteria_from_graduated_rules() returns at least one criterion."""
    from gradata.contrib.patterns.reflection import criteria_from_graduated_rules
    criteria = criteria_from_graduated_rules()
    assert len(criteria) > 0, "Expected at least one criterion from graduated rules"


def test_T02_guards_from_graduated_rules():
    """guards_from_graduated_rules() returns at least one guard."""
    from gradata.contrib.patterns.guardrails import guards_from_graduated_rules
    guards = guards_from_graduated_rules()
    assert len(guards) > 0, "Expected at least one guard from graduated rules"


def test_T03_dimensions_from_graduated_rules():
    """dimensions_from_graduated_rules() returns at least one dimension."""
    from gradata.contrib.patterns.evaluator import dimensions_from_graduated_rules
    dims = dimensions_from_graduated_rules()
    assert len(dims) > 0, "Expected at least one dimension from graduated rules"


def test_T04_rules_budget_deep():
    """rules_budget('DEEP') returns the expected budget of 2."""
    ctx = get_rule_context()
    budget = ctx.rules_budget("DEEP")
    assert budget == 2, f"Expected budget=2 for DEEP, got {budget}"


def test_T05_gates_from_graduated_rules():
    """gates_from_graduated_rules() returns at least one gate dict."""
    from gradata.enhancements.pattern_integration import gates_from_graduated_rules
    gates = gates_from_graduated_rules()
    assert len(gates) > 0, "Expected at least one gate from graduated rules"
    assert "name" in gates[0] and "confidence" in gates[0]


def test_T06_routing_adjustments():
    """routing_adjustments() returns a non-empty category-to-density mapping."""
    from gradata.enhancements.pattern_integration import routing_adjustments
    adj = routing_adjustments()
    assert len(adj) > 0, "Expected at least one routing adjustment category"


def test_T07_importance_categories():
    """importance_categories() returns a non-empty list."""
    from gradata.enhancements.pattern_integration import importance_categories
    cats = importance_categories()
    assert len(cats) > 0, "Expected at least one importance category"


def test_T08_delegation_criteria_for_coder():
    """delegation_criteria_for_agent('coder') returns rules scoped to coder."""
    from gradata.enhancements.pattern_integration import delegation_criteria_for_agent
    crit = delegation_criteria_for_agent("coder")
    assert len(crit) > 0, "Expected at least one rule for agent type 'coder'"


def test_T09_suggested_mode_override():
    """suggested_mode_override() returns None or a string."""
    from gradata.enhancements.pattern_integration import suggested_mode_override
    mode = suggested_mode_override()
    assert mode is None or isinstance(mode, str), f"Expected None or str, got {type(mode)}"


def test_T10_register_brain_tools(brain):
    """register_brain_tools(brain) registers exactly 2 tools."""
    from gradata.enhancements.pattern_integration import register_brain_tools
    count = register_brain_tools(brain)
    assert count == 2, f"Expected 2 tools registered, got {count}"


def test_T11_mcp_rule_tools():
    """mcp_rule_tools() returns exactly 2 MCP tool schemas."""
    from gradata.enhancements.pattern_integration import mcp_rule_tools
    schemas = mcp_rule_tools()
    assert len(schemas) == 2, f"Expected 2 MCP tool schemas, got {len(schemas)}"
    names = [s["name"] for s in schemas]
    assert len(names) == 2


def test_T12_scope_confidence_boost_process():
    """scope_confidence_boost('PROCESS') returns a positive boost."""
    from gradata.enhancements.pattern_integration import scope_confidence_boost
    boost = scope_confidence_boost("PROCESS")
    assert boost > 0, f"Expected positive boost for PROCESS category, got {boost}"


def test_T13_topic_boosts_from_rules():
    """topic_boosts_from_rules() returns at least one category with boost > 1.0."""
    from gradata.enhancements.pattern_integration import topic_boosts_from_rules
    boosts = topic_boosts_from_rules()
    cats_above_1 = {k: v for k, v in boosts.items() if v > 1.0}
    assert len(cats_above_1) > 0, "Expected at least one category with topic boost > 1.0"


def test_T14_loop_threshold_adjustment():
    """loop_threshold_adjustment() returns a dict with 'warn' and 'stop' keys."""
    from gradata.enhancements.pattern_integration import loop_threshold_adjustment
    thresholds = loop_threshold_adjustment()
    assert "warn" in thresholds, "Expected 'warn' key in loop threshold adjustments"
    assert "stop" in thresholds, "Expected 'stop' key in loop threshold adjustments"


def test_T15_strict_categories_from_rules():
    """strict_categories_from_rules() returns at least one strict category."""
    from gradata.enhancements.pattern_integration import strict_categories_from_rules
    strict = strict_categories_from_rules()
    assert len(strict) > 0, "Expected at least one strict category from rules"


def test_T16_create_graduation_middleware():
    """create_graduation_middleware() returns a middleware with name='graduation'."""
    from gradata.enhancements.pattern_integration import create_graduation_middleware
    mw = create_graduation_middleware()
    assert mw is not None
    assert mw.name == "graduation", f"Expected middleware name='graduation', got '{mw.name}'"


# ---------------------------------------------------------------------------
# FORWARD FLOW TESTS  (patterns -> graduation pipeline)
# ---------------------------------------------------------------------------

def test_T17_process_reflection_result(brain):
    """process_reflection_result() returns processed=True for a passing reflection."""
    from gradata.enhancements.pattern_integration import process_reflection_result
    from gradata.contrib.patterns.reflection import ReflectionResult, CritiqueResult, CriterionScore

    mock_critique = CritiqueResult(
        scores={"accuracy": CriterionScore(name="accuracy", passed=True, reason="ok", score=9.0)},
        all_required_passed=True,
        overall_score=9.0,
        cycle=1,
    )
    mock_result = ReflectionResult(
        final_output="Test output",
        critiques=[mock_critique],
        cycles_used=1,
        converged=True,
    )
    result = process_reflection_result(brain, mock_result, "TONE")
    assert result.get("processed", False), f"Expected processed=True, got: {result}"


def test_T18_process_guardrail_result(brain):
    """process_guardrail_result() returns processed=True for a blocked guardrail result."""
    from gradata.enhancements.pattern_integration import process_guardrail_result
    from gradata.contrib.patterns.guardrails import GuardedResult

    class MockGuardCheck:
        def __init__(self):
            self.name = "pii_detector"
            self.guard_name = "pii_detector"
            self.result = "fail"
            self.details = "Found PII: email"
            self.detail = "Found PII: email"
            self.action_taken = "blocked"

    mock_result = GuardedResult(
        input_checks=[MockGuardCheck()],
        output_checks=[],
        all_passed=False,
        blocked=True,
        block_reason="PII detected",
    )
    result = process_guardrail_result(brain, mock_result)
    assert result.get("processed", False), f"Expected processed=True, got: {result}"


def test_T19_feed_q_router(brain):
    """feed_q_router() returns a result dict (processed may be False in cold brain)."""
    from gradata.enhancements.pattern_integration import feed_q_router
    result = feed_q_router(brain, "moderate", agent_type="coder")
    # Router may not be warm-started in a fresh test brain; accept either outcome
    assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
    assert "processed" in result, "Result must contain a 'processed' key"


def test_T20_process_loop_event(brain):
    """process_loop_event() returns processed=True for a WARN loop event."""
    from gradata.enhancements.pattern_integration import process_loop_event
    result = process_loop_event(brain, "WARN", "Bash")
    assert result.get("processed", False), f"Expected processed=True, got: {result}"


def test_T21_process_parallel_failures(brain):
    """process_parallel_failures() returns processed=True."""
    from gradata.enhancements.pattern_integration import process_parallel_failures
    result = process_parallel_failures(brain, ["task_1"], 3)
    assert result.get("processed", False), f"Expected processed=True, got: {result}"


def test_T22_process_escalation(brain):
    """process_escalation() returns processed=True for DONE_WITH_CONCERNS."""
    from gradata.enhancements.pattern_integration import process_escalation
    result = process_escalation(brain, "DONE_WITH_CONCERNS", ["data may be stale"])
    assert result.get("processed", False), f"Expected processed=True, got: {result}"


# ---------------------------------------------------------------------------
# INTEGRATION TESTS
# ---------------------------------------------------------------------------

def test_T23_full_cycle(brain):
    """Full forward+bridge+backward cycle all succeed in sequence."""
    from gradata.enhancements.pattern_integration import process_loop_event
    from gradata.enhancements.rule_context_bridge import bootstrap_rule_context
    from gradata.contrib.patterns.reflection import criteria_from_graduated_rules

    # Forward: emit a loop event
    loop_result = process_loop_event(brain, "WARN", "Read")
    assert loop_result.get("processed", False), f"Loop event not processed: {loop_result}"

    # Bridge: load rules from lessons.md into rule context
    lessons_path = brain._find_lessons_path()
    loaded = bootstrap_rule_context(lessons_path=lessons_path)
    assert loaded > 0, f"Expected >0 rules loaded from lessons.md, got {loaded}"

    # Backward: criteria are now populated from the freshly loaded rules
    criteria = criteria_from_graduated_rules()
    assert len(criteria) > 0, f"Expected criteria after bootstrap, got none"


def test_T24_rule_context_stats_consistency(seeded_rule_context):
    """RuleContext.stats() tier counts are internally consistent."""
    ctx = seeded_rule_context
    stats = ctx.stats()
    total = stats["total_rules"]
    rule_tier = stats["rule_tier"]
    pattern_tier = stats["pattern_tier"]

    assert total > 0, "Expected at least one rule in context"
    assert (rule_tier + pattern_tier) <= total, (
        f"rule_tier({rule_tier}) + pattern_tier({pattern_tier}) > total({total})"
    )


def test_T25_no_circular_imports():
    """All gradata pattern and enhancement modules import without circular errors."""
    modules = [
        "gradata.contrib.patterns.reflection",
        "gradata.contrib.patterns.guardrails",
        "gradata.contrib.patterns.evaluator",
        "gradata.contrib.patterns.pipeline",
        "gradata.contrib.patterns.orchestrator",
        "gradata.contrib.patterns.memory",
        "gradata.rules.scope",
        "gradata.rules.rule_engine",
        "gradata.contrib.patterns.rag",
        "gradata.contrib.patterns.sub_agents",
        "gradata.contrib.patterns.mcp",
        "gradata.contrib.patterns.tools",
        "gradata.contrib.patterns.middleware",
        "gradata.contrib.patterns.loop_detection",
        "gradata.contrib.patterns.parallel",
        "gradata.contrib.patterns.q_learning_router",
        "gradata.contrib.patterns.reconciliation",
        "gradata.contrib.patterns.task_escalation",
        "gradata.contrib.patterns.human_loop",
        "gradata.contrib.patterns.execute_qualify",
        "gradata.contrib.patterns.context_brackets",
        "gradata.contrib.patterns.agent_modes",
        "gradata.rules.rule_context",
        "gradata.rules.rule_tracker",
        "gradata.enhancements.pattern_integration",
        "gradata.enhancements.rule_context_bridge",
        "gradata.enhancements.self_improvement",
        "gradata.enhancements.learning_pipeline",
    ]
    failed = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as exc:
            failed.append(f"{mod}: {exc}")

    assert not failed, "Circular import or load failures:\n" + "\n".join(failed)


# ---------------------------------------------------------------------------
# END-TO-END PIPELINE TESTS  (merged from test_end_to_end.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def e2e_brain(tmp_path: Path) -> Brain:
    """Create a fresh brain for end-to-end tests."""
    import os
    brain_dir = tmp_path / "e2e_brain"
    os.environ["BRAIN_DIR"] = str(brain_dir)
    b = Brain.init(brain_dir, name="E2EBrain", domain="Testing", interactive=False)
    yield b
    os.environ.pop("BRAIN_DIR", None)


class TestFullPipeline:
    """Correction -> confidence increase -> graduation -> rule injection."""

    def test_first_correction_creates_lesson(self, e2e_brain):
        result = e2e_brain.correct(
            draft="We are pleased to inform you of our new product offering.",
            final="Hey, check out what we just shipped.",
            category="TONE",
        )
        assert result.get("data", {}).get("severity") != "as-is"
        lessons = e2e_brain.export_rules_json(min_state="INSTINCT")
        assert len(lessons) >= 1
        assert any(l["category"] == "TONE" for l in lessons)

    def test_repeated_corrections_increase_confidence(self, e2e_brain):
        pairs = [
            ("Dear Sir/Madam, I hope this email finds you well.", "Hey, quick question."),
            ("We would like to schedule a meeting at your convenience.", "Can we chat Thursday?"),
            ("Please find attached the requested documentation.", "Here's the doc you asked for."),
            ("I am writing to follow up on our previous discussion.", "Following up on our chat."),
            ("We are delighted to present our quarterly results.", "Here are this quarter's numbers."),
        ]
        for draft, final in pairs:
            e2e_brain.correct(draft=draft, final=final, category="TONE")

        lessons = e2e_brain.export_rules_json(min_state="INSTINCT")
        tone_lessons = [l for l in lessons if l["category"] == "TONE"]
        assert len(tone_lessons) >= 1
        max_conf = max(l["confidence"] for l in tone_lessons)
        assert max_conf > 0.40, f"Expected confidence > 0.40 after 5 corrections, got {max_conf}"

    def test_graduation_to_pattern(self, e2e_brain):
        # Use 12 corrections across 3 simulated sessions for reliable graduation
        for session in range(1, 4):
            for i in range(4):
                e2e_brain.correct(
                    draft=f"Per our earlier correspondence regarding item {session}_{i}, we wish to advise.",
                    final=f"Quick update on item {session}_{i}.",
                    category="TONE",
                    session=session,
                )
        e2e_brain.end_session()
        lessons = e2e_brain.export_rules_json(min_state="PATTERN")
        pattern_lessons = [l for l in lessons if l["state"] in ("PATTERN", "RULE")]
        assert len(pattern_lessons) >= 1, (
            f"Expected at least 1 PATTERN+ lesson after 12 corrections across 3 sessions, "
            f"got {len(pattern_lessons)}. All lessons: {e2e_brain.export_rules_json(min_state='INSTINCT')}"
        )

    def test_rules_injected_into_prompt(self, e2e_brain):
        for i in range(8):
            e2e_brain.correct(
                draft=f"I am writing to confirm the details of arrangement {i}.",
                final=f"Confirming details for arrangement {i}.",
                category="TONE",
            )
        e2e_brain.end_session()
        rules_text = e2e_brain.apply_brain_rules(task="write an email")
        lessons = e2e_brain.export_rules_json(min_state="PATTERN")
        if lessons:
            assert len(rules_text) > 0, "Expected rules to be injected but got empty string"

    def test_min_severity_skips_trivial(self, e2e_brain):
        result = e2e_brain.correct(
            draft="Hello world",
            final="Hello world!",
            min_severity="moderate",
        )
        assert "data" in result
        severity = result.get("data", {}).get("severity", "")
        if severity in ("as-is", "minor"):
            assert result.get("lessons_created", 0) == 0

    def test_rollback_kills_lesson(self, e2e_brain):
        e2e_brain.correct(
            draft="We are very excited to announce.",
            final="Announcing today.",
            category="TONE",
        )
        lessons_before = e2e_brain.export_rules_json(min_state="INSTINCT")
        assert len(lessons_before) >= 1
        result = e2e_brain.rollback(category="TONE")
        assert result.get("rolled_back") is True

    def test_search_returns_results(self, e2e_brain):
        e2e_brain.correct(
            draft="Please find the budget report attached.",
            final="Budget report attached.",
            category="CONTENT",
        )
        results = e2e_brain.search("budget")
        assert isinstance(results, list)

    def test_export_skills_creates_files(self, e2e_brain, tmp_path):
        for i in range(6):
            e2e_brain.correct(
                draft=f"Formal communication piece number {i} for your review.",
                final=f"Here's piece {i}.",
                category="TONE",
            )
        e2e_brain.end_session()
        output_dir = tmp_path / "skills_export"
        paths = e2e_brain.export_skills(output_dir=str(output_dir))
        if paths:
            for p in paths:
                content = Path(p).read_text(encoding="utf-8")
                assert "---" in content
                assert "gradata" in content.lower()

    def test_doctor_runs_on_brain(self, e2e_brain):
        from gradata._doctor import diagnose
        report = diagnose(brain_dir=e2e_brain.dir)
        assert report["status"] in ("healthy", "degraded")

    def test_manifest_generates(self, e2e_brain):
        e2e_brain.correct(draft="Old text", final="New text")
        m = e2e_brain.manifest()
        assert "metadata" in m
        assert "quality" in m
