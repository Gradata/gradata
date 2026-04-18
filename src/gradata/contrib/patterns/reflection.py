"""
Self-Critique / Reflection Pattern — Generate-Critique-Refine Loop
==================================================================
SDK LAYER: Pure logic, stdlib only, no file I/O.
Implements the Reflection agentic pattern: an output is repeatedly
critiqued against a structured checklist and refined until all
required criteria pass or the cycle budget is exhausted.

Typical usage::

    from .reflection import (
        reflect,
        EMAIL_CHECKLIST,
        CriterionScore,
        default_evaluator,
    )

    def my_refiner(output, failed):
        # call your LLM here
        return improved_output

    result = reflect(
        output=draft_email,
        checklist=EMAIL_CHECKLIST,
        evaluator=default_evaluator,
        refiner=my_refiner,
        max_cycles=3,
    )
    print(result.final_output)
    print(result.converged)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Criterion:
    """A single evaluation criterion within a critique checklist.

    Args:
        name: Short identifier, e.g. ``"accuracy"``.
        question: Natural-language question used during evaluation,
            e.g. ``"Are all facts verifiable?"``.
        required: When ``True``, failing this criterion prevents
            convergence and triggers another refinement cycle.
        weight: Relative weight used when computing the weighted
            average ``overall_score`` (must be > 0).
    """

    name: str
    question: str
    required: bool = True
    weight: float = 1.0

    def __post_init__(self) -> None:
        if self.weight <= 0:
            raise ValueError(f"Criterion '{self.name}': weight must be > 0, got {self.weight}")


@dataclass
class CriterionScore:
    """The evaluation result for a single :class:`Criterion`.

    Args:
        name: Must match the associated :attr:`Criterion.name`.
        passed: Whether the criterion was satisfied.
        reason: Human-readable explanation of the verdict.
        score: Optional numeric score on a 0-10 scale.  When
            provided it participates in :attr:`CritiqueResult.overall_score`.
    """

    name: str
    passed: bool
    reason: str
    score: float | None = None

    def __post_init__(self) -> None:
        if self.score is not None and not (0.0 <= self.score <= 10.0):
            raise ValueError(
                f"CriterionScore '{self.name}': score must be in [0, 10], got {self.score}"
            )


@dataclass
class CritiqueResult:
    """Aggregated result of one full checklist evaluation pass.

    Args:
        scores: Mapping of criterion name to its
            :class:`CriterionScore`.
        all_required_passed: ``True`` when every
            :attr:`Criterion.required` criterion passed.
        overall_score: Weighted average of all *numeric* scores
            (those where :attr:`CriterionScore.score` is not
            ``None``).  ``0.0`` when no numeric scores are present.
        cycle: 1-based index of the refinement cycle that produced
            this result.
    """

    scores: dict[str, CriterionScore]
    all_required_passed: bool
    overall_score: float
    cycle: int


@dataclass
class ReflectionResult:
    """Full history of a reflection loop run.

    Args:
        final_output: The output after the last cycle (refined or
            original if convergence was immediate).
        critiques: One :class:`CritiqueResult` per cycle executed,
            in chronological order.
        cycles_used: Total number of evaluate-refine cycles
            completed.
        converged: ``True`` when the final critique had
            :attr:`CritiqueResult.all_required_passed` equal to
            ``True``.
    """

    final_output: Any
    critiques: list[CritiqueResult] = field(default_factory=list)
    cycles_used: int = 0
    converged: bool = False


# ---------------------------------------------------------------------------
# CritiqueChecklist
# ---------------------------------------------------------------------------


class CritiqueChecklist:
    """An ordered collection of :class:`Criterion` objects.

    Evaluates an arbitrary output by delegating each criterion to a
    caller-supplied *evaluator* function, then aggregates the
    individual :class:`CriterionScore` results into a single
    :class:`CritiqueResult`.

    Args:
        *criteria: One or more :class:`Criterion` instances.
            Names must be unique within a checklist.

    Raises:
        ValueError: If no criteria are supplied or if two criteria
            share the same name.

    Example::

        checklist = CritiqueChecklist(
            Criterion("length", "Is the output under 200 words?"),
            Criterion("cta", "Does it include a call to action?"),
        )
        result = checklist.evaluate(my_output, my_evaluator)
    """

    def __init__(self, *criteria: Criterion) -> None:
        if not criteria:
            raise ValueError("CritiqueChecklist requires at least one Criterion.")
        names = [c.name for c in criteria]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"CritiqueChecklist: duplicate criterion names: {duplicates}")
        self._criteria: tuple[Criterion, ...] = criteria

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def criteria_names(self) -> list[str]:
        """Return criterion names in definition order."""
        return [c.name for c in self._criteria]

    def evaluate(
        self,
        output: Any,
        evaluator: Callable[[Any, Criterion], CriterionScore],
        cycle: int = 1,
    ) -> CritiqueResult:
        """Run *evaluator* against every criterion and return a :class:`CritiqueResult`.

        Args:
            output: The artifact to critique (string, dict, or any
                domain object).
            evaluator: A callable with signature
                ``(output, criterion) -> CriterionScore``.  It is
                invoked once per criterion in definition order.
            cycle: The 1-based refinement cycle number recorded in
                the returned :class:`CritiqueResult`.

        Returns:
            A fully populated :class:`CritiqueResult`.
        """
        scores: dict[str, CriterionScore] = {}
        for criterion in self._criteria:
            criterion_score = evaluator(output, criterion)
            scores[criterion.name] = criterion_score

        all_required_passed = all(scores[c.name].passed for c in self._criteria if c.required)
        _weight_map = {c.name: c.weight for c in self._criteria}
        _total_weight = 0.0
        _weighted_sum = 0.0
        for _name, _cs in scores.items():
            if _cs.score is not None:
                _w = _weight_map.get(_name, 1.0)
                _weighted_sum += _cs.score * _w
                _total_weight += _w
        overall_score = round(_weighted_sum / _total_weight, 2) if _total_weight > 0.0 else 0.0

        return CritiqueResult(
            scores=scores,
            all_required_passed=all_required_passed,
            overall_score=overall_score,
            cycle=cycle,
        )


# ---------------------------------------------------------------------------
# Core reflect() function
# ---------------------------------------------------------------------------


def reflect(
    output: Any,
    checklist: CritiqueChecklist,
    evaluator: Callable[[Any, Criterion], CriterionScore],
    refiner: Callable[[Any, list[CriterionScore]], Any],
    max_cycles: int = 3,
) -> ReflectionResult:
    """Run the generate-critique-refine loop.

    The loop proceeds as follows for each cycle:

    1. Evaluate *output* against *checklist* using *evaluator*.
    2. If all required criteria pass, record the critique and return
       immediately (``converged=True``).
    3. Otherwise collect the failing :class:`CriterionScore` objects,
       pass them to *refiner*, and repeat with the refined output.
    4. After *max_cycles* evaluations without convergence, return
       with ``converged=False`` and the best available output.

    Args:
        output: Initial artifact to be critiqued and refined.
        checklist: The :class:`CritiqueChecklist` defining pass/fail
            criteria.
        evaluator: ``(output, criterion) -> CriterionScore``.
            Called once per criterion per cycle.
        refiner: ``(output, failed_criteria) -> refined_output``.
            Receives the current output and the list of
            :class:`CriterionScore` objects that *failed*.  Must
            return a new (or unchanged) output.
        max_cycles: Maximum number of evaluate-refine cycles to
            attempt before giving up.  Must be >= 1.

    Returns:
        :class:`ReflectionResult` containing the final output, full
        critique history, cycle count, and convergence flag.

    Raises:
        ValueError: If *max_cycles* is less than 1.

    Example::

        result = reflect(
            output=draft,
            checklist=EMAIL_CHECKLIST,
            evaluator=default_evaluator,
            refiner=lambda out, failed: out + " [revised]",
            max_cycles=3,
        )
        assert result.cycles_used >= 1
    """
    if max_cycles < 1:
        raise ValueError(f"max_cycles must be >= 1, got {max_cycles}")

    current_output = output
    critiques: list[CritiqueResult] = []

    for cycle in range(1, max_cycles + 1):
        critique = checklist.evaluate(current_output, evaluator, cycle=cycle)
        critiques.append(critique)

        if critique.all_required_passed:
            return ReflectionResult(
                final_output=current_output,
                critiques=critiques,
                cycles_used=cycle,
                converged=True,
            )

        # Collect failing scores to guide the refiner
        failed: list[CriterionScore] = [s for s in critique.scores.values() if not s.passed]

        # Only refine if there are cycles remaining
        if cycle < max_cycles:
            current_output = refiner(current_output, failed)

    return ReflectionResult(
        final_output=current_output,
        critiques=critiques,
        cycles_used=max_cycles,
        converged=False,
    )


# ---------------------------------------------------------------------------
# Default evaluator (baseline / override-friendly)
# ---------------------------------------------------------------------------


def default_evaluator(output: Any, criterion: Criterion) -> CriterionScore:
    """Baseline evaluator using heuristic length and content checks.

    This implementation handles common structural criteria by name so
    that the predefined checklists work out of the box.  Domain-
    specific deployments should replace this with an LLM-backed or
    rule-based evaluator tailored to their output format.

    Recognised criterion names and their heuristic logic:

    ``has_subject``
        Passes when *output* (as a string) contains the word
        ``"subject:"`` (case-insensitive).

    ``has_cta``
        Passes when *output* contains any of a fixed set of common
        call-to-action phrases (book, schedule, reply, click, visit,
        call, download, sign up, learn more, get started).

    ``appropriate_length``
        Passes when the word count is under 200.

    ``no_jargon``
        Passes when none of a small list of jargon tokens appears in
        the output.

    Any unrecognised criterion name falls back to a non-empty string
    check: the output passes if it is a non-empty string.

    Args:
        output: The artifact to evaluate.  Coerced to ``str`` for all
            checks.
        criterion: The :class:`Criterion` to evaluate against.

    Returns:
        A :class:`CriterionScore` with ``score`` set to ``10.0`` on
        pass and ``0.0`` on fail.
    """
    text = str(output)
    name = criterion.name.lower()

    if name == "has_subject":
        passed = "subject:" in text.lower()
        reason = "Found 'Subject:' header." if passed else "No 'Subject:' header detected."

    elif name == "has_cta":
        cta_phrases = (
            "book",
            "schedule",
            "reply",
            "click",
            "visit",
            "call",
            "download",
            "sign up",
            "learn more",
            "get started",
        )
        matched = next((p for p in cta_phrases if p in text.lower()), None)
        passed = matched is not None
        reason = (
            f"Call-to-action phrase found: '{matched}'."
            if passed
            else "No recognisable call-to-action phrase found."
        )

    elif name == "appropriate_length":
        word_count = len(text.split())
        passed = word_count < 200
        reason = (
            f"Word count {word_count} is within the 200-word limit."
            if passed
            else f"Word count {word_count} exceeds the 200-word limit."
        )

    elif name == "no_jargon":
        jargon_tokens = (
            "synergy",
            "leverage",
            "paradigm",
            "disruptive",
            "holistic",
            "bandwidth",
            "circle back",
            "deep dive",
        )
        found = [j for j in jargon_tokens if j in text.lower()]
        passed = len(found) == 0
        reason = "No jargon detected." if passed else f"Jargon detected: {found}."

    else:
        # Generic fallback: non-empty string
        passed = isinstance(output, str) and len(output.strip()) > 0
        reason = "Output is a non-empty string." if passed else "Output is empty or not a string."

    return CriterionScore(
        name=criterion.name,
        passed=passed,
        reason=reason,
        score=10.0 if passed else 0.0,
    )


# ---------------------------------------------------------------------------
# Predefined checklists
# ---------------------------------------------------------------------------

EMAIL_CHECKLIST = CritiqueChecklist(
    Criterion(
        name="has_subject",
        question="Does the email have a clear subject?",
        required=True,
        weight=1.5,
    ),
    Criterion(
        name="has_cta",
        question="Is there a clear call to action?",
        required=True,
        weight=2.0,
    ),
    Criterion(
        name="appropriate_length",
        question="Is the email concise (under 200 words)?",
        required=True,
        weight=1.0,
    ),
    Criterion(
        name="no_jargon",
        question="Is it free of unnecessary jargon?",
        required=False,
        weight=0.5,
    ),
)


# ---------------------------------------------------------------------------
# RuleContext integration — graduated rules become reflection criteria
# ---------------------------------------------------------------------------


def criteria_from_graduated_rules(task_type: str = "") -> list[Criterion]:
    """Build Criterion objects from graduated rules in the RuleContext.

    Graduated PATTERN/RULE-tier lessons automatically become reflection
    criteria, so the critique checklist grows from corrections.

    Example: A TONE rule "keep it casual in cold emails" becomes a Criterion
    that checks whether the output uses casual tone.
    """
    try:
        from ...rules.rule_context import get_rule_context
    except ImportError:
        return []

    ctx = get_rule_context()
    rules = ctx.for_reflection(task_type=task_type)

    criteria = []
    for rule in rules:
        criteria.append(
            Criterion(
                name=f"rule_{rule.category.lower()}_{len(criteria)}",
                question=f"Does the output follow this rule: {rule.principle}?",
                required=rule.is_rule_tier,  # RULE tier = required, PATTERN = optional
                weight=rule.confidence,
            )
        )
    return criteria
