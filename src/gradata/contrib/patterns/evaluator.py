"""
Evaluator-Optimizer Pattern
============================
Two independent agents collaborate in a quality loop:

  1. A **generator** produces candidate output for a given task.
  2. An **evaluator** scores the output against a set of weighted dimensions.
  3. If the weighted average falls below the threshold, the generator is called
     again with the evaluator's feedback attached.
  4. The loop terminates when the threshold is met or the iteration budget is
     exhausted.

Domain-agnostic
---------------
This module contains **zero** domain-specific logic.  Callers supply:

* The generator callable (any domain).
* The evaluator callable (any domain).
* The dimension set appropriate for the task type.

The predefined ``QUALITY_DIMENSIONS`` list provides a reasonable generic
starting point that can be overridden or extended for any domain.

Stdlib only — no third-party dependencies.

Example
-------
    from .evaluator import (
        evaluate_optimize_loop,
        QUALITY_DIMENSIONS,
    )

    def my_generator(task, feedback=None):
        # call an LLM, run a template, anything...
        return generated_text

    def my_evaluator(output, dimension):
        # call an LLM judge, run heuristics, anything...
        score = ...
        rationale = ...
        return score, rationale

    result = evaluate_optimize_loop(
        generator=my_generator,
        evaluator=my_evaluator,
        task="Summarize the quarterly results",
        dimensions=QUALITY_DIMENSIONS,
        threshold=8.0,
        max_iterations=4,
    )
    print(result.final_output)
    print(result.converged)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_APPROVED_THRESHOLD: float = 8.0
_REVISION_THRESHOLD: float = 6.0

_VERDICT_APPROVED = "APPROVED"
_VERDICT_NEEDS_REVISION = "NEEDS_REVISION"
_VERDICT_MAJOR_REVISION = "MAJOR_REVISION"

# Baseline heuristic: outputs shorter than this are flagged as potentially
# incomplete.  The value is intentionally conservative; domain evaluators
# should override with task-appropriate checks.
_MIN_MEANINGFUL_LENGTH: int = 30


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EvalDimension:
    """A single scoring axis used by the evaluator.

    Attributes:
        name: Machine-readable identifier (e.g. ``"task_alignment"``).
        weight: Relative importance.  Weights need not sum to any particular
            value; the loop normalises them internally.
        description: Human-readable explanation of what this dimension
            measures.  Passed to the evaluator callable so that an LLM-backed
            judge can produce relevant rationale.
    """

    name: str
    weight: float = 1.0
    description: str = ""


@dataclass
class EvalResult:
    """Outcome of one evaluation pass.

    Attributes:
        scores: Mapping of dimension name to raw score (0–10).
        average: Weighted average of all dimension scores.
        verdict: One of ``"APPROVED"``, ``"NEEDS_REVISION"``, or
            ``"MAJOR_REVISION"``.
        feedback: Mapping of dimension name to the evaluator's rationale
            string for that dimension.
        regression: ``True`` when ``average`` dropped compared to the
            immediately preceding iteration.
    """

    scores: dict[str, float]
    average: float
    verdict: str
    feedback: dict[str, str]
    regression: bool = False


@dataclass
class EvalLoopResult:
    """Outcome of a full evaluator-optimizer loop.

    Attributes:
        final_output: The last output produced by the generator.
        iterations: Ordered list of ``EvalResult`` objects, one per loop
            iteration.
        converged: ``True`` when the final iteration received
            ``"APPROVED"`` verdict.
        total_iterations: Number of generator calls made.
    """

    final_output: Any
    iterations: list[EvalResult] = field(default_factory=list)
    converged: bool = False
    total_iterations: int = 0


# ---------------------------------------------------------------------------
# Predefined dimension sets
# ---------------------------------------------------------------------------

QUALITY_DIMENSIONS: list[EvalDimension] = [
    EvalDimension(
        name="task_alignment",
        weight=2.0,
        description="Does the output directly address what was asked?",
    ),
    EvalDimension(
        name="completeness",
        weight=1.5,
        description="Are all required elements present?  Is anything missing?",
    ),
    EvalDimension(
        name="accuracy",
        weight=2.0,
        description="Are the claims and facts correct given the task context?",
    ),
    EvalDimension(
        name="clarity",
        weight=1.0,
        description="Is the output clear, well-structured, and easy to understand?",
    ),
    EvalDimension(
        name="conciseness",
        weight=0.5,
        description="Is the output appropriately concise without sacrificing quality?",
    ),
]


# ---------------------------------------------------------------------------
# Default (heuristic) evaluator
# ---------------------------------------------------------------------------


def default_evaluator(output: Any, dimension: EvalDimension) -> tuple[float, str]:
    """Baseline heuristic evaluator for text outputs.

    Scores are derived from lightweight structural signals rather than
    semantic understanding.  Domain-specific evaluators — typically backed
    by an LLM judge — should replace this for production use.

    Heuristics applied per dimension
    ---------------------------------
    task_alignment
        Always returns 5.0 (unknown without semantic understanding).
    completeness
        Scores based on output length relative to ``_MIN_MEANINGFUL_LENGTH``.
    accuracy
        Always returns 5.0 (cannot be assessed heuristically).
    clarity
        Penalises excessively long single-paragraph outputs (> 2 000 chars)
        as a proxy for structural density.
    conciseness
        Rewards brevity: full marks when output is under 500 chars, scaling
        down towards zero at 5 000 chars.
    (unknown)
        Returns 5.0 with a note that no heuristic exists.

    Args:
        output: The candidate output.  Non-string values are coerced via
            ``str()`` before measurement.
        dimension: The dimension being scored.

    Returns:
        A ``(score, rationale)`` tuple where ``score`` is in ``[0, 10]``.
    """
    text = str(output) if not isinstance(output, str) else output
    length = len(text.strip())

    if dimension.name == "task_alignment":
        return 5.0, "Heuristic evaluator cannot assess alignment without semantic understanding."

    if dimension.name == "completeness":
        if length == 0:
            return 0.0, "Output is empty."
        if length < _MIN_MEANINGFUL_LENGTH:
            score = round(length / _MIN_MEANINGFUL_LENGTH * 5.0, 1)
            return score, f"Output is very short ({length} chars); may be incomplete."
        return 8.0, f"Output has sufficient length ({length} chars)."

    if dimension.name == "accuracy":
        return 5.0, "Heuristic evaluator cannot assess factual accuracy."

    if dimension.name == "clarity":
        # Proxy: a single dense block of text is harder to read than
        # structured output.  Paragraphs and line breaks improve clarity.
        newlines = text.count("\n")
        if length > 2_000 and newlines == 0:
            return 4.0, "Long output with no structure detected; consider breaking into sections."
        return 7.0, "No obvious structural issues detected."

    if dimension.name == "conciseness":
        if length <= 500:
            return 10.0, "Output is concise."
        if length >= 5_000:
            return 2.0, f"Output is very long ({length} chars); consider condensing."
        # Linear decay between 500 and 5000 chars: 10 -> 2
        score = round(10.0 - ((length - 500) / 4_500) * 8.0, 1)
        return score, f"Output length is {length} chars."

    return 5.0, f"No heuristic defined for dimension '{dimension.name}'."


# ---------------------------------------------------------------------------
# Core evaluation function
# ---------------------------------------------------------------------------


def evaluate(
    output: Any,
    dimensions: list[EvalDimension],
    evaluator: Callable[[Any, EvalDimension], tuple[float, str]],
    *,
    previous_result: EvalResult | None = None,
) -> EvalResult:
    """Score ``output`` across all ``dimensions`` and return an ``EvalResult``.

    The weighted average is computed as::

        average = sum(score_i * weight_i) / sum(weight_i)

    Verdict thresholds (applied to the weighted average)
    -----------------------------------------------------
    * ``>= 8.0`` -> ``"APPROVED"``
    * ``>= 6.0`` -> ``"NEEDS_REVISION"``
    * ``< 6.0``  -> ``"MAJOR_REVISION"``

    Args:
        output: The candidate output to evaluate.
        dimensions: Ordered list of scoring dimensions.  Must be non-empty.
        evaluator: Callable that accepts ``(output, dimension)`` and returns
            ``(score, rationale)`` where ``score`` is a float in ``[0, 10]``.
        previous_result: If supplied, ``EvalResult.regression`` is set to
            ``True`` when the new weighted average is lower than the previous
            one.

    Returns:
        A populated ``EvalResult``.

    Raises:
        ValueError: When ``dimensions`` is empty or any weight is non-positive.
    """
    if not dimensions:
        raise ValueError("At least one EvalDimension is required.")

    total_weight: float = 0.0
    weighted_sum: float = 0.0
    scores: dict[str, float] = {}
    feedback: dict[str, str] = {}

    for dim in dimensions:
        if dim.weight <= 0:
            raise ValueError(
                f"Dimension '{dim.name}' has non-positive weight {dim.weight!r}. "
                "All weights must be > 0."
            )
        raw_score, rationale = evaluator(output, dim)
        # Clamp to valid range — evaluator implementations may be imperfect.
        clamped = max(0.0, min(10.0, float(raw_score)))
        scores[dim.name] = round(clamped, 2)
        feedback[dim.name] = rationale
        weighted_sum += clamped * dim.weight
        total_weight += dim.weight
        logger.debug(
            "Evaluated dimension '%s': raw=%.2f clamped=%.2f weight=%.2f",
            dim.name,
            raw_score,
            clamped,
            dim.weight,
        )

    average = round(weighted_sum / total_weight, 3)

    if average >= _APPROVED_THRESHOLD:
        verdict = _VERDICT_APPROVED
    elif average >= _REVISION_THRESHOLD:
        verdict = _VERDICT_NEEDS_REVISION
    else:
        verdict = _VERDICT_MAJOR_REVISION

    regression = previous_result is not None and average < previous_result.average

    if regression and previous_result is not None:
        logger.warning(
            "Regression detected: score dropped from %.3f to %.3f.",
            previous_result.average,
            average,
        )

    return EvalResult(
        scores=scores,
        average=average,
        verdict=verdict,
        feedback=feedback,
        regression=regression,
    )


# ---------------------------------------------------------------------------
# Evaluator-Optimizer loop
# ---------------------------------------------------------------------------


def evaluate_optimize_loop(
    generator: Callable[..., Any],
    evaluator: Callable[[Any, EvalDimension], tuple[float, str]],
    task: Any,
    dimensions: list[EvalDimension],
    *,
    threshold: float = 8.0,
    max_iterations: int = 4,
) -> EvalLoopResult:
    """Run the evaluator-optimizer loop until convergence or budget exhaustion.

    Loop contract
    -------------
    1. First iteration: ``generator(task)`` — no feedback available yet.
    2. Subsequent iterations: ``generator(task, feedback=last_eval.feedback)``
       where ``feedback`` is the ``dict[str, str]`` from the previous
       ``EvalResult``.
    3. The loop terminates when ``EvalResult.average >= threshold`` or
       ``max_iterations`` calls have been made.

    Args:
        generator: Callable that produces output.  Must accept ``task`` as its
            first positional argument and optionally a ``feedback`` keyword
            argument (``dict[str, str]`` keyed by dimension name).
        evaluator: Callable passed directly to :func:`evaluate`.
        task: Arbitrary task descriptor forwarded to ``generator`` unchanged.
        dimensions: Scoring dimensions passed to :func:`evaluate`.
        threshold: Minimum weighted average score required for convergence.
            Must be in ``(0, 10]``.
        max_iterations: Hard upper bound on generator calls.  Must be >= 1.

    Returns:
        An ``EvalLoopResult`` containing the final output, the full iteration
        history, convergence status, and iteration count.

    Raises:
        ValueError: When ``threshold`` is out of range or ``max_iterations``
            is less than 1.
    """
    if not (0.0 < threshold <= 10.0):
        raise ValueError(f"threshold must be in (0, 10]; got {threshold!r}.")
    if max_iterations < 1:
        raise ValueError(f"max_iterations must be >= 1; got {max_iterations!r}.")

    iteration_results: list[EvalResult] = []
    current_output: Any = None
    previous_eval: EvalResult | None = None

    for iteration in range(1, max_iterations + 1):
        logger.debug("Loop iteration %d / %d", iteration, max_iterations)

        if iteration == 1:
            current_output = generator(task)
        else:
            fb = previous_eval.feedback if previous_eval is not None else {}
            current_output = generator(task, feedback=fb)

        result = evaluate(
            output=current_output,
            dimensions=dimensions,
            evaluator=evaluator,
            previous_result=previous_eval,
        )
        iteration_results.append(result)

        logger.info(
            "Iteration %d: average=%.3f verdict=%s regression=%s",
            iteration,
            result.average,
            result.verdict,
            result.regression,
        )

        if result.average >= threshold:
            logger.info("Threshold %.2f reached at iteration %d. Converged.", threshold, iteration)
            return EvalLoopResult(
                final_output=current_output,
                iterations=iteration_results,
                converged=True,
                total_iterations=iteration,
            )

        previous_eval = result

    logger.warning(
        "Max iterations (%d) reached without converging. Best average: %.3f (threshold: %.2f).",
        max_iterations,
        iteration_results[-1].average if iteration_results else 0.0,
        threshold,
    )
    return EvalLoopResult(
        final_output=current_output,
        iterations=iteration_results,
        converged=False,
        total_iterations=max_iterations,
    )


# ---------------------------------------------------------------------------
# RuleContext integration — graduated rules become evaluation dimensions
# ---------------------------------------------------------------------------


def dimensions_from_graduated_rules(task_type: str = "") -> list[EvalDimension]:
    """Build EvalDimension objects from graduated DRAFTING/STYLE/TONE rules.

    Graduated rules automatically become scoring dimensions, so the
    evaluator checklist grows from corrections.

    Example: A DRAFTING rule "no em dashes" becomes an EvalDimension
    that penalizes outputs containing em dashes.
    """
    try:
        from ...rules.rule_context import get_rule_context
    except ImportError:
        return []

    ctx = get_rule_context()
    rules = ctx.for_evaluator(task_type=task_type)

    dims = []
    for rule in rules:
        dims.append(
            EvalDimension(
                name=f"rule_{rule.category.lower()}_{len(dims)}",
                weight=rule.confidence,
                description=f"Check: {rule.principle}",
            )
        )
    return dims
