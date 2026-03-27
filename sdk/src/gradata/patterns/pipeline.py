"""
Sequential Pipeline Pattern
============================
Assembly-line execution of named stages with typed I/O and optional quality
gates per stage.  Each stage can retry on gate failure up to ``max_retries``
times before the pipeline halts.

SDK LAYER: Pure logic, stdlib only.  No file I/O, no imports from brain
internals.  Callers wire logging/event emission externally if desired.

Usage::

    from gradata.patterns.pipeline import Pipeline, Stage, GateResult, gate

    def research(query: str) -> dict:
        return {"findings": f"Research on {query}"}

    def draft(data: dict) -> str:
        return f"Email based on {data['findings']}"

    @gate
    def quality_check(text: str) -> bool:
        return len(text) > 10

    pipe = Pipeline(
        Stage("research", research),
        Stage("draft", draft, gate=quality_check),
    )
    result = pipe.run("pricing strategy")
    print(result.success, result.stages_completed)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    pass  # Reserved for future forward-reference imports


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GateResult:
    """The verdict emitted by a quality gate function.

    Args:
        passed: Whether the gate check succeeded.
        reason: Human-readable explanation of the decision.
        score:  Optional numeric score (0.0–1.0) for graded gates.
    """

    passed: bool
    reason: str
    score: float | None = None

    def __post_init__(self) -> None:
        if self.score is not None:
            if not (0.0 <= self.score <= 1.0):
                raise ValueError(
                    f"GateResult.score must be in [0.0, 1.0], got {self.score!r}"
                )


@dataclass
class StageLog:
    """Execution record for a single pipeline stage.

    Args:
        name:          Stage identifier.
        input_summary: First 100 characters of ``repr(input_data)``.
        output_summary: First 100 characters of ``repr(output_data)``.
        gate_result:   Gate verdict, or ``None`` if no gate was attached.
        duration_ms:   Wall-clock execution time in milliseconds.
        retries:       Number of retries attempted (0 = first attempt succeeded).
    """

    name: str
    input_summary: str
    output_summary: str
    gate_result: GateResult | None
    duration_ms: float
    retries: int


@dataclass
class PipelineResult:
    """Final result returned by :py:meth:`Pipeline.run`.

    Args:
        success:          ``True`` when all stages completed and passed their gates.
        output:           The value produced by the last completed stage, or the
                          raw input when no stages ran.
        stages_completed: Number of stages that ran to completion (gate included).
        stages_total:     Total number of stages registered in the pipeline.
        stage_logs:       Ordered execution records, one per completed attempt.
        total_duration_ms: Sum of all stage durations in milliseconds.
    """

    success: bool
    output: Any
    stages_completed: int
    stages_total: int
    stage_logs: list[StageLog] = field(default_factory=list)
    total_duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Decorator helper
# ---------------------------------------------------------------------------


def gate(fn: Callable[..., bool]) -> Callable[..., GateResult]:
    """Wrap a bool-returning function so it satisfies the gate protocol.

    The decorator converts ``True`` to ``GateResult(passed=True, reason="OK")``
    and ``False`` to ``GateResult(passed=False, reason="Gate check failed")``.

    Args:
        fn: A callable that accepts the stage output and returns ``bool``.

    Returns:
        A new callable with an identical signature that returns
        :class:`GateResult`.

    Example::

        @gate
        def is_long_enough(text: str) -> bool:
            return len(text) > 10
    """

    def _wrapper(*args: Any, **kwargs: Any) -> GateResult:
        passed: bool = bool(fn(*args, **kwargs))
        if passed:
            return GateResult(passed=True, reason="OK")
        return GateResult(passed=False, reason="Gate check failed")

    _wrapper.__name__ = getattr(fn, "__name__", "gate_wrapper")
    _wrapper.__doc__ = getattr(fn, "__doc__", None)
    return _wrapper


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


class Stage:
    """A single named step in a :class:`Pipeline`.

    Args:
        name:        Unique human-readable identifier for this stage.
        handler:     Callable that transforms the incoming value to an outgoing
                     value.  Signature: ``(Any) -> Any``.
        gate:        Optional quality-gate callable.  Must accept the handler
                     output and return a :class:`GateResult`.  If the gate
                     ``passed`` is ``False`` the stage retries the handler up to
                     ``max_retries`` times before the pipeline halts.
        max_retries: Maximum retry attempts when a gate fails.  Defaults to 3.
                     Set to 0 to disable retries entirely.
    """

    def __init__(
        self,
        name: str,
        handler: Callable[..., Any],
        gate: Callable[..., GateResult] | None = None,
        max_retries: int = 3,
    ) -> None:
        if not callable(handler):
            raise TypeError(f"Stage '{name}': handler must be callable, got {type(handler)!r}")
        if gate is not None and not callable(gate):
            raise TypeError(f"Stage '{name}': gate must be callable or None, got {type(gate)!r}")
        if max_retries < 0:
            raise ValueError(f"Stage '{name}': max_retries must be >= 0, got {max_retries!r}")

        self.name = name
        self.handler = handler
        self.gate = gate
        self.max_retries = max_retries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, input_data: Any) -> tuple[Any, GateResult | None, int]:
        """Execute the handler, then run the gate check.

        The method retries the handler on gate failure up to
        :attr:`max_retries` times.  The *same* ``input_data`` is passed to
        every attempt — it is the caller's responsibility to inject varied
        input when true retry semantics are needed.

        Args:
            input_data: Value passed to the handler callable.

        Returns:
            A 3-tuple of:
            - ``output``: The handler result from the last attempt.
            - ``gate_result``: The :class:`GateResult` from the gate check on
              the last attempt, or ``None`` when no gate is attached.
            - ``retries``: Number of retry attempts performed (0 on first-pass
              success).

        Raises:
            Exception: Any unhandled exception raised by the handler or gate
                       propagates unchanged so the pipeline can record it.
        """
        retries = 0
        output: Any = None
        gate_result: GateResult | None = None

        while True:
            output = self.handler(input_data)

            if self.gate is None:
                break

            gate_result = self.gate(output)

            # Gate passed — done
            if gate_result.passed:
                break

            # Gate failed — retry or give up
            if retries < self.max_retries:
                retries += 1
            else:
                # Retries exhausted; surface the failure
                break

        return output, gate_result, retries

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        gate_label = self.gate.__name__ if self.gate is not None else "none"
        return (
            f"Stage(name={self.name!r}, gate={gate_label!r}, "
            f"max_retries={self.max_retries!r})"
        )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

_SUMMARY_LIMIT = 100


def _summarise(value: Any) -> str:
    """Return the first ``_SUMMARY_LIMIT`` characters of ``repr(value)``."""
    text = repr(value)
    if len(text) <= _SUMMARY_LIMIT:
        return text
    return text[:_SUMMARY_LIMIT] + "..."


class Pipeline:
    """Execute a sequence of :class:`Stage` objects, threading output to input.

    Stages run sequentially.  The output of stage *N* becomes the input of
    stage *N+1*.  Execution halts immediately when a stage's gate fails and
    retries are exhausted.

    Args:
        *stages: One or more :class:`Stage` instances to execute in order.

    Raises:
        ValueError: When constructed with no stages.

    Example::

        pipe = Pipeline(
            Stage("research", research_fn),
            Stage("draft", draft_fn, gate=quality_gate),
        )
        result = pipe.run("AI pricing strategy")
        if not result.success:
            print("Pipeline halted at stage", result.stages_completed)
    """

    def __init__(self, *stages: Stage) -> None:
        if not stages:
            raise ValueError("Pipeline requires at least one Stage.")
        # Accept Stage instances only; reject plain callables to surface config errors early.
        for idx, s in enumerate(stages):
            if not isinstance(s, Stage):
                raise TypeError(
                    f"Pipeline argument {idx} must be a Stage instance, got {type(s)!r}"
                )
        self._stages: tuple[Stage, ...] = stages

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, input_data: Any) -> PipelineResult:
        """Execute all stages in order.

        Args:
            input_data: The initial value fed into the first stage.

        Returns:
            A :class:`PipelineResult` describing the overall outcome, the final
            output value, per-stage logs, and cumulative timing.

        Notes:
            - Exceptions from handlers or gates propagate immediately; partial
              ``stage_logs`` are not returned on unhandled exceptions.
            - ``total_duration_ms`` is the sum of individual stage durations
              (wall-clock), not wall-clock from call to return.
        """
        current: Any = input_data
        logs: list[StageLog] = []
        total_ms = 0.0
        success = True

        for stage in self._stages:
            input_summary = _summarise(current)
            t_start = time.perf_counter()

            output, gate_result, retries = stage.run(current)

            duration_ms = (time.perf_counter() - t_start) * 1000.0
            total_ms += duration_ms

            output_summary = _summarise(output)
            log = StageLog(
                name=stage.name,
                input_summary=input_summary,
                output_summary=output_summary,
                gate_result=gate_result,
                duration_ms=round(duration_ms, 3),
                retries=retries,
            )
            logs.append(log)

            # Gate failed after exhausting retries — halt
            if gate_result is not None and not gate_result.passed:
                success = False
                return PipelineResult(
                    success=False,
                    output=output,
                    stages_completed=len(logs) - 1,  # this stage did not fully complete
                    stages_total=len(self._stages),
                    stage_logs=logs,
                    total_duration_ms=round(total_ms, 3),
                )

            current = output

        return PipelineResult(
            success=success,
            output=current,
            stages_completed=len(logs),
            stages_total=len(self._stages),
            stage_logs=logs,
            total_duration_ms=round(total_ms, 3),
        )

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of stages in this pipeline."""
        return len(self._stages)

    def __repr__(self) -> str:
        stage_names = ", ".join(s.name for s in self._stages)
        return f"Pipeline(stages=[{stage_names}])"
