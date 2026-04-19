"""CrewAIGuard callable for agent ``guardrails=[...]``. Returns the expected
``(valid, result_or_error)``. No hard dep on crewai.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._core import (
    RuleSource,
    RuleViolation,
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
        if output is None:
            text = ""
        elif isinstance(output, str):
            text = output
        else:
            text = ""
            for key in _OUTPUT_TEXT_KEYS:
                val = getattr(output, key, None)
                if isinstance(val, str):
                    text = val
                    break
            else:
                if isinstance(output, dict):
                    for key in _OUTPUT_TEXT_KEYS:
                        val = output.get(key)
                        if isinstance(val, str):
                            text = val
                            break
                    else:
                        text = str(output)
                else:
                    text = str(output)
        if not text:
            return True, output
        try:
            violations = check_output(self._source, text, strict=False)
        except RuleViolation as v:  # pragma: no cover - strict=False above
            return False, str(v)
        if not violations:
            return True, output
        if self._strict:
            message = "; ".join(f"{v.pattern_name}: {v.rule_description}" for v in violations)
            return False, f"Gradata rule violation(s): {message}"
        return True, output
