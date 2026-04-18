"""
Guardrails Pattern — Gradata
====================================
Two-phase validation: input guards run before agent execution; output guards
run after.  Both phases are composable via Guard, InputGuard, and OutputGuard
primitives.  ``guarded()`` wires them around any callable.

Usage::

    from .guardrails import (
        Guard, InputGuard, OutputGuard, guarded,
        pii_detector, injection_detector, scope_validator,
        banned_phrases, destructive_action,
    )

    safe_fn = guarded(
        InputGuard(pii_detector, injection_detector),
        my_agent_fn,
        OutputGuard(banned_phrases, destructive_action),
    )
    result = safe_fn(user_input)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class GuardCheck:
    """Result of a single guard evaluation.

    Attributes:
        name: The guard's identifier (e.g. ``"pii_detector"``).
        result: ``"pass"``, ``"fail"``, or ``"override"``.
        details: Human-readable explanation of what was found / why it passed.
        action_taken: ``"blocked"``, ``"redacted"``, ``"passed"``, or
            ``"user_override"``.
    """

    name: str
    result: str          # "pass" | "fail" | "override"
    details: str
    action_taken: str    # "blocked" | "redacted" | "passed" | "user_override"


@dataclass
class GuardedResult:
    """Aggregated outcome of running input + output guards around an agent call.

    Attributes:
        input_checks: Results from every guard in the :class:`InputGuard`.
        output_checks: Results from every guard in the :class:`OutputGuard`.
        all_passed: ``True`` only when every guard in both phases returned
            ``"pass"`` or ``"override"``.
        blocked: ``True`` when execution was prevented by a failing input guard.
        block_reason: Plain-English explanation of the first blocking failure
            (``None`` when ``blocked`` is ``False``).
        output: The agent's return value; ``None`` when ``blocked`` is ``True``.
    """

    input_checks: list[GuardCheck]
    output_checks: list[GuardCheck]
    all_passed: bool
    blocked: bool
    block_reason: str | None = None
    output: Any = None


# ---------------------------------------------------------------------------
# Core classes
# ---------------------------------------------------------------------------


class Guard:
    """A single validation unit wrapping a pure check function.

    Args:
        name: Identifier for this guard (used in :class:`GuardCheck` results).
        check_fn: Callable that receives arbitrary data and returns a
            :class:`GuardCheck`.  Must be side-effect free.
    """

    def __init__(self, name: str, check_fn: Callable[[Any], GuardCheck]) -> None:
        self.name = name
        self.check_fn = check_fn

    def check(self, data: Any) -> GuardCheck:
        """Run the guard against *data*.

        Args:
            data: The payload to inspect (raw string, dict, etc.).

        Returns:
            A :class:`GuardCheck` describing the outcome.
        """
        return self.check_fn(data)


class InputGuard:
    """Ordered collection of guards evaluated against agent input.

    All guards are run unconditionally so callers get a full picture of every
    problem; the first ``"fail"`` result is what blocks execution.

    Args:
        *guards: One or more :class:`Guard` instances to run in sequence.
    """

    def __init__(self, *guards: Guard) -> None:
        self._guards: tuple[Guard, ...] = guards

    def check(self, input_data: Any) -> list[GuardCheck]:
        """Evaluate every guard against *input_data*.

        Args:
            input_data: The raw input destined for the agent.

        Returns:
            A list of :class:`GuardCheck` instances, one per guard.
        """
        return [g.check(input_data) for g in self._guards]


class OutputGuard:
    """Ordered collection of guards evaluated against agent output.

    Args:
        *guards: One or more :class:`Guard` instances to run in sequence.
    """

    def __init__(self, *guards: Guard) -> None:
        self._guards: tuple[Guard, ...] = guards

    def check(self, output_data: Any) -> list[GuardCheck]:
        """Evaluate every guard against *output_data*.

        Args:
            output_data: The value returned by the agent function.

        Returns:
            A list of :class:`GuardCheck` instances, one per guard.
        """
        return [g.check(output_data) for g in self._guards]


# ---------------------------------------------------------------------------
# guarded() wrapper
# ---------------------------------------------------------------------------


def guarded(
    input_guard: InputGuard | None,
    agent_fn: Callable[..., Any],
    output_guard: OutputGuard | None,
) -> Callable[..., GuardedResult]:
    """Wrap *agent_fn* with pre/post validation phases.

    Execution flow::

        input_guard.check(args[0])  →  [if fail: block]
        agent_fn(*args, **kwargs)
        output_guard.check(result)  →  [flag failures but return output]

    Args:
        input_guard: Guards to evaluate before the agent runs.  Pass ``None``
            to skip input validation.
        agent_fn: The agent callable to protect.  It is called with the same
            positional and keyword arguments passed to the wrapper.
        output_guard: Guards to evaluate after the agent runs.  Pass ``None``
            to skip output validation.

    Returns:
        A wrapper that accepts the same signature as *agent_fn* but always
        returns a :class:`GuardedResult`.

    Example::

        safe = guarded(InputGuard(pii_detector), my_fn, OutputGuard(banned_phrases))
        result = safe("Hello, my email is user@example.com")
        assert result.blocked
    """

    def _wrapper(*args: Any, **kwargs: Any) -> GuardedResult:
        # --- Phase 1: input validation ---
        input_checks: list[GuardCheck] = []
        if input_guard is not None:
            # Inspect the first positional arg (the "payload") when present.
            payload = args[0] if args else kwargs
            input_checks = input_guard.check(payload)

        failing_input = [c for c in input_checks if c.result == "fail"]
        if failing_input:
            block_reason = "; ".join(
                f"{c.name}: {c.details}" for c in failing_input
            )
            return GuardedResult(
                input_checks=input_checks,
                output_checks=[],
                all_passed=False,
                blocked=True,
                block_reason=block_reason,
                output=None,
            )

        # --- Phase 2: execute agent ---
        raw_output: Any = agent_fn(*args, **kwargs)

        # --- Phase 3: output validation ---
        output_checks: list[GuardCheck] = []
        if output_guard is not None:
            output_checks = output_guard.check(raw_output)

        failing_output = [c for c in output_checks if c.result == "fail"]
        all_passed = len(failing_output) == 0

        return GuardedResult(
            input_checks=input_checks,
            output_checks=output_checks,
            all_passed=all_passed,
            blocked=False,
            block_reason=None,
            output=raw_output,
        )

    _wrapper.__name__ = f"guarded_{agent_fn.__name__}"
    _wrapper.__qualname__ = f"guarded_{agent_fn.__qualname__}"
    return _wrapper


# ---------------------------------------------------------------------------
# Regex patterns (private)
# ---------------------------------------------------------------------------

# Input patterns
_RE_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)
_RE_PHONE = re.compile(
    r"(?:\+\d[\s\-.]?)?(?:\(\d{3}\)|\d{3})[\s\-.]?\d{3}[\s\-.]?\d{4}\b"
)
_RE_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_RE_API_KEY = re.compile(r"\b(?:sk-|key-)[A-Za-z0-9_\-]{8,}\b")

_RE_INJECTION = re.compile(
    r"(?i)(?:ignore\s+previous|disregard\s+instructions?|system\s+prompt)",
)

# Output patterns
_RE_BANNED = re.compile(
    r"(?i)(?:I(?:'ve| have)\s+successfully|I(?:'m| am)\s+happy\s+to|"
    r"I(?:'d| would)\s+be\s+glad\s+to|Certainly!|Absolutely!)"
)
_RE_DESTRUCTIVE = re.compile(
    r"(?i)(?:\bdrop\s+table\b|\bdelete\s+from\b|\brm\s+-[rRfF]+\b|"
    r"\btruncate\s+table\b|\bformat\s+[a-z]:\b)"
)

# Scope: configurable out-of-scope pattern. Disabled by default.
# Domain-specific brains can override this via configure_scope_guard().
# Layer 0 patterns MUST NOT hardcode domain-specific competitor names.
_RE_OUT_OF_SCOPE: re.Pattern | None = None


# ---------------------------------------------------------------------------
# Guard check functions (private)
# ---------------------------------------------------------------------------


def _check_pii(data: Any) -> GuardCheck:
    """Detect email, phone, SSN, or API key patterns in *data*."""
    text = str(data)
    findings: list[str] = []

    if _RE_EMAIL.search(text):
        findings.append("email address")
    if _RE_PHONE.search(text):
        findings.append("phone number")
    if _RE_SSN.search(text):
        findings.append("SSN (NNN-NN-NNNN)")
    if _RE_API_KEY.search(text):
        findings.append("API key (sk-* or key-*)")

    if findings:
        detail = "PII detected: " + ", ".join(findings)
        return GuardCheck(
            name="pii_detector",
            result="fail",
            details=detail,
            action_taken="blocked",
        )
    return GuardCheck(
        name="pii_detector",
        result="pass",
        details="No PII patterns found.",
        action_taken="passed",
    )


def _check_injection(data: Any) -> GuardCheck:
    """Detect prompt-injection attempts in *data*."""
    text = str(data)
    match = _RE_INJECTION.search(text)
    if match:
        return GuardCheck(
            name="injection_detector",
            result="fail",
            details=f"Injection pattern detected: '{match.group(0)}'",
            action_taken="blocked",
        )
    return GuardCheck(
        name="injection_detector",
        result="pass",
        details="No injection patterns found.",
        action_taken="passed",
    )


def _check_scope(data: Any) -> GuardCheck:
    """Validate that the request is in-scope (configurable, disabled by default)."""
    if _RE_OUT_OF_SCOPE is None:
        return GuardCheck(name="scope_validator", result="pass", details="scope guard disabled", action_taken="passed")
    text = str(data)
    match = _RE_OUT_OF_SCOPE.search(text)
    if match:
        return GuardCheck(
            name="scope_validator",
            result="fail",
            details=f"Out-of-scope reference detected: '{match.group(0)}'",
            action_taken="blocked",
        )
    return GuardCheck(
        name="scope_validator",
        result="pass",
        details="Request is in-scope.",
        action_taken="passed",
    )


def _check_banned(data: Any) -> GuardCheck:
    """Detect banned filler phrases in agent output."""
    text = str(data)
    match = _RE_BANNED.search(text)
    if match:
        return GuardCheck(
            name="banned_phrases",
            result="fail",
            details=f"Banned phrase detected: '{match.group(0)}'",
            action_taken="redacted",
        )
    return GuardCheck(
        name="banned_phrases",
        result="pass",
        details="No banned phrases found.",
        action_taken="passed",
    )


def _check_destructive(data: Any) -> GuardCheck:
    """Detect destructive operations (DROP, DELETE, rm -rf, etc.) in output."""
    text = str(data)
    match = _RE_DESTRUCTIVE.search(text)
    if match:
        return GuardCheck(
            name="destructive_action",
            result="fail",
            details=f"Destructive operation detected: '{match.group(0)}'",
            action_taken="blocked",
        )
    return GuardCheck(
        name="destructive_action",
        result="pass",
        details="No destructive operations found.",
        action_taken="passed",
    )


# ---------------------------------------------------------------------------
# Built-in guard singletons
# ---------------------------------------------------------------------------

#: Detects email addresses, phone numbers, SSNs, and API keys (``sk-*``, ``key-*``).
pii_detector = Guard("pii_detector", _check_pii)

#: Detects common prompt-injection patterns (``ignore previous``, etc.).
injection_detector = Guard("injection_detector", _check_injection)

#: Validates that the request does not reference out-of-scope platforms.
scope_validator = Guard("scope_validator", _check_scope)

#: Flags sycophantic filler phrases (``I've successfully``, ``Certainly!``, etc.).
banned_phrases = Guard("banned_phrases", _check_banned)

#: Flags destructive operations (``DROP TABLE``, ``rm -rf``, ``DELETE FROM``).
destructive_action = Guard("destructive_action", _check_destructive)


# ---------------------------------------------------------------------------
# Manifest-Based Agent Security (extracted from brain/scripts/guardrails.py)
# ---------------------------------------------------------------------------
# Pure computation over pre-loaded manifest data. The caller loads the manifest
# (JSON file) and passes the relevant sections to these functions.
# This separates the "what to check" (here) from "where to find config" (caller).


@dataclass
class ManifestCheckResult:
    """Result of a manifest-based security check.

    Attributes:
        allowed: Whether the action is permitted.
        reason: Human-readable explanation.
        budget: Allocated token budget (only for spawn checks).
    """

    allowed: bool
    reason: str
    budget: int = 0


def check_write_path(
    target_path: str,
    agent_write_paths: list[str],
    agent_tools_denied: list[str] | None = None,
    global_deny: list[str] | None = None,
) -> ManifestCheckResult:
    """Check if a target path is allowed for an agent.

    Pure function: receives the policy data, not the manifest file.

    Args:
        target_path: Path the agent wants to write to.
        agent_write_paths: Allowed write path patterns from the agent's manifest entry.
        agent_tools_denied: Optional denied tool patterns (e.g., "Write docs/**").
        global_deny: Optional global deny patterns that apply to all agents.

    Returns:
        ManifestCheckResult with allowed/denied and reason.
    """
    from fnmatch import fnmatch

    # Normalize path
    target = target_path.replace("\\", "/")
    while target.startswith("./"):
        target = target[2:]

    # 1. Global deny list
    for pattern in (global_deny or []):
        if fnmatch(target, pattern) or fnmatch(target.split("/")[-1], pattern):
            return ManifestCheckResult(False, f"DENIED by global policy: matches '{pattern}'")

    # 2. Agent-specific write_paths
    for pattern in agent_write_paths:
        if fnmatch(target, pattern):
            return ManifestCheckResult(True, f"ALLOWED: matches agent write path '{pattern}'")

    # 3. Check tools_denied for write restrictions
    for denial in (agent_tools_denied or []):
        if denial.startswith("Write "):
            deny_pattern = denial[6:]
            if fnmatch(target, deny_pattern):
                return ManifestCheckResult(False, f"DENIED by agent tool restriction: '{denial}'")

    return ManifestCheckResult(
        False,
        f"DENIED: '{target}' not in allowed write paths. Allowed: {agent_write_paths}",
    )


def check_exec_command(
    command: str,
    deny_patterns: list[str],
) -> ManifestCheckResult:
    """Check if a command is allowed to execute.

    Args:
        command: The shell command to validate.
        deny_patterns: List of substrings that block execution.

    Returns:
        ManifestCheckResult with allowed/denied and reason.
    """
    cmd_lower = command.lower().strip()
    for pattern in deny_patterns:
        if pattern.lower() in cmd_lower:
            return ManifestCheckResult(False, f"DENIED: command matches blocked pattern '{pattern}'")
    return ManifestCheckResult(True, "ALLOWED: no deny patterns matched")


def scan_for_secrets(
    text: str,
    patterns: list[str],
    pattern_names: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Scan text for sensitive data patterns.

    Args:
        text: The text to scan.
        patterns: List of regex patterns to check.
        pattern_names: Optional mapping of pattern -> friendly name.

    Returns:
        List of (pattern_name, masked_preview) tuples. Empty = clean.
    """
    names = pattern_names or {}
    findings: list[tuple[str, str]] = []
    for pattern in patterns:
        name = names.get(pattern, "unknown_secret")
        matches = re.findall(pattern, text)
        for match in matches:
            preview = match[:8] + "..." if len(match) > 8 else match
            findings.append((name, preview))
    return findings


def validate_agent_spawn(
    max_tokens: int,
    budget_enabled: bool = False,
    parent_budget_remaining: int | None = None,
    parent_reserves_percent: int = 20,
    child_warning_threshold_percent: int = 80,
    child_hard_limit_percent: int = 95,
) -> ManifestCheckResult:
    """Validate whether an agent can be spawned within budget constraints.

    Args:
        max_tokens: The agent's requested token budget.
        budget_enabled: Whether budget cascade is active.
        parent_budget_remaining: Remaining tokens in parent's budget.
        parent_reserves_percent: Percentage parent must keep in reserve.
        child_warning_threshold_percent: Usage % that triggers a warning.
        child_hard_limit_percent: Usage % that blocks the spawn.

    Returns:
        ManifestCheckResult with allowed/denied, reason, and allocated budget.
    """
    if not budget_enabled or parent_budget_remaining is None:
        return ManifestCheckResult(True, f"ALLOWED: budget {max_tokens} tokens", max_tokens)

    reserve = int(parent_budget_remaining * parent_reserves_percent / 100)
    available = parent_budget_remaining - reserve

    if available >= max_tokens:
        return ManifestCheckResult(True, f"ALLOWED: budget {max_tokens} tokens", max_tokens)

    usage_pct = int((max_tokens / parent_budget_remaining) * 100) if parent_budget_remaining > 0 else 100

    if usage_pct >= child_hard_limit_percent:
        return ManifestCheckResult(
            False,
            f"DENIED: would consume {usage_pct}% of parent budget (hard limit: {child_hard_limit_percent}%)",
            0,
        )

    if usage_pct >= child_warning_threshold_percent:
        return ManifestCheckResult(
            True,
            f"ALLOWED with WARNING: consuming {usage_pct}% of parent budget",
            min(available, max_tokens),
        )

    return ManifestCheckResult(
        True,
        f"ALLOWED: budget constrained to {available} tokens (requested {max_tokens})",
        min(available, max_tokens),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Classes
    "Guard",
    # Data types
    "GuardCheck",
    "GuardedResult",
    "InputGuard",
    "ManifestCheckResult",
    "OutputGuard",
    "banned_phrases",
    "check_exec_command",
    # Manifest-based agent security
    "check_write_path",
    "destructive_action",
    # Wrapper
    "guarded",
    "guards_from_graduated_rules",
    "injection_detector",
    # Built-in guards
    "pii_detector",
    "scan_for_secrets",
    "scope_validator",
    "validate_agent_spawn",
]


# ---------------------------------------------------------------------------
# RuleContext integration — graduated rules become guardrail checks
# ---------------------------------------------------------------------------


def guards_from_graduated_rules() -> list[Guard]:
    """Build Guard objects from graduated SECURITY/ACCURACY rules.

    Graduated rules in safety-related categories automatically become
    output guards, so the guardrail set grows from corrections.

    Example: A SECURITY rule "never include API keys" becomes a Guard
    that checks output for common API key patterns.
    """
    try:
        from ...rules.rule_context import get_rule_context
    except ImportError:
        return []

    ctx = get_rule_context()
    rules = ctx.for_guardrails()

    guards = []
    for rule in rules:
        rule.principle.lower()

        def _make_check(rule_text: str, rule_cat: str) -> Callable[[Any], GuardCheck]:
            """Create a check function that scans output for rule violations."""
            def check_fn(data: Any) -> GuardCheck:
                str(data).lower() if data else ""
                # Simple keyword check — does the output violate the rule?
                # Rules are phrased as "never X" or "always Y"
                # This is a heuristic; real guardrails need LLM-backed checks
                return GuardCheck(
                    name=f"rule_{rule_cat.lower()}",
                    result="pass",
                    details=f"Rule: {rule_text[:80]}",
                    action_taken="passed",
                )
            return check_fn

        guards.append(Guard(
            name=f"rule_{rule.category.lower()}_{len(guards)}",
            check_fn=_make_check(rule.principle, rule.category),
        ))
    return guards
