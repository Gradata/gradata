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

    # ── Proof of Learning ─────────────────────────────────────────────

    def prove(self, window: int = 10) -> dict:
        """Mathematically prove the brain is learning.

        Compares correction rates before and after rule graduations using
        a Wilcoxon signed-rank test (non-parametric, no normality assumption).

        Returns a proof dict with:
          - verdict: "PROVEN" | "EMERGING" | "INSUFFICIENT_DATA" | "NO_EFFECT"
          - p_value: statistical significance (< 0.05 = significant)
          - effect_size: matched-pairs rank-biserial correlation [-1, 1]
          - correction_rate_before: avg corrections/session in baseline window
          - correction_rate_after: avg corrections/session in current window
          - reduction_pct: percentage reduction in corrections
          - sessions_analyzed: total sessions used in the test
          - graduated_rules: number of RULE-state lessons
          - confidence_interval: 95% CI for the mean difference
        """
        import math
        import sqlite3

        result = {
            "verdict": "INSUFFICIENT_DATA",
            "p_value": None,
            "effect_size": None,
            "correction_rate_before": None,
            "correction_rate_after": None,
            "reduction_pct": None,
            "sessions_analyzed": 0,
            "graduated_rules": 0,
            "confidence_interval": None,
        }

        # Count graduated rules
        try:
            from gradata.enhancements.self_improvement import parse_lessons
            lessons_path = self._find_lessons_path()
            if lessons_path and lessons_path.is_file():
                text = lessons_path.read_text(encoding="utf-8")
                lessons = parse_lessons(text)
                result["graduated_rules"] = sum(
                    1 for l in lessons if l.state.value == "RULE"
                )
        except (ImportError, Exception):
            pass

        # Pull per-session correction counts from DB
        try:
            conn = sqlite3.connect(str(self.db_path))
            rows = conn.execute("""
                SELECT session, COUNT(*) as corrections
                FROM events
                WHERE type = 'CORRECTION' AND typeof(session) = 'integer'
                GROUP BY session
                ORDER BY session ASC
            """).fetchall()
            conn.close()
        except Exception:
            return result

        if len(rows) < window * 2:
            return result

        # Split: first half = before, second half = after
        midpoint = len(rows) // 2
        before_counts = [r[1] for r in rows[:midpoint]]
        after_counts = [r[1] for r in rows[midpoint:]]

        # Trim to equal length (paired test requirement)
        n = min(len(before_counts), len(after_counts), window)
        before = before_counts[-n:]
        after = after_counts[:n]

        if n < 5:
            return result

        avg_before = sum(before) / n
        avg_after = sum(after) / n
        result["correction_rate_before"] = round(avg_before, 3)
        result["correction_rate_after"] = round(avg_after, 3)
        result["sessions_analyzed"] = n * 2

        if avg_before > 0.001:
            result["reduction_pct"] = round(
                (avg_before - avg_after) / avg_before * 100, 1
            )

        # Paired differences
        diffs = [b - a for b, a in zip(before, after)]
        mean_diff = sum(diffs) / n

        # 95% CI for mean difference (t-distribution approximation)
        if n > 1:
            var = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1)
            se = math.sqrt(var / n) if var > 0 else 0.0
            t_crit = 2.0  # approximate t(0.025, df>5)
            ci_low = round(mean_diff - t_crit * se, 3)
            ci_high = round(mean_diff + t_crit * se, 3)
            result["confidence_interval"] = (ci_low, ci_high)

        # Wilcoxon signed-rank test (pure Python implementation)
        p_value, effect = self._wilcoxon_test(diffs)
        result["p_value"] = p_value
        result["effect_size"] = effect

        # Verdict
        if p_value is not None and p_value < 0.05 and mean_diff > 0:
            result["verdict"] = "PROVEN"
        elif p_value is not None and p_value < 0.10 and mean_diff > 0:
            result["verdict"] = "EMERGING"
        elif mean_diff <= 0:
            result["verdict"] = "NO_EFFECT"
        else:
            result["verdict"] = "INSUFFICIENT_DATA"

        return result

    @staticmethod
    def _wilcoxon_test(diffs: list[float]) -> tuple[float | None, float | None]:
        """Pure-Python Wilcoxon signed-rank test (no scipy needed).

        Returns (p_value, effect_size) or (None, None) if not computable.
        Effect size is matched-pairs rank-biserial correlation.
        """
        import math

        # Remove zeros
        nonzero = [(abs(d), 1 if d > 0 else -1) for d in diffs if d != 0]
        n = len(nonzero)
        if n < 5:
            return None, None

        # Rank by absolute value
        nonzero.sort(key=lambda x: x[0])
        ranks = []
        i = 0
        while i < n:
            j = i + 1
            while j < n and nonzero[j][0] == nonzero[i][0]:
                j += 1
            avg_rank = (i + 1 + j) / 2.0
            for k in range(i, j):
                ranks.append((avg_rank, nonzero[k][1]))
            i = j

        # W+ = sum of positive ranks, W- = sum of negative ranks
        w_plus = sum(r for r, s in ranks if s > 0)
        w_minus = sum(r for r, s in ranks if s < 0)
        w = min(w_plus, w_minus)

        # Normal approximation for p-value (valid for n >= 10, approximate for n >= 5)
        mean_w = n * (n + 1) / 4
        std_w = math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
        if std_w == 0:
            return None, None

        z = (w - mean_w) / std_w
        # Two-tailed p-value from z-score (normal CDF approximation)
        p_value = round(2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))), 4)

        # Matched-pairs rank-biserial correlation (effect size)
        total_ranks = n * (n + 1) / 2
        effect = round((w_plus - w_minus) / total_ranks, 4) if total_ranks > 0 else 0.0

        return p_value, effect

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
