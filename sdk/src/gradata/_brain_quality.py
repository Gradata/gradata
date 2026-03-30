"""Brain mixin — Quality, Classification, Health, Contracts, Guards, and Risk methods."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class BrainQualityMixin:
    """Pattern integration, health checks, contracts, guardrails, reflection, and risk for Brain."""

    # ── Pattern integration ──────────────────────────────────────────

    def classify(self, message: str) -> dict:
        """Classify a user message into intent, audience, pattern."""
        try:
            from gradata.patterns.orchestrator import classify_request
            c = classify_request(message)
            import dataclasses
            return dataclasses.asdict(c) if dataclasses.is_dataclass(c) else vars(c)
        except ImportError:
            return {"intent": "general", "selected_pattern": "pipeline"}

    def health(self) -> dict:
        """Generate brain health report."""
        try:
            try:
                from gradata_cloud.scoring.reports import generate_health_report
            except ImportError:
                from gradata.enhancements.reports import generate_health_report
            import dataclasses
            report = generate_health_report(self.db_path)
            return dataclasses.asdict(report)
        except ImportError:
            return {"healthy": True, "issues": []}

    def success_conditions(self, window: int = 20) -> dict:
        """Evaluate success conditions from SPEC.md Section 5."""
        try:
            try:
                from gradata_cloud.scoring.success_conditions import evaluate_success_conditions
            except ImportError:
                from gradata.enhancements.success_conditions import evaluate_success_conditions
            import dataclasses
            report = evaluate_success_conditions(self.db_path, window)
            return dataclasses.asdict(report)
        except ImportError:
            return {"all_met": False, "conditions": []}

    def register_contract(self, contract) -> None:
        """Register a CARL behavioral contract."""
        if self.contracts is not None:
            self.contracts.register(contract)

    def get_constraints(self, task: str) -> list[str]:
        """Get applicable CARL constraints for a task."""
        if self.contracts is not None:
            return self.contracts.get_constraints(task)
        return []

    def register_tool(self, spec, handler=None) -> None:
        """Register a tool in the brain's tool registry."""
        if self.tools is not None:
            self.tools.register(spec, handler)

    # ── Pattern API — new convenience methods ────────────────────────────

    def guard(self, text: str, direction: str = "input") -> dict:
        """Run guardrail checks on text. direction: ``"input"`` or ``"output"``."""
        from gradata.patterns.guardrails import (
            InputGuard,
            OutputGuard,
            banned_phrases,
            destructive_action,
            injection_detector,
            pii_detector,
        )
        if direction == "input":
            guard_obj = InputGuard(pii_detector, injection_detector)
            checks = guard_obj.check(text)
        else:
            guard_obj = OutputGuard(banned_phrases, destructive_action)
            checks = guard_obj.check(text)

        failing = [c for c in checks if c.result == "fail"]
        blocked = direction == "input" and bool(failing)
        return {
            "all_passed": not failing,
            "blocked": blocked,
            "block_reason": "; ".join(f"{c.name}: {c.details}" for c in failing) if failing else None,
            "checks": [{"name": c.name, "result": c.result, "details": c.details} for c in checks],
        }

    def reflect(
        self,
        draft: str,
        checklist=None,
        evaluator=None,
        refiner=None,
        max_cycles: int = 3,
    ) -> dict:
        """Run a generate-critique-refine reflection loop on a draft.

        Returns dict with ``final_output``, ``cycles_used``, ``converged``, ``critiques``.
        """
        from gradata.patterns.reflection import (
            EMAIL_CHECKLIST,
            default_evaluator,
        )
        from gradata.patterns.reflection import (
            reflect as _reflect,
        )

        if checklist is None:
            checklist = EMAIL_CHECKLIST
        if evaluator is None:
            evaluator = default_evaluator
        if refiner is None:
            refiner = lambda output, failed: output  # noqa: E731

        result = _reflect(
            output=draft,
            checklist=checklist,
            evaluator=evaluator,
            refiner=refiner,
            max_cycles=max_cycles,
        )
        return {
            "final_output": result.final_output,
            "cycles_used": result.cycles_used,
            "converged": result.converged,
            "critiques": [
                {
                    "cycle": c.cycle,
                    "all_required_passed": c.all_required_passed,
                    "overall_score": c.overall_score,
                }
                for c in result.critiques
            ],
        }

    def assess_risk(self, action: str, context: dict | None = None) -> dict:
        """Classify risk level of an action. Returns tier, reason, affected, reversible."""
        from gradata.patterns.human_loop import assess_risk as _assess_risk
        result = _assess_risk(action, context)
        return {
            "tier": result.tier,
            "reason": result.reason,
            "affected": result.affected,
            "reversible": result.reversible,
        }

    def track_rule(
        self,
        rule_id: str,
        accepted: bool,
        misfired: bool = False,
        contradicted: bool = False,
        session: int | None = None,
    ) -> dict | None:
        """Log a RULE_APPLICATION event. Returns event dict or None on failure."""
        from gradata.patterns.rule_tracker import log_application

        # Infer current session from events if not provided
        if session is None:
            try:
                from gradata._events import get_current_session
                session = get_current_session()
            except Exception:
                import sys
                print("[brain] WARNING: session detection failed, defaulting to 0", file=sys.stderr)
                session = 0

        return log_application(
            rule_id=rule_id,
            session=session,
            accepted=accepted,
            misfired=misfired,
            contradicted=contradicted,
        )

    def process_outcome_feedback(self, session: int | None = None) -> dict[str, float]:
        """Process external signal outcomes (DELTA_TAG) for confidence feedback.

        Returns {rule_id: confidence_delta} dict. Deltas are capped per tier
        and weighted below user corrections (external attribution is uncertain).
        Idempotent: processing the same session twice returns empty dict.
        """
        import logging
        logger = logging.getLogger("gradata")

        try:
            from gradata.enhancements.outcome_feedback import process_session_outcomes
            return process_session_outcomes(session, ctx=self.ctx)
        except ImportError:
            return {}
        except Exception as e:
            logger.warning("Outcome feedback processing failed: %s", e)
            return {}
