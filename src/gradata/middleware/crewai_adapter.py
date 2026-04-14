"""CrewAI middleware adapter.

Provides :class:`CrewAIGuard`, a callable that CrewAI agents can register
in their ``guardrails=[...]`` list. The guard runs on the agent's output
and returns the CrewAI-expected ``(valid, result_or_error)`` tuple.

Usage::

    from crewai import Agent
    from gradata.middleware import CrewAIGuard

    guard = CrewAIGuard(brain_path="./brain")
    agent = Agent(
        role="Writer",
        goal="Draft clean prose",
        backstory="...",
        guardrails=[guard],
    )

This adapter has no hard dependency on ``crewai`` — it only implements
the guard callable shape CrewAI expects, so tests can exercise it with a
plain Python call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gradata.middleware._core import (
    RuleSource,
    RuleViolation,
    _get,
    check_output,
)

_OUTPUT_TEXT_KEYS = ("raw", "output", "text", "content")


class CrewAIGuard:
    """A CrewAI-compatible guardrail that enforces Gradata RULE-tier rules.

    CrewAI guardrails are callables that take the agent output and return
    ``(is_valid, result_or_error_message)``. When ``strict`` is False
    (default) the guard always returns ``(True, output)`` but logs the
    violations for observability. When ``strict`` is True, a violation
    returns ``(False, "<explanation>")`` so CrewAI can retry.
    """

    def __init__(
        self,
        *,
        brain_path: str | Path | None = None,
        source: RuleSource | None = None,
        strict: bool = False,
    ) -> None:
        self._source = source or RuleSource(brain_path=brain_path)
        self._strict = strict

    def __call__(self, output: Any) -> tuple[bool, Any]:
        text = _coerce_text(output)
        if not text:
            return True, output
        try:
            violations = check_output(self._source, text, strict=False)
        except RuleViolation as v:  # pragma: no cover - strict=False above
            return False, str(v)
        if not violations:
            return True, output
        if self._strict:
            message = "; ".join(
                f"{v.pattern_name}: {v.rule_description}" for v in violations
            )
            return False, f"Gradata rule violation(s): {message}"
        return True, output


def _coerce_text(output: Any) -> str:
    """Best-effort text extraction for CrewAI agent outputs."""
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    for key in _OUTPUT_TEXT_KEYS:
        val = _get(output, key)
        if isinstance(val, str) and val:
            return val
    return str(output)
