"""Truth Protocol — evidence-based output validation (stdlib-only, no I/O).
``verify_*`` all return ``TruthVerdict``. Case-insensitive regex banned-phrase
detection; ``numbers_without_source`` flags bare percentages lacking a
citation; ``verify_mutations`` requires ``|`` or ``->``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TruthCheck:
    """Result of a single truth-validation rule.

    Args:
        name: Short identifier for the check, e.g. ``"no_banned_phrases"``.
        passed: True when the check found no violations.
        detail: Human-readable explanation of the result.
        evidence: The specific text or action that triggered the violation,
            or ``None`` if the check passed.
    """

    name: str
    passed: bool
    detail: str
    evidence: str | None = None


@dataclass
class TruthVerdict:
    """Aggregate result from a ``verify_*`` call.

    Args:
        checks: All individual ``TruthCheck`` results.
        all_passed: True iff every check passed.
        violations: List of ``check.name`` values for failed checks.
    """

    checks: list[TruthCheck] = field(default_factory=list)
    all_passed: bool = True
    violations: list[str] = field(default_factory=list)

    def add(self, check: TruthCheck) -> None:
        """Register a check and update aggregate state."""
        self.checks.append(check)
        if not check.passed:
            self.all_passed = False
            self.violations.append(check.name)


# ---------------------------------------------------------------------------
# Banned phrases
# ---------------------------------------------------------------------------

#: Phrases that signal unverified success claims.  Any output containing
#: one of these (case-insensitive) should be flagged for human review.
BANNED_PHRASES: list[str] = [
    # Unqualified completion claims
    "successfully completed",
    "completed successfully",
    "everything is working",
    "everything works",
    "everything is working perfectly",
    "all tests pass",
    "all tests passed",
    "tests are passing",
    # Happy-path openers that mask uncertainty
    "i'm happy to report",
    "i am happy to report",
    "pleased to report",
    "i'm pleased to announce",
    "i am pleased to announce",
    "great news",
    "good news",
    # Absolute-success language without evidence
    "no issues found",
    "no errors found",
    "no problems found",
    "no issues detected",
    "no errors detected",
    "no problems detected",
    "zero errors",
    "zero issues",
    "zero problems",
    "works perfectly",
    "working perfectly",
    "runs perfectly",
    "running perfectly",
    # Confident delivery without proof
    "as expected",
    "exactly as expected",
    "exactly as specified",
    "mission accomplished",
    "task completed",
    "done and dusted",
]

# Pre-compiled patterns for performance
_BANNED_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (phrase, re.compile(re.escape(phrase), re.IGNORECASE)) for phrase in BANNED_PHRASES
]

# Numbers without source: percentage or multiplier not preceded by a citation.
# Matches "300%", "3x", "2.5x" etc.
_NUMBER_CLAIM_RE = re.compile(
    r"(?<!\()"  # not inside a parenthetical
    r"(?<!source:)"  # not after "source:"
    r"(?<!ref:)"  # not after "ref:"
    r"\b(\d+(?:\.\d+)?)\s*"  # number
    r"(%|x\b)",  # percent or multiplier
    re.IGNORECASE,
)

# Citation evidence markers: (source), [1], (ref: ...), etc.
_CITATION_RE = re.compile(
    r"(\([^)]{3,}\)|\[[^\]]{1,}\]|source:\s*\S+|ref:\s*\S+)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# verify_claims
# ---------------------------------------------------------------------------


def verify_claims(output: str) -> TruthVerdict:
    """Scan ``output`` for unverifiable claims and banned success phrases.

    Checks performed:
        1. ``no_banned_phrases`` — detects any phrase from ``BANNED_PHRASES``.
        2. ``no_unverified_numbers`` — detects bare percentages/multipliers
           without an accompanying citation marker nearby.

    Args:
        output: The text string to validate.

    Returns:
        A ``TruthVerdict`` with one ``TruthCheck`` per rule.  ``all_passed``
        is True only when both checks pass.
    """
    verdict = TruthVerdict()

    # --- Check 1: banned phrases ---
    found_phrases: list[str] = []
    for phrase, pattern in _BANNED_PATTERNS:
        if pattern.search(output):
            found_phrases.append(phrase)

    if found_phrases:
        verdict.add(
            TruthCheck(
                name="no_banned_phrases",
                passed=False,
                detail=(
                    f"Output contains {len(found_phrases)} banned phrase(s) "
                    "that signal unverified success claims."
                ),
                evidence="; ".join(found_phrases[:5]),  # cap evidence to 5
            )
        )
    else:
        verdict.add(
            TruthCheck(
                name="no_banned_phrases",
                passed=True,
                detail="No banned success phrases detected.",
            )
        )

    # --- Check 2: numbers without source ---
    number_matches = list(_NUMBER_CLAIM_RE.finditer(output))
    unverified: list[str] = []
    for m in number_matches:
        start = max(0, m.start() - 80)
        end = min(len(output), m.end() + 80)
        context = output[start:end]
        if not _CITATION_RE.search(context):
            unverified.append(m.group(0).strip())

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_unverified = [
        v
        for v in unverified
        if not (v in seen or seen.add(v))  # type: ignore[func-returns-value]
    ]

    if unique_unverified:
        verdict.add(
            TruthCheck(
                name="no_unverified_numbers",
                passed=False,
                detail=(
                    f"Found {len(unique_unverified)} numeric claim(s) without "
                    "an accompanying citation or source reference."
                ),
                evidence=", ".join(unique_unverified[:5]),
            )
        )
    else:
        verdict.add(
            TruthCheck(
                name="no_unverified_numbers",
                passed=True,
                detail="All numeric claims have accompanying citations or none found.",
            )
        )

    return verdict
