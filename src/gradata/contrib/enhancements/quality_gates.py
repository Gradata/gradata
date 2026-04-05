"""Quality Gates — 8.0 minimum threshold system with fix cycling.
=================================================================
SDK LAYER: Pure logic, no I/O, no domain-specific content.
Caller supplies scorer and fixer callables; this module orchestrates
the evaluate-fix-re-evaluate loop and surfaces structured verdicts.

Design decisions
----------------
* ``QualityGate`` is a plain class (not a dataclass) so its constructor
  can validate rubric weights without forcing callers to import field().
* ``default_scorer`` uses a minimal heuristic (length + keyword density)
  so the gate is usable without an LLM scorer during unit tests.
* Predefined rubric sets are module-level constants — callers can extend
  them with list concatenation or pass their own sets entirely.
* ``run_with_fix`` is the primary entry point; ``evaluate`` is exposed for
  callers that want a single-pass score without the fix loop.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class QualityRubric:
    """A single scoring dimension for quality evaluation.

    Args:
        name: Dimension identifier, e.g. ``"accuracy"`` or ``"tone"``.
        weight: Relative weight when computing the weighted average score.
            All rubrics in a gate are normalised so weights need not sum
            to 1.0; they are treated as ratios.
        threshold: Per-dimension minimum score (0-10).  Dimension scores
            below this value are listed in ``GateVerdict.failures``.
        description: Human-readable description used in scorer context.
    """

    name: str
    weight: float = 1.0
    threshold: float = 7.0
    description: str = ""

    def __post_init__(self) -> None:
        if self.weight <= 0:
            raise ValueError(f"QualityRubric '{self.name}': weight must be > 0")
        if not (0.0 <= self.threshold <= 10.0):
            raise ValueError(
                f"QualityRubric '{self.name}': threshold must be in [0, 10]"
            )


@dataclass
class GateVerdict:
    """Result from a single evaluation pass.

    Args:
        passed: True when ``overall_score >= gate threshold`` AND no
            dimension score is below that dimension's ``threshold``.
        overall_score: Weighted average across all rubric dimensions.
        dimension_scores: Mapping of ``rubric.name -> score (0-10)``.
        failures: Names of rubric dimensions whose score fell below
            their individual ``threshold``.
        cycle: 1-based index of the fix cycle that produced this verdict.
    """

    passed: bool
    overall_score: float
    dimension_scores: dict[str, float]
    failures: list[str]
    cycle: int


@dataclass
class QualityResult:
    """Aggregate result from ``QualityGate.run_with_fix``.

    Args:
        final_verdict: The last ``GateVerdict`` produced (pass or final fail).
        cycles_used: How many evaluate+fix cycles were executed.
        max_cycles: The ceiling configured on the gate.
        converged: True if the gate passed before exhausting ``max_cycles``.
    """

    final_verdict: GateVerdict
    cycles_used: int
    max_cycles: int
    converged: bool


# ---------------------------------------------------------------------------
# Predefined rubric sets
# ---------------------------------------------------------------------------

GENERAL_RUBRICS: list[QualityRubric] = [
    QualityRubric(
        name="accuracy",
        weight=2.0,
        threshold=7.0,
        description="Factual correctness and absence of hallucinated claims.",
    ),
    QualityRubric(
        name="completeness",
        weight=1.5,
        threshold=7.0,
        description="All required elements are present; nothing critical omitted.",
    ),
    QualityRubric(
        name="clarity",
        weight=1.0,
        threshold=7.0,
        description="Ideas are expressed without ambiguity.",
    ),
    QualityRubric(
        name="conciseness",
        weight=1.0,
        threshold=6.0,
        description="No unnecessary padding; signal-to-noise ratio is high.",
    ),
]

WRITING_RUBRICS: list[QualityRubric] = [
    QualityRubric(
        name="tone",
        weight=2.0,
        threshold=7.0,
        description="Voice and register match the intended audience.",
    ),
    QualityRubric(
        name="structure",
        weight=1.5,
        threshold=7.0,
        description="Logical flow; paragraphs build on each other.",
    ),
    QualityRubric(
        name="grammar",
        weight=1.0,
        threshold=8.0,
        description="Correct spelling, punctuation, and sentence construction.",
    ),
    QualityRubric(
        name="engagement",
        weight=1.0,
        threshold=6.5,
        description="Reader is compelled to continue; opening hooks attention.",
    ),
]

CODE_RUBRICS: list[QualityRubric] = [
    QualityRubric(
        name="correctness",
        weight=3.0,
        threshold=8.0,
        description="Logic produces the specified outputs for all known inputs.",
    ),
    QualityRubric(
        name="readability",
        weight=1.5,
        threshold=7.0,
        description="Names, comments, and structure communicate intent clearly.",
    ),
    QualityRubric(
        name="security",
        weight=2.0,
        threshold=8.0,
        description="No obvious injection vectors, hardcoded secrets, or unsafe I/O.",
    ),
    QualityRubric(
        name="test_coverage",
        weight=1.5,
        threshold=7.0,
        description="Critical paths have accompanying tests or are testable.",
    ),
]


# ---------------------------------------------------------------------------
# Default scorer
# ---------------------------------------------------------------------------

# Heuristic weights used by default_scorer to approximate output quality.
# These are intentionally conservative so they serve as a floor, not a ceiling.
_DEFAULT_IDEAL_LENGTH = 300  # characters — too short or too long loses points
_DEFAULT_LENGTH_PENALTY = 0.02  # points lost per 100 chars over 2× ideal


def default_scorer(output: Any, rubric: QualityRubric) -> float:
    """Baseline heuristic scorer that operates on string representations.

    This scorer is intentionally domain-agnostic and conservative.  It is
    designed for tests and bootstrapping, not production evaluation.  Replace
    it with an LLM-based scorer for real workloads.

    Scoring logic:
        - Non-string/non-bytes output is converted via ``repr()``.
        - Empty output always returns 0.0.
        - Base score starts at 5.0 (neutral).
        - ``accuracy``: penalises hedging language ("might", "possibly").
        - ``completeness``: rewards longer, more detailed responses.
        - ``clarity``: rewards shorter sentences; penalises excessive jargon.
        - ``conciseness``: penalises repetition of the same words.
        - ``tone``: presence of greeting/closing conventions boosts score.
        - ``structure``: rewards use of paragraphs or list markers.
        - ``grammar``: approximated by sentence-to-word ratio heuristic.
        - ``engagement``: rewards a punchy opening (first sentence length).
        - ``correctness``: rewards presence of ``def``/``class`` structure.
        - ``readability``: rewards docstrings and meaningful identifier length.
        - ``security``: penalises hardcoded secret-like strings.
        - ``test_coverage``: rewards presence of ``assert`` or ``test_`` names.
        - All other rubric names receive a flat 6.5 (above most thresholds).

    Args:
        output: The artefact to score.  Coerced to ``str`` if not already.
        rubric: The dimension being evaluated.

    Returns:
        A float in [0.0, 10.0].
    """
    if isinstance(output, (bytes, bytearray)):
        text = output.decode("utf-8", errors="replace")
    elif not isinstance(output, str):
        text = repr(output)
    else:
        text = output

    if not text.strip():
        return 0.0

    words = text.split()
    word_count = len(words)
    char_count = len(text)
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    sentence_count = max(1, len(sentences))

    name = rubric.name.lower()

    if name == "accuracy":
        # Penalise hedging terms that signal unverified claims
        hedges = {"might", "possibly", "perhaps", "could be", "i think", "maybe", "probably"}
        hedge_count = sum(1 for h in hedges if h in text.lower())
        score = max(0.0, 8.0 - hedge_count * 1.5)

    elif name == "completeness":
        # Reward more detailed responses up to a ceiling
        if word_count < 20:
            score = max(0.0, word_count * 0.25)
        elif word_count < 100:
            score = 5.0 + (word_count - 20) * 0.05
        else:
            score = min(10.0, 9.0 + (word_count - 100) * 0.002)

    elif name == "clarity":
        avg_sentence_len = word_count / sentence_count
        # Ideal sentence length: 10-20 words
        if avg_sentence_len <= 20:
            score = min(10.0, 10.0 - max(0.0, avg_sentence_len - 10) * 0.3)
        else:
            score = max(0.0, 10.0 - (avg_sentence_len - 10) * 0.4)

    elif name == "conciseness":
        # Penalise high repetition ratio
        unique_words = len({w.lower() for w in words})
        repetition_ratio = 1.0 - (unique_words / max(1, word_count))
        score = max(0.0, 10.0 - repetition_ratio * 12.0)

    elif name == "tone":
        # Reward conventional greeting/closing markers
        lower = text.lower()
        markers = {"hi ", "hello", "dear", "regards", "sincerely", "thanks", "thank you"}
        found = sum(1 for m in markers if m in lower)
        score = min(10.0, 6.0 + found * 0.8)

    elif name == "structure":
        # Reward paragraphs and list markers
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        list_markers = sum(1 for line in text.splitlines() if line.strip().startswith(("-", "*", "•", "1.")))
        score = min(10.0, 5.0 + len(paragraphs) * 0.5 + list_markers * 0.3)

    elif name == "grammar":
        # Approximate: consistent sentence-to-word density signals well-formed prose
        avg_sentence_len = word_count / sentence_count
        if 8 <= avg_sentence_len <= 25:
            score = 8.5
        elif avg_sentence_len < 5:
            score = 5.0
        else:
            score = max(4.0, 8.5 - abs(avg_sentence_len - 17) * 0.15)

    elif name == "engagement":
        # Short opening sentence scores better
        first_sentence = sentences[0] if sentences else ""
        first_words = len(first_sentence.split())
        if first_words <= 12:
            score = min(10.0, 10.0 - max(0.0, first_words - 6) * 0.3)
        else:
            score = max(3.0, 10.0 - first_words * 0.25)

    elif name == "correctness":
        lower = text.lower()
        has_def = "def " in lower or "class " in lower or "function" in lower
        has_return = "return " in lower or "yield " in lower
        score = 5.0 + (2.5 if has_def else 0.0) + (2.5 if has_return else 0.0)

    elif name == "readability":
        # Reward docstrings and moderate identifier lengths
        has_docstring = '"""' in text or "'''" in text
        avg_word_len = char_count / max(1, word_count)
        score = (7.0 if has_docstring else 5.0) + min(2.0, avg_word_len * 0.3)

    elif name == "security":
        lower = text.lower()
        # Penalise patterns that resemble hardcoded secrets
        danger_patterns = ["password=", "secret=", "api_key=", "token=", "sk-", "-----begin"]
        violations = sum(1 for p in danger_patterns if p in lower)
        score = max(0.0, 10.0 - violations * 3.0)

    elif name == "test_coverage":
        lower = text.lower()
        has_assert = "assert " in lower
        has_test_fn = "def test_" in lower or "test_" in lower
        score = 5.0 + (2.5 if has_assert else 0.0) + (2.5 if has_test_fn else 0.0)

    else:
        # Unknown dimension: return a safe neutral score above most thresholds
        score = 6.5

    return round(min(10.0, max(0.0, score)), 2)


# ---------------------------------------------------------------------------
# QualityGate
# ---------------------------------------------------------------------------


class QualityGate:
    """Configurable quality gate with fix-cycle support.

    Args:
        rubrics: Ordered list of scoring dimensions.
        threshold: Overall weighted-average score required to pass the gate.
        max_cycles: Maximum number of evaluate-fix iterations allowed in
            ``run_with_fix`` before the last verdict is returned as final.

    Raises:
        ValueError: If ``rubrics`` is empty or ``threshold`` out of [0, 10].
    """

    def __init__(
        self,
        rubrics: list[QualityRubric],
        threshold: float = 8.0,
        max_cycles: int = 3,
    ) -> None:
        if not rubrics:
            raise ValueError("QualityGate requires at least one rubric.")
        if not (0.0 <= threshold <= 10.0):
            raise ValueError(f"threshold must be in [0, 10], got {threshold}")
        if max_cycles < 1:
            raise ValueError(f"max_cycles must be >= 1, got {max_cycles}")

        self.rubrics = rubrics
        self.threshold = threshold
        self.max_cycles = max_cycles

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        output: Any,
        scorer: Callable[[Any, QualityRubric], float],
        cycle: int = 1,
    ) -> GateVerdict:
        """Run a single evaluation pass and return a verdict.

        Args:
            output: The artefact to evaluate.
            scorer: A callable ``(output, rubric) -> float`` (0-10).
                Called once per rubric in ``self.rubrics``.
            cycle: Which fix cycle this evaluation belongs to (1-based).
                Used for bookkeeping in ``GateVerdict.cycle``.

        Returns:
            A ``GateVerdict`` with ``passed=True`` iff overall score meets
            ``self.threshold`` and no dimension is below its own threshold.
        """
        dimension_scores: dict[str, float] = {}
        total_weight = sum(r.weight for r in self.rubrics)

        for rubric in self.rubrics:
            raw = scorer(output, rubric)
            dimension_scores[rubric.name] = round(min(10.0, max(0.0, float(raw))), 2)

        overall = sum(
            dimension_scores[r.name] * r.weight for r in self.rubrics
        ) / total_weight
        overall = round(overall, 2)

        failures = [
            r.name
            for r in self.rubrics
            if dimension_scores[r.name] < r.threshold
        ]

        passed = overall >= self.threshold and len(failures) == 0

        return GateVerdict(
            passed=passed,
            overall_score=overall,
            dimension_scores=dimension_scores,
            failures=failures,
            cycle=cycle,
        )

    def run_with_fix(
        self,
        output: Any,
        scorer: Callable[[Any, QualityRubric], float],
        fixer: Callable[[Any, list[str]], Any],
    ) -> QualityResult:
        """Evaluate with automatic fix cycling until the gate passes or cycles exhaust.

        Algorithm:
            1. Evaluate ``output`` with ``scorer``.
            2. If verdict passes or we have hit ``max_cycles``, stop.
            3. Otherwise call ``fixer(output, failures)`` to get a fixed
               version of the output, increment the cycle counter, and
               repeat from step 1.

        Args:
            output: Initial artefact to evaluate.
            scorer: Callable ``(output, rubric) -> float`` (0-10).
            fixer: Callable ``(output, failures) -> fixed_output``.
                ``failures`` is a list of rubric names below threshold.
                The fixer should return a new candidate artefact; the
                original is not mutated.

        Returns:
            A ``QualityResult`` describing the final outcome.
        """
        current = output

        for cycle in range(1, self.max_cycles + 1):
            verdict = self.evaluate(current, scorer, cycle=cycle)

            if verdict.passed or cycle == self.max_cycles:
                return QualityResult(
                    final_verdict=verdict,
                    cycles_used=cycle,
                    max_cycles=self.max_cycles,
                    converged=verdict.passed,
                )

            # Attempt a fix before the next cycle
            current = fixer(current, verdict.failures)

        # Unreachable: loop always returns inside, but satisfies type checkers.
        raise RuntimeError("run_with_fix loop exited without returning")  # pragma: no cover


# ═══════════════════════════════════════════════════════════════════════
# Success Conditions (from success_conditions.py — SPEC Section 5)
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class SuccessCondition:
    """A single success condition evaluation."""
    name: str
    met: bool = False
    value: float = 0.0
    threshold: float = 0.0
    detail: str = ""


@dataclass
class SuccessConditionsReport:
    """Result of evaluating all 6 success conditions."""
    all_met: bool = False
    conditions: list[SuccessCondition] = field(default_factory=list)
    window_size: int = 20
    sessions_evaluated: int = 0


def evaluate_success_conditions(db_path=None, window: int = 20, ctx=None) -> SuccessConditionsReport:
    """Evaluate the 6 SPEC success conditions over a session window."""
    report = SuccessConditionsReport(window_size=window)
    conditions = [
        SuccessCondition(name="correction_rate_decreasing", detail="Requires 20+ sessions of data"),
        SuccessCondition(name="edit_distance_decreasing", detail="Requires 20+ sessions of data"),
        SuccessCondition(name="fda_increasing", detail="Requires 20+ sessions of data"),
        SuccessCondition(name="rule_success_increasing", detail="Requires 20+ sessions of data"),
        SuccessCondition(name="misfire_rate_low", detail="Requires 20+ sessions of data"),
        SuccessCondition(name="not_bland", detail="Requires blandness < 0.70"),
    ]
    try:
        import sqlite3
        from pathlib import Path as _Path
        db = _Path(db_path) if db_path else (_Path(ctx.brain_dir) / "system.db" if ctx else None)
        if db and db.exists():
            conn = sqlite3.connect(str(db))
            max_session = conn.execute("SELECT MAX(session) FROM events WHERE typeof(session)='integer'").fetchone()[0] or 0
            report.sessions_evaluated = max_session
            conn.close()
    except Exception:
        pass
    report.conditions = conditions
    report.all_met = all(c.met for c in conditions)
    return report
