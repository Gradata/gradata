"""Rule-to-Hook graduation — deterministic rules auto-generate enforcement."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class EnforcementType(StrEnum):
    """How a rule is enforced."""

    PROMPT_INJECTION = "prompt_injection"  # Default: injected into LLM context
    HOOK = "hook"  # Claude Code hook (shell script)
    MIDDLEWARE = "middleware"  # API wrapper (Python function)
    GUARDRAIL = "guardrail"  # LangChain/CrewAI guard


class DeterminismCheck(StrEnum):
    """Why a rule is or isn't deterministic."""

    REGEX_PATTERN = "regex_pattern"  # Can be checked with regex (e.g., no em dashes)
    FILE_CHECK = "file_check"  # Can verify file properties (size, existence)
    COMMAND_BLOCK = "command_block"  # Can block specific commands
    TEST_TRIGGER = "test_trigger"  # Can trigger test runs
    NOT_DETERMINISTIC = "not_deterministic"  # Requires LLM judgment


@dataclass
class HookCandidate:
    """A rule that could be promoted to a hook."""

    rule_description: str
    rule_confidence: float
    determinism: DeterminismCheck
    enforcement: EnforcementType
    hook_template: str  # Template name or inline script
    reason: str  # Why this rule is/isn't promotable


# Patterns that indicate a rule is deterministic.
# Each entry: (regex matching rule description, check type, hook template name)
DETERMINISTIC_PATTERNS: list[tuple[str, DeterminismCheck, str]] = [
    (r"never use em.?dash", DeterminismCheck.REGEX_PATTERN, "regex_replace"),
    (r"no em.?dash", DeterminismCheck.REGEX_PATTERN, "regex_replace"),
    (r"don.t use em.?dash", DeterminismCheck.REGEX_PATTERN, "regex_replace"),
    (r"keep files? under \d+ lines?", DeterminismCheck.FILE_CHECK, "file_size_check"),
    (r"files? under \d+ lines?", DeterminismCheck.FILE_CHECK, "file_size_check"),
    (r"never (commit|push) secret", DeterminismCheck.COMMAND_BLOCK, "secret_scan"),
    (r"no (hardcod|hardcode).+secret", DeterminismCheck.COMMAND_BLOCK, "secret_scan"),
    (r"run tests? after", DeterminismCheck.TEST_TRIGGER, "auto_test"),
    (r"always run tests?", DeterminismCheck.TEST_TRIGGER, "auto_test"),
    (r"read.+before edit", DeterminismCheck.FILE_CHECK, "read_before_edit"),
    (r"always read.+before", DeterminismCheck.FILE_CHECK, "read_before_edit"),
    (r"never (rm|delete|remove).+rf", DeterminismCheck.COMMAND_BLOCK, "destructive_block"),
    (r"never force.?push", DeterminismCheck.COMMAND_BLOCK, "destructive_block"),
    (r"never.*format.*f.?string.*python.?-c", DeterminismCheck.COMMAND_BLOCK, "fstring_block"),
]


def classify_rule(description: str, confidence: float) -> HookCandidate:
    """Classify whether a graduated rule can become a hook.

    Returns a HookCandidate indicating if/how the rule can be enforced
    deterministically, or NOT_DETERMINISTIC if it requires LLM judgment.
    """
    desc_lower = description.lower()

    for pattern, check_type, template in DETERMINISTIC_PATTERNS:
        if re.search(pattern, desc_lower):
            return HookCandidate(
                rule_description=description,
                rule_confidence=confidence,
                determinism=check_type,
                enforcement=EnforcementType.HOOK,
                hook_template=template,
                reason=f"Matches deterministic pattern: {pattern}",
            )

    return HookCandidate(
        rule_description=description,
        rule_confidence=confidence,
        determinism=DeterminismCheck.NOT_DETERMINISTIC,
        enforcement=EnforcementType.PROMPT_INJECTION,
        hook_template="",
        reason="Requires LLM judgment — stays as prompt injection",
    )


def find_hook_candidates(
    lessons: list[dict],
    min_confidence: float = 0.90,
) -> list[HookCandidate]:
    """Scan graduated rules and return those promotable to hooks.

    Only considers RULE and META-RULE state lessons above min_confidence.
    """
    candidates: list[HookCandidate] = []
    for lesson in lessons:
        status = lesson.get("status", "").upper()
        if status not in ("RULE", "META-RULE", "META_RULE"):
            continue
        conf = lesson.get("confidence", 0.0)
        if conf < min_confidence:
            continue
        candidate = classify_rule(lesson.get("description", ""), conf)
        if candidate.determinism != DeterminismCheck.NOT_DETERMINISTIC:
            candidates.append(candidate)
    return candidates
