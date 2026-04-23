"""
Execute/Qualify — Fresh verification loop with diagnostic routing.
==================================================================
Adapted from: paul (ChristopherKahler/paul) checkpoints.md, apply-phase.md

Enforces a disciplined execute-then-verify loop:
1. Execute the task
2. Report status (DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED)
3. Qualify: re-read output files fresh, run verification, compare to spec
4. Score: PASS/GAP/DRIFT
5. On failure: classify root cause (intent/spec/code) and retry (max 3)

The key insight: never trust memory. Always re-read files after execution.

Usage::

    from gradata.contrib.patterns.execute_qualify import (
        ExecuteQualifyLoop, QualifyResult, FailureClassification,
    )

    loop = ExecuteQualifyLoop(max_attempts=3)
    result = loop.run(
        executor=my_executor,
        qualifier=my_qualifier,
        task_spec="Implement login endpoint",
    )
    print(result.passed)        # True/False
    print(result.attempts_used) # 1-3
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from gradata.contrib.patterns.task_escalation import TaskOutcome, TaskStatus

__all__ = [
    "ExecuteQualifyLoop",
    "ExecuteQualifyResult",
    "ExecutorFn",
    "FailureClassification",
    "FixerFn",
    "QualifierFn",
    "QualifyResult",
    "QualifyScore",
]


class QualifyScore(Enum):
    """Qualification score from fresh verification."""

    PASS = "pass"
    GAP = "gap"
    DRIFT = "drift"


class FailureClassification(Enum):
    """Root cause classification for qualification failures.

    Determines the correct fix strategy:
    - INTENT: The plan's goal was wrong. Replan with updated intent.
    - SPEC: The acceptance criteria were wrong. Fix plan first, then code.
    - CODE: Implementation doesn't match correct plan. Fix code in place.
    """

    INTENT = "intent"
    SPEC = "spec"
    CODE = "code"


@dataclass
class QualifyResult:
    """Result from a single qualify pass.

    Attributes:
        score: PASS, GAP, or DRIFT.
        evidence: Proof of verification.
        classification: Root cause if score != PASS.
        concerns: Issues found during qualification.
    """

    score: QualifyScore
    evidence: str = ""
    classification: FailureClassification | None = None
    concerns: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.score == QualifyScore.PASS


@dataclass
class ExecuteQualifyResult:
    """Aggregate result from the full execute/qualify loop.

    Attributes:
        passed: Whether the task ultimately passed qualification.
        attempts_used: How many execute+qualify cycles were run.
        max_attempts: The ceiling configured on the loop.
        final_outcome: The last TaskOutcome from execution.
        final_qualify: The last QualifyResult from verification.
        attempt_history: Full history of (outcome, qualify) pairs.
    """

    passed: bool
    attempts_used: int
    max_attempts: int
    final_outcome: TaskOutcome | None = None
    final_qualify: QualifyResult | None = None
    attempt_history: list[tuple[TaskOutcome, QualifyResult | None]] = field(default_factory=list)


# Type aliases for callables
ExecutorFn = Callable[[str, int], TaskOutcome]
QualifierFn = Callable[[TaskOutcome, str], QualifyResult]
FixerFn = Callable[[TaskOutcome, QualifyResult, int], None]


class ExecuteQualifyLoop:
    """Disciplined execute-then-verify loop with diagnostic routing.

    The loop enforces:
    1. Execute the task
    2. If NEEDS_CONTEXT or BLOCKED, stop immediately
    3. Qualify: fresh verification against spec
    4. If PASS, done
    5. If GAP/DRIFT, classify root cause and retry (up to max_attempts)

    Args:
        max_attempts: Maximum number of execute+qualify cycles (default 3).
    """

    def __init__(self, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
        self.max_attempts = max_attempts

    def run(
        self,
        executor: ExecutorFn,
        qualifier: QualifierFn,
        task_spec: str,
        fixer: FixerFn | None = None,
    ) -> ExecuteQualifyResult:
        """Run the full execute/qualify loop.

        Args:
            executor: Callable ``(task_spec, attempt) -> TaskOutcome``.
                Executes the task and returns a structured outcome.
            qualifier: Callable ``(outcome, task_spec) -> QualifyResult``.
                Verifies the outcome by re-reading files and running checks.
                Must perform fresh reads, never trust memory.
            task_spec: The task specification/acceptance criteria.
            fixer: Optional callable ``(outcome, qualify_result, attempt) -> None``.
                Called between attempts when qualification fails. Should
                apply fixes based on the failure classification.

        Returns:
            An ExecuteQualifyResult with the full attempt history.
        """
        history: list[tuple[TaskOutcome, QualifyResult | None]] = []

        for attempt in range(1, self.max_attempts + 1):
            # Step 1: Execute
            outcome = executor(task_spec, attempt)

            # Step 2: Check if execution itself failed
            if outcome.status in (TaskStatus.NEEDS_CONTEXT, TaskStatus.BLOCKED):
                history.append((outcome, None))
                return ExecuteQualifyResult(
                    passed=False,
                    attempts_used=attempt,
                    max_attempts=self.max_attempts,
                    final_outcome=outcome,
                    final_qualify=None,
                    attempt_history=history,
                )

            # Step 3: Qualify — fresh verification
            qualify = qualifier(outcome, task_spec)
            history.append((outcome, qualify))

            # Step 4: Check qualification
            if qualify.passed:
                return ExecuteQualifyResult(
                    passed=True,
                    attempts_used=attempt,
                    max_attempts=self.max_attempts,
                    final_outcome=outcome,
                    final_qualify=qualify,
                    attempt_history=history,
                )

            # Step 5: If not last attempt, apply fix
            if attempt < self.max_attempts and fixer is not None:
                fixer(outcome, qualify, attempt)

        # Exhausted all attempts
        last_outcome, last_qualify = history[-1]
        return ExecuteQualifyResult(
            passed=False,
            attempts_used=self.max_attempts,
            max_attempts=self.max_attempts,
            final_outcome=last_outcome,
            final_qualify=last_qualify,
            attempt_history=history,
        )
