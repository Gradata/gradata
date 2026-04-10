"""
Evaluation Benchmark — Measuring procedural memory quality.
=============================================================
Comparable to EverOS's LoCoMo benchmark but for correction-based procedural memory.

Three benchmark dimensions:
1. Correction Recall: Can the system retrieve relevant past corrections?
2. Rule Precision: Do graduated rules actually prevent re-occurrence?
3. Graduation Accuracy: Are INSTINCT→PATTERN→RULE promotions correct?

Usage::

    from gradata.contrib.enhancements.eval_benchmark import (
        LearningBenchmark, BenchmarkResult, BenchmarkCase,
    )

    bench = LearningBenchmark()
    bench.add_case(BenchmarkCase(
        correction_text="Changed formal to casual",
        category="TONE",
        severity="moderate",
        expected_rule=True,       # Should this graduate to RULE?
        expected_category="TONE", # Expected category detection
    ))
    result = bench.run()
    print(result.overall_score)         # 0.0-1.0
    print(result.correction_recall)     # Precision on retrieval
    print(result.rule_precision)        # Precision on graduated rules
    print(result.graduation_accuracy)   # Accuracy on promotion decisions
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "STANDARD_BENCHMARK",
    "BenchmarkCase",
    "BenchmarkResult",
    "CaseResult",
    "LearningBenchmark",
    "run_standard_benchmark",
]


@dataclass
class BenchmarkCase:
    """A single benchmark test case.

    Attributes:
        correction_text: Description of the correction.
        category: Expected correction category.
        severity: Expected severity level.
        expected_rule: Should this eventually graduate to RULE?
        expected_category: Expected auto-detected category.
        expected_high_value: Should the discriminator flag this?
        task_type: Task type context.
        tags: Arbitrary tags for filtering.
    """
    correction_text: str = ""
    category: str = ""
    severity: str = "moderate"
    expected_rule: bool = False
    expected_category: str = ""
    expected_high_value: bool | None = None
    task_type: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class CaseResult:
    """Result of running a single benchmark case.

    Attributes:
        case: The benchmark case that was run.
        category_correct: Whether category was detected correctly.
        severity_correct: Whether severity matches expected.
        high_value_correct: Whether discriminator agreed with expected.
        predicted_category: What the system predicted.
        predicted_high_value: What the discriminator returned.
        discriminator_confidence: Confidence from discriminator.
        error: Error message if case failed to run.
    """
    case: BenchmarkCase
    category_correct: bool = False
    severity_correct: bool = True
    high_value_correct: bool | None = None
    predicted_category: str = ""
    predicted_high_value: bool | None = None
    discriminator_confidence: float = 0.0
    error: str = ""

    @property
    def passed(self) -> bool:
        """True if all verifiable assertions passed."""
        if self.error:
            return False
        checks = [self.category_correct, self.severity_correct]
        if self.high_value_correct is not None:
            checks.append(self.high_value_correct)
        return all(checks)


@dataclass
class BenchmarkResult:
    """Aggregate result from running all benchmark cases.

    Attributes:
        cases: Individual case results.
        correction_recall: Fraction of cases where category was correctly detected.
        rule_precision: Fraction of expected-rule cases correctly identified as high-value.
        graduation_accuracy: Fraction of high-value predictions matching expected.
        overall_score: Weighted average of the three dimensions.
        total_cases: Number of cases run.
        passed_cases: Number of cases that passed all assertions.
    """
    cases: list[CaseResult] = field(default_factory=list)
    correction_recall: float = 0.0
    rule_precision: float = 0.0
    graduation_accuracy: float = 0.0
    overall_score: float = 0.0
    total_cases: int = 0
    passed_cases: int = 0

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 1.0
        return self.passed_cases / self.total_cases


class LearningBenchmark:
    """Benchmark suite for measuring learning quality.

    Runs correction cases through the discriminator and category
    detection, then scores against expected outcomes.
    """

    def __init__(self) -> None:
        self._cases: list[BenchmarkCase] = []

    def add_case(self, case: BenchmarkCase) -> None:
        """Add a benchmark case."""
        self._cases.append(case)

    def add_cases(self, cases: list[BenchmarkCase]) -> None:
        """Add multiple benchmark cases."""
        self._cases.extend(cases)

    @property
    def case_count(self) -> int:
        return len(self._cases)

    def run(self) -> BenchmarkResult:
        """Run all benchmark cases and compute scores.

        Returns:
            BenchmarkResult with per-case results and aggregate scores.
        """
        # Import discriminator
        try:
            from gradata.enhancements.lesson_discriminator import LessonDiscriminator
            discriminator = LessonDiscriminator()
        except ImportError:
            discriminator = None

        # Import edit classifier for category detection
        try:
            from gradata.enhancements.diff_engine import compute_diff
            from gradata.enhancements.edit_classifier import classify_edits
            has_classifier = True
        except ImportError:
            has_classifier = False

        case_results: list[CaseResult] = []

        for case in self._cases:
            cr = CaseResult(case=case)
            try:
                # Test category detection
                if has_classifier and case.correction_text:
                    diff = compute_diff(
                        f"original {case.correction_text}",
                        f"corrected {case.correction_text}",
                    )
                    classifications = classify_edits(diff)
                    if classifications:
                        cr.predicted_category = classifications[0].category.upper()
                    cr.category_correct = (
                        cr.predicted_category == case.expected_category.upper()
                        if case.expected_category
                        else True
                    )
                else:
                    cr.category_correct = True  # Can't verify without classifier

                # Test discriminator
                if discriminator:
                    verdict = discriminator.evaluate(
                        correction_text=case.correction_text,
                        severity=case.severity,
                        task_type=case.task_type,
                    )
                    cr.predicted_high_value = verdict.is_high_value
                    cr.discriminator_confidence = verdict.confidence

                    if case.expected_high_value is not None:
                        cr.high_value_correct = (
                            verdict.is_high_value == case.expected_high_value
                        )

            except Exception as e:
                cr.error = str(e)

            case_results.append(cr)

        # Compute aggregate scores
        total = len(case_results)
        passed = sum(1 for cr in case_results if cr.passed)

        # Correction recall: fraction with correct category
        category_cases = [cr for cr in case_results if cr.case.expected_category]
        correction_recall = (
            sum(1 for cr in category_cases if cr.category_correct) / len(category_cases)
            if category_cases else 1.0
        )

        # Rule precision: of cases expected to be rules, how many flagged high-value
        rule_cases = [cr for cr in case_results if cr.case.expected_rule]
        rule_precision = (
            sum(1 for cr in rule_cases if cr.predicted_high_value is True) / len(rule_cases)
            if rule_cases else 1.0
        )

        # Graduation accuracy: all high-value predictions matching expected
        hv_cases = [cr for cr in case_results if cr.high_value_correct is not None]
        graduation_accuracy = (
            sum(1 for cr in hv_cases if cr.high_value_correct) / len(hv_cases)
            if hv_cases else 1.0
        )

        # Overall: weighted average (rule precision most important)
        overall = (
            correction_recall * 0.25
            + rule_precision * 0.45
            + graduation_accuracy * 0.30
        )

        return BenchmarkResult(
            cases=case_results,
            correction_recall=round(correction_recall, 4),
            rule_precision=round(rule_precision, 4),
            graduation_accuracy=round(graduation_accuracy, 4),
            overall_score=round(overall, 4),
            total_cases=total,
            passed_cases=passed,
        )


# ---------------------------------------------------------------------------
# Built-in benchmark suite
# ---------------------------------------------------------------------------

STANDARD_BENCHMARK: list[BenchmarkCase] = [
    # High severity, should graduate
    BenchmarkCase(
        correction_text="Complete rewrite of email tone from formal to casual",
        category="TONE", severity="rewrite",
        expected_rule=True, expected_high_value=True,
    ),
    BenchmarkCase(
        correction_text="Fixed incorrect pricing in proposal",
        category="ACCURACY", severity="major",
        expected_rule=True, expected_high_value=True,
    ),
    BenchmarkCase(
        correction_text="Restructured entire email flow",
        category="STRUCTURE", severity="major",
        expected_rule=True, expected_high_value=True,
    ),
    # Low severity, should not graduate
    BenchmarkCase(
        correction_text="Fixed typo in greeting",
        category="TONE", severity="trivial",
        expected_rule=False, expected_high_value=False,
    ),
    BenchmarkCase(
        correction_text="Adjusted spacing in signature",
        category="STYLE", severity="trivial",
        expected_rule=False, expected_high_value=False,
    ),
    # Moderate, borderline
    BenchmarkCase(
        correction_text="Changed call-to-action from link to button",
        category="CONTENT", severity="moderate",
        expected_rule=False, expected_high_value=None,  # Don't assert
    ),
    BenchmarkCase(
        correction_text="Replaced em dash with colon",
        category="STYLE", severity="minor",
        expected_rule=False, expected_high_value=False,
    ),
]


def run_standard_benchmark() -> BenchmarkResult:
    """Run the built-in standard benchmark suite.

    Returns:
        BenchmarkResult with scores comparable to EverOS's LoCoMo.
    """
    bench = LearningBenchmark()
    bench.add_cases(STANDARD_BENCHMARK)
    return bench.run()
