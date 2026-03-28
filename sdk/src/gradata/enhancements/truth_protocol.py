"""Truth Protocol — Evidence-based output validation.
=====================================================
SDK LAYER: Pure logic, stdlib only (re, dataclasses).
No domain-specific content. No I/O.

Design decisions
----------------
* All three ``verify_*`` functions return a ``TruthVerdict`` for a uniform
  caller interface; mix-and-match or run all three and merge as needed.
* Banned-phrase detection uses case-insensitive regex so it catches
  variations in casing and whitespace without forcing callers to normalise.
* The ``numbers_without_source`` check looks for bare percentages and
  multipliers (e.g. "300%" or "3x") not preceded by a citation marker
  (parentheses or "source:").  It errs on the side of false-positives
  because a missed violation is worse than an extra warning.
* ``verify_mutations`` is intentionally simple: it checks that every
  action string in the list ends with a log-evidence marker ("|" or "->")
  so callers can wire it to their event/audit system as needed.
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
    (phrase, re.compile(re.escape(phrase), re.IGNORECASE))
    for phrase in BANNED_PHRASES
]

# Numbers without source: percentage or multiplier not preceded by a citation.
# Matches "300%", "3x", "2.5x" etc.
_NUMBER_CLAIM_RE = re.compile(
    r"(?<!\()"               # not inside a parenthetical
    r"(?<!source:)"          # not after "source:"
    r"(?<!ref:)"             # not after "ref:"
    r"\b(\d+(?:\.\d+)?)\s*"  # number
    r"(%|x\b)",              # percent or multiplier
    re.IGNORECASE,
)

# Citation evidence markers: (source), [1], (ref: ...), etc.
_CITATION_RE = re.compile(
    r"(\([^)]{3,}\)|\[[^\]]{1,}\]|source:\s*\S+|ref:\s*\S+)",
    re.IGNORECASE,
)

# Log-evidence trailer expected on mutation action strings.
# A mutation is "logged" if it contains "|", "->", "logged", "emitted", or "saved".
_MUTATION_LOG_RE = re.compile(
    r"(\|->?|->|\blogged\b|\bemitted\b|\bsaved\b|\brecorded\b|\bwritten\b)",
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
        verdict.add(TruthCheck(
            name="no_banned_phrases",
            passed=False,
            detail=(
                f"Output contains {len(found_phrases)} banned phrase(s) "
                "that signal unverified success claims."
            ),
            evidence="; ".join(found_phrases[:5]),  # cap evidence to 5
        ))
    else:
        verdict.add(TruthCheck(
            name="no_banned_phrases",
            passed=True,
            detail="No banned success phrases detected.",
        ))

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
        v for v in unverified if not (v in seen or seen.add(v))  # type: ignore[func-returns-value]
    ]

    if unique_unverified:
        verdict.add(TruthCheck(
            name="no_unverified_numbers",
            passed=False,
            detail=(
                f"Found {len(unique_unverified)} numeric claim(s) without "
                "an accompanying citation or source reference."
            ),
            evidence=", ".join(unique_unverified[:5]),
        ))
    else:
        verdict.add(TruthCheck(
            name="no_unverified_numbers",
            passed=True,
            detail="All numeric claims have accompanying citations or none found.",
        ))

    return verdict


# ---------------------------------------------------------------------------
# verify_citations
# ---------------------------------------------------------------------------


def verify_citations(output: str, sources: list[str]) -> TruthVerdict:
    """Verify that claims in ``output`` are backed by entries in ``sources``.

    For each source string provided, the function checks whether a reference
    to that source (case-insensitive substring match) appears in ``output``.
    It also checks that ``output`` contains at least one citation marker
    when sources are provided.

    Checks performed:
        1. ``sources_cited`` — every supplied source is referenced in output.
        2. ``citation_markers_present`` — at least one citation-style marker
           (parenthetical, bracket reference, or "source:") exists in output
           when sources are non-empty.

    Args:
        output: The text string being validated.
        sources: Authoritative source strings that should be cited.  Pass
            an empty list to skip source-coverage checking.

    Returns:
        A ``TruthVerdict`` summarising citation health.
    """
    verdict = TruthVerdict()

    # --- Check 1: each source referenced ---
    if sources:
        uncited: list[str] = [
            src for src in sources
            if src.lower() not in output.lower()
        ]
        if uncited:
            verdict.add(TruthCheck(
                name="sources_cited",
                passed=False,
                detail=(
                    f"{len(uncited)} of {len(sources)} source(s) not "
                    "referenced in output."
                ),
                evidence="; ".join(uncited[:5]),
            ))
        else:
            verdict.add(TruthCheck(
                name="sources_cited",
                passed=True,
                detail=f"All {len(sources)} source(s) referenced in output.",
            ))
    else:
        verdict.add(TruthCheck(
            name="sources_cited",
            passed=True,
            detail="No sources provided; check skipped.",
        ))

    # --- Check 2: citation markers present when sources are expected ---
    if sources:
        has_markers = bool(_CITATION_RE.search(output))
        if has_markers:
            verdict.add(TruthCheck(
                name="citation_markers_present",
                passed=True,
                detail="Citation markers found in output.",
            ))
        else:
            verdict.add(TruthCheck(
                name="citation_markers_present",
                passed=False,
                detail=(
                    "Sources were provided but output contains no citation "
                    "markers (parentheticals, brackets, or 'source:' prefixes)."
                ),
                evidence=output[:120] if output else None,
            ))
    else:
        verdict.add(TruthCheck(
            name="citation_markers_present",
            passed=True,
            detail="No sources provided; citation marker check skipped.",
        ))

    return verdict


# ---------------------------------------------------------------------------
# verify_mutations
# ---------------------------------------------------------------------------


def verify_mutations(actions: list[str]) -> TruthVerdict:
    """Check that every state-changing action string carries a log marker.

    State-changing actions should be verifiable.  This function enforces the
    convention that action strings include a log-evidence trailer such as
    ``"| logged"`` or ``"-> events.jsonl"`` so that callers can confirm the
    action was actually recorded.

    Checks performed:
        1. ``actions_have_log_markers`` — every string in ``actions`` matches
           the log-evidence pattern (contains ``|``, ``->``, or a keyword
           such as ``logged``, ``emitted``, ``saved``, ``recorded``,
           ``written``).

    Args:
        actions: List of action description strings from the caller's
            execution trace.

    Returns:
        A ``TruthVerdict`` with one check summarising all unlogged actions.
    """
    verdict = TruthVerdict()

    if not actions:
        verdict.add(TruthCheck(
            name="actions_have_log_markers",
            passed=True,
            detail="No actions provided; check skipped.",
        ))
        return verdict

    unlogged: list[str] = [
        action for action in actions
        if not _MUTATION_LOG_RE.search(action)
    ]

    if unlogged:
        verdict.add(TruthCheck(
            name="actions_have_log_markers",
            passed=False,
            detail=(
                f"{len(unlogged)} of {len(actions)} action(s) lack a "
                "log-evidence marker (|, ->, logged, emitted, saved, "
                "recorded, or written)."
            ),
            evidence="; ".join(unlogged[:5]),
        ))
    else:
        verdict.add(TruthCheck(
            name="actions_have_log_markers",
            passed=True,
            detail=f"All {len(actions)} action(s) carry log-evidence markers.",
        ))

    return verdict
