"""Pattern Integration — Forward flow from patterns into graduation pipeline.

Each process_* function takes a pattern's output and feeds relevant signals
into the graduation pipeline (confidence updates, correction events, rewards).

This is the FORWARD direction of the bidirectional cycle:
  patterns produce signals → graduation pipeline → rules graduate
  (the BACKWARD direction is handled by rule_context.py adapters in each pattern)

Usage:
    from gradata.enhancements.pattern_integration import (
        process_reflection_result,
        process_guardrail_result,
        process_eval_result,
        process_qualify_result,
        process_reconciliation,
        process_loop_event,
        process_parallel_failures,
        process_escalation,
        feed_q_router,
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata.brain import Brain
    from gradata.patterns.reflection import ReflectionResult
    from gradata.patterns.guardrails import GuardedResult
    from gradata.patterns.evaluator import EvalLoopResult
    from gradata.patterns.execute_qualify import ExecuteQualifyResult
    from gradata.patterns.reconciliation import ReconciliationSummary
    from gradata.patterns.loop_detection import LoopAction

logger = logging.getLogger("gradata")


# ---------------------------------------------------------------------------
# 1. Reflection → Graduation
# ---------------------------------------------------------------------------

def process_reflection_result(
    brain: Brain,
    result: ReflectionResult,
    category: str = "QUALITY",
) -> dict:
    """Feed reflection quality scores into graduation confidence.

    - Converged with score >= 8.0 → boost lessons in matching category
    - Not converged → treat as implicit correction signal
    """
    from gradata.enhancements.self_improvement import (
        parse_lessons, format_lessons, update_confidence,
        ACCEPTANCE_BONUS,
    )

    if not result.critiques:
        return {"processed": False}

    final_score = result.critiques[-1].overall_score if result.critiques else 0.0

    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        return {"processed": False}

    text = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(text)

    if result.converged and final_score >= 8.0:
        # High quality: boost related lessons
        for lesson in lessons:
            if lesson.category == category.upper() and lesson.confidence < 1.0:
                boost = ACCEPTANCE_BONUS * (final_score / 10.0)
                lesson.confidence = round(min(1.0, lesson.confidence + boost), 2)
                lesson.fire_count += 1
    elif not result.converged:
        # Failed to converge: treat as soft correction
        correction_data = [{"category": category.upper(), "severity_label": "minor"}]
        lessons = update_confidence(lessons, correction_data)

    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    return {"processed": True, "converged": result.converged, "score": final_score}


# ---------------------------------------------------------------------------
# 2. Guardrails → Graduation
# ---------------------------------------------------------------------------

GUARD_CATEGORY_MAP = {
    "pii": "SECURITY",
    "injection": "SAFETY",
    "secret": "SECURITY",
    "banned": "TONE",
    "length": "DRAFTING",
    "scope": "PROCESS",
    "destructive": "SAFETY",
}


def process_guardrail_result(
    brain: Brain,
    result: GuardedResult,
) -> dict:
    """Feed guardrail violations into graduation as contradiction signals.

    Each failed guard maps to a lesson category and applies a penalty.
    """
    from gradata.enhancements.self_improvement import (
        parse_lessons, format_lessons, update_confidence,
    )

    failed_checks = []
    for check in list(result.input_checks or []) + list(result.output_checks or []):
        if getattr(check, "result", "") == "fail":
            failed_checks.append(check)

    if not failed_checks:
        return {"processed": False, "violations": 0}

    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        return {"processed": False}

    text = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(text)

    for check in failed_checks:
        # Map guard name to category
        category = "GENERAL"
        guard_name = getattr(check, "name", getattr(check, "guard_name", "unknown"))
        guard_detail = getattr(check, "details", getattr(check, "detail", ""))
        guard_lower = guard_name.lower()
        for keyword, cat in GUARD_CATEGORY_MAP.items():
            if keyword in guard_lower:
                category = cat
                break

        correction_data = [{
            "category": category,
            "severity_label": "moderate",
            "description": f"Guardrail violation: {guard_name} - {guard_detail or ''}",
        }]
        lessons = update_confidence(lessons, correction_data)

    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    return {"processed": True, "violations": len(failed_checks)}


# ---------------------------------------------------------------------------
# 3. Q-Learning Router ← Correction severity
# ---------------------------------------------------------------------------

def feed_q_router(
    brain: Brain,
    severity: str,
    agent_type: str = "",
    task_type: str = "",
) -> dict:
    """Feed correction severity as reward signal to the Q-learning router.

    Called after brain.correct() when agent_type is known.
    """
    if not brain._learning_pipeline:
        return {"processed": False, "reason": "no_pipeline"}

    router = getattr(brain._learning_pipeline, "_router", None)
    if not router:
        return {"processed": False, "reason": "no_router"}

    try:
        reward = router.reward_from_severity(severity)
        from gradata.patterns.q_learning_router import RouteDecision
        decision = RouteDecision(
            agent=agent_type or "default",
            state_hash=str(hash(task_type) & 0xFFFFFFFF),
            confidence=reward,
            exploiting=True,
        )
        router.update_reward(decision, reward)
        return {"processed": True, "reward": reward, "agent": agent_type}
    except Exception as e:
        logger.debug("feed_q_router failed: %s", e)
        return {"processed": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 4. Evaluator → Graduation
# ---------------------------------------------------------------------------

def process_eval_result(
    brain: Brain,
    result: EvalLoopResult,
    category: str = "QUALITY",
) -> dict:
    """Feed evaluator verdicts into graduation confidence.

    - APPROVED (avg >= 8.0) → boost
    - MAJOR_REVISION (avg < 6.0) → penalty
    - Regression detected → contradiction penalty
    """
    from gradata.enhancements.self_improvement import (
        parse_lessons, format_lessons, update_confidence,
        ACCEPTANCE_BONUS,
    )

    if not result.iterations:
        return {"processed": False}

    final_iter = result.iterations[-1]
    avg = final_iter.average

    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        return {"processed": False}

    text = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(text)

    if result.converged and avg >= 8.0:
        for lesson in lessons:
            if lesson.category == category.upper():
                lesson.confidence = round(min(1.0, lesson.confidence + ACCEPTANCE_BONUS * 0.5), 2)
    elif avg < 6.0:
        correction_data = [{"category": category.upper(), "severity_label": "moderate"}]
        lessons = update_confidence(lessons, correction_data)

    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    return {"processed": True, "converged": result.converged, "average": avg}


# ---------------------------------------------------------------------------
# 5. Execute/Qualify → Graduation
# ---------------------------------------------------------------------------

def process_qualify_result(
    brain: Brain,
    result: ExecuteQualifyResult,
    category: str = "ACCURACY",
) -> dict:
    """Feed qualify PASS/GAP/DRIFT into graduation.

    - PASS → survival bonus for related lessons
    - GAP → minor correction (rule is incomplete)
    - DRIFT → moderate correction (rule is wrong)
    """
    from gradata.enhancements.self_improvement import (
        parse_lessons, format_lessons, update_confidence,
    )

    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        return {"processed": False}

    text = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(text)

    final_qualify = getattr(result, "final_qualify", None)
    if final_qualify is None:
        return {"processed": False}

    score = getattr(final_qualify, "score", None)
    score_name = score.name if score else "UNKNOWN"

    if score_name == "PASS":
        # Survival bonus
        for lesson in lessons:
            if lesson.category == category.upper():
                lesson.fire_count += 1
    elif score_name == "GAP":
        correction_data = [{"category": category.upper(), "severity_label": "minor",
                            "description": "Qualify GAP: rule incomplete"}]
        lessons = update_confidence(lessons, correction_data)
    elif score_name == "DRIFT":
        correction_data = [{"category": category.upper(), "severity_label": "moderate",
                            "description": "Qualify DRIFT: rule is wrong"}]
        lessons = update_confidence(lessons, correction_data)

    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    return {"processed": True, "score": score_name, "attempts": getattr(result, "attempts_used", 0)}


# ---------------------------------------------------------------------------
# 6. Reconciliation → Graduation
# ---------------------------------------------------------------------------

def process_reconciliation(
    brain: Brain,
    summary: ReconciliationSummary,
) -> dict:
    """Feed plan-vs-actual deviations into graduation.

    - PASS items → survival bonus for related lessons
    - GAP/DRIFT deviations → correction signals per category
    """
    from gradata.enhancements.self_improvement import (
        parse_lessons, format_lessons, update_confidence,
    )

    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        return {"processed": False}

    text = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(text)

    deviations = getattr(summary, "deviations", [])
    passes = 0
    gaps = 0

    for dev in deviations:
        score_name = getattr(getattr(dev, "score", None), "name", "UNKNOWN")
        category = getattr(dev, "category", "GENERAL").upper() if hasattr(dev, "category") else "GENERAL"

        if score_name == "PASS":
            passes += 1
        elif score_name in ("GAP", "DRIFT"):
            gaps += 1
            severity = "minor" if score_name == "GAP" else "moderate"
            correction_data = [{"category": category, "severity_label": severity,
                                "description": f"Reconciliation {score_name}: {getattr(dev, 'detail', '')}"}]
            lessons = update_confidence(lessons, correction_data)

    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    return {"processed": True, "passes": passes, "gaps": gaps}


# ---------------------------------------------------------------------------
# 7. Loop Detection → Graduation
# ---------------------------------------------------------------------------

def process_loop_event(
    brain: Brain,
    action: str,
    tool_name: str = "",
) -> dict:
    """Feed loop WARN/STOP events as PROCESS corrections.

    Loops indicate missing or wrong process rules.
    """
    from gradata.enhancements.self_improvement import (
        parse_lessons, format_lessons, update_confidence,
    )

    if action not in ("WARN", "STOP"):
        return {"processed": False}

    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        return {"processed": False}

    text = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(text)

    severity = "minor" if action == "WARN" else "major"
    correction_data = [{
        "category": "PROCESS",
        "severity_label": severity,
        "description": f"Loop detected on {tool_name}: {action}",
    }]
    lessons = update_confidence(lessons, correction_data)

    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    return {"processed": True, "action": action, "tool": tool_name}


# ---------------------------------------------------------------------------
# 8. Parallel Failures → Graduation
# ---------------------------------------------------------------------------

def process_parallel_failures(
    brain: Brain,
    failed_tasks: list[str],
    total_tasks: int,
) -> dict:
    """Feed parallel task failures as correction signals.

    High failure rate in parallel execution suggests process rules are weak.
    """
    if not failed_tasks or total_tasks == 0:
        return {"processed": False}

    from gradata.enhancements.self_improvement import (
        parse_lessons, format_lessons, update_confidence,
    )

    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        return {"processed": False}

    text = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(text)

    failure_rate = len(failed_tasks) / total_tasks
    severity = "major" if failure_rate > 0.5 else "moderate" if failure_rate > 0.2 else "minor"

    correction_data = [{
        "category": "PROCESS",
        "severity_label": severity,
        "description": f"Parallel failures: {len(failed_tasks)}/{total_tasks} tasks failed",
    }]
    lessons = update_confidence(lessons, correction_data)

    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    return {"processed": True, "failed": len(failed_tasks), "total": total_tasks}


# ---------------------------------------------------------------------------
# 9. Task Escalation → Graduation
# ---------------------------------------------------------------------------

def process_escalation(
    brain: Brain,
    status: str,
    concerns: list[str] | None = None,
    category: str = "PROCESS",
) -> dict:
    """Feed DONE_WITH_CONCERNS as low-severity self-assessment corrections."""
    if status != "DONE_WITH_CONCERNS" or not concerns:
        return {"processed": False}

    from gradata.enhancements.self_improvement import (
        parse_lessons, format_lessons, update_confidence,
    )

    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        return {"processed": False}

    text = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(text)

    for concern in concerns:
        correction_data = [{
            "category": category.upper(),
            "severity_label": "minor",
            "description": f"Self-assessment concern: {concern}",
        }]
        lessons = update_confidence(lessons, correction_data)

    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    return {"processed": True, "concerns": len(concerns)}


# ===========================================================================
# WAVE 4: Backward flow adapters (rules → improve patterns)
# ===========================================================================
# These are helper functions that patterns call to read graduated rules
# and adapt their behavior. They all query the RuleContext hub.


# ---------------------------------------------------------------------------
# 10. Pipeline — PROCESS rules become suggested pipeline gates
# ---------------------------------------------------------------------------

def gates_from_graduated_rules() -> list[dict]:
    """Return PROCESS rules as pipeline gate suggestions.

    Each rule becomes a dict with name + check description that callers
    can convert into Stage objects with gate functions.
    """
    try:
        from gradata.patterns.rule_context import get_rule_context
    except ImportError:
        return []

    ctx = get_rule_context()
    rules = ctx.query(category="PROCESS", min_confidence=0.60, limit=5)
    return [{"name": f"rule_gate_{i}", "rule": r.principle, "confidence": r.confidence}
            for i, r in enumerate(rules)]


# ---------------------------------------------------------------------------
# 11. Orchestrator — correction density adjusts routing
# ---------------------------------------------------------------------------

def routing_adjustments() -> dict[str, float]:
    """Return correction density per category for routing decisions.

    Categories with high density should get extra validation/reflection.
    """
    try:
        from gradata.patterns.rule_context import get_rule_context
    except ImportError:
        return {}

    ctx = get_rule_context()
    stats = ctx.stats()
    categories = stats.get("categories", {})
    total = stats.get("total_rules", 1)
    return {cat: count / total for cat, count in categories.items()}


# ---------------------------------------------------------------------------
# 12. Memory — rule categories define importance for reinforcement
# ---------------------------------------------------------------------------

def importance_categories() -> set[str]:
    """Return categories that have graduated rules (high importance).

    Memory systems should prioritize reinforcing memories in these categories.
    """
    try:
        from gradata.patterns.rule_context import get_rule_context
    except ImportError:
        return set()

    ctx = get_rule_context()
    stats = ctx.stats()
    return set(stats.get("categories", {}).keys())


# ---------------------------------------------------------------------------
# 13. Sub-agents — agent-specific rules for delegation criteria
# ---------------------------------------------------------------------------

def delegation_criteria_for_agent(agent_type: str) -> list[str]:
    """Return graduated rule principles scoped to a specific agent.

    These should be added to delegation success_criteria.
    """
    try:
        from gradata.patterns.rule_context import get_rule_context
    except ImportError:
        return []

    ctx = get_rule_context()
    rules = ctx.for_agent(agent_type)
    return [r.principle for r in rules]


# ---------------------------------------------------------------------------
# 14. Agent Modes — correction rate determines mode safety level
# ---------------------------------------------------------------------------

def suggested_mode_override() -> str | None:
    """Suggest a safer mode if correction density is high.

    Returns "SAFE" if overall correction density > 0.3, else None (no override).
    """
    try:
        from gradata.patterns.rule_context import get_rule_context
    except ImportError:
        return None

    ctx = get_rule_context()
    stats = ctx.stats()
    total = stats.get("total_rules", 0)
    rule_count = stats.get("rule_tier", 0)

    # If most rules are RULE tier, the system is mature → no override needed
    if total > 0 and rule_count / total > 0.5:
        return None

    # If many corrections but few graduations, system is still learning → suggest SAFE
    if total > 10 and rule_count < 3:
        return "SAFE"

    return None


# ---------------------------------------------------------------------------
# 15. Tools — register brain operations as discoverable tools
# ---------------------------------------------------------------------------

def register_brain_tools(brain: Brain) -> int:
    """Register brain.correct() and brain.apply_brain_rules() in ToolRegistry.

    Returns count of tools registered.
    """
    if not brain.tools:
        return 0

    try:
        from gradata.patterns.tools import ToolSpec
    except ImportError:
        return 0

    count = 0

    try:
        brain.tools.register(ToolSpec(
            name="brain_correct",
            description="Log a user correction for the learning pipeline",
            category="learning",
            parameters={"draft": "str", "final": "str"},
        ))
        count += 1
    except (ValueError, Exception):
        pass  # Already registered

    try:
        brain.tools.register(ToolSpec(
            name="brain_apply_rules",
            description="Get graduated rules for prompt injection",
            category="learning",
            parameters={"task": "str"},
            returns="str",
        ))
        count += 1
    except (ValueError, Exception):
        pass

    return count


# ---------------------------------------------------------------------------
# 16. MCP — additional tool schemas for rule management
# ---------------------------------------------------------------------------

def mcp_rule_tools() -> list[dict]:
    """Return MCP tool schemas for rule management.

    These can be added to the MCP server's tool list.
    """
    return [
        {
            "name": "brain_rules",
            "description": "Get currently active graduated rules for a task context",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_type": {"type": "string", "description": "Task type for scope filtering"},
                },
            },
        },
        {
            "name": "brain_rule_stats",
            "description": "Get rule context statistics (counts by category, tier distribution)",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


# ---------------------------------------------------------------------------
# 17. Scope — rule density refines scope matching
# ---------------------------------------------------------------------------

def scope_confidence_boost(category: str) -> float:
    """Return a confidence boost for scope matching in categories with rules.

    Categories with many graduated rules should match more precisely.
    Returns 0.0-0.5 boost value.
    """
    try:
        from gradata.patterns.rule_context import get_rule_context
    except ImportError:
        return 0.0

    ctx = get_rule_context()
    density = ctx.correction_density(category)
    return min(0.5, density * 2.0)


# ---------------------------------------------------------------------------
# 18. RAG — rule categories boost topic retrieval relevance
# ---------------------------------------------------------------------------

def topic_boosts_from_rules() -> dict[str, float]:
    """Return category-based boost multipliers for RAG retrieval.

    Categories with graduated rules get boosted relevance in search.
    """
    try:
        from gradata.patterns.rule_context import get_rule_context
    except ImportError:
        return {}

    ctx = get_rule_context()
    stats = ctx.stats()
    categories = stats.get("categories", {})
    total = max(stats.get("total_rules", 1), 1)

    # Categories with more rules get higher boost (1.0 + density * 0.5)
    return {cat: round(1.0 + (count / total) * 0.5, 2) for cat, count in categories.items()}


# ---------------------------------------------------------------------------
# 19. Rule Engine — assumption validation feeds back misfires
# ---------------------------------------------------------------------------

def process_rule_assumption_failure(
    brain: Brain,
    rule_description: str,
    reason: str,
) -> dict:
    """Feed rule assumption failures back as misfire signals."""
    from gradata.enhancements.self_improvement import (
        parse_lessons, format_lessons, update_confidence,
    )

    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        return {"processed": False}

    text = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(text)

    # Find and penalize the matching lesson
    for lesson in lessons:
        if lesson.description[:40] == rule_description[:40]:
            lesson.misfire_count += 1
            break

    correction_data = [{"category": "GENERAL", "severity_label": "minor",
                        "description": f"Rule assumption failed: {reason}"}]
    lessons = update_confidence(lessons, correction_data)
    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    return {"processed": True, "reason": reason}


# ---------------------------------------------------------------------------
# 20. Middleware — graduation middleware wraps operations
# ---------------------------------------------------------------------------

def create_graduation_middleware():
    """Create a Middleware that injects rules before and observes results after.

    Returns a Middleware instance (or None if patterns unavailable).
    """
    try:
        from gradata.patterns.middleware import Middleware, MiddlewareContext
        from gradata.patterns.rule_context import get_rule_context
    except ImportError:
        return None

    class GraduationMiddleware(Middleware):
        """Injects graduated rules into context before execution."""
        name: str = "graduation"

        def before(self, ctx: MiddlewareContext) -> MiddlewareContext:
            rule_ctx = get_rule_context()
            task_type = ctx.data.get("task_type", "")
            rules = rule_ctx.for_reflection(task_type=task_type)
            ctx.data["graduated_rules"] = [r.principle for r in rules]
            ctx.data["rules_budget"] = rule_ctx.rules_budget(
                ctx.data.get("context_bracket", "FRESH")
            )
            return ctx

        def after(self, ctx: MiddlewareContext) -> MiddlewareContext:
            # Observe: if result contains quality signals, they'll be
            # processed by the pattern-specific handlers above
            return ctx

    return GraduationMiddleware()


# ---------------------------------------------------------------------------
# 21. Loop Detection — PROCESS rules lower thresholds
# ---------------------------------------------------------------------------

def loop_threshold_adjustment() -> dict[str, int]:
    """Return adjusted loop detection thresholds based on PROCESS rules.

    More PROCESS rules = stricter loop detection (lower thresholds).
    """
    try:
        from gradata.patterns.rule_context import get_rule_context
    except ImportError:
        return {"warn": 3, "stop": 5}

    ctx = get_rule_context()
    process_rules = ctx.query(category="PROCESS", min_confidence=0.60, limit=20)

    # Default: warn at 3, stop at 5
    # With 5+ PROCESS rules: warn at 2, stop at 4
    # With 10+ PROCESS rules: warn at 2, stop at 3
    count = len(process_rules)
    if count >= 10:
        return {"warn": 2, "stop": 3}
    elif count >= 5:
        return {"warn": 2, "stop": 4}
    return {"warn": 3, "stop": 5}


# ---------------------------------------------------------------------------
# 22. Reconciliation — rule categories define strict deviation thresholds
# ---------------------------------------------------------------------------

def strict_categories_from_rules() -> set[str]:
    """Return categories where deviations should be scored as DRIFT not GAP.

    Categories with RULE-tier (0.90+) lessons are strict — any deviation
    from a proven rule is DRIFT, not just GAP.
    """
    try:
        from gradata.patterns.rule_context import get_rule_context
    except ImportError:
        return set()

    ctx = get_rule_context()
    rules = ctx.query(min_confidence=0.90, limit=50)
    return {r.category for r in rules}
