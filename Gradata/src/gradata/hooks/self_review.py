"""PostToolUse hook: self-review against mandatory rules.

After Write/Edit tool calls, checks if the output respects mandatory
rules. Logs violations for the learning pipeline without blocking execution.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "PostToolUse",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}

# Tools whose output content is checked for rule compliance.
_REVIEWED_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})

# Regex to pull the banned token out of "never use/do/create/add/include <X>"
_NEVER_RE = re.compile(r"never\s+(?:use|do|create|add|include)\s+(.+)", re.I)

# Process-level cache: (brain_dir, mtime) → parsed mandatory rules
_rules_cache: dict[tuple[str, float], list[dict]] = {}


def _load_mandatory_rules(brain_dir: str) -> list[dict]:
    """Load RULE-tier mandatory lessons, cached by file mtime."""
    try:
        from gradata._types import LessonState
        from gradata.enhancements.self_improvement import parse_lessons

        lessons_path = Path(brain_dir) / "lessons.md"
        if not lessons_path.is_file():
            return []
        mtime = lessons_path.stat().st_mtime
        cache_key = (brain_dir, mtime)
        if cache_key in _rules_cache:
            return _rules_cache[cache_key]
        text = lessons_path.read_text(encoding="utf-8")
        lessons = parse_lessons(text)
        result = [
            {"description": l.description, "category": l.category}
            for l in lessons
            if l.state == LessonState.RULE and l.confidence >= 0.90 and l.fire_count >= 10
        ]
        _rules_cache.clear()
        _rules_cache[cache_key] = result
        return result
    except Exception as exc:
        _log.debug("_load_mandatory_rules failed: %s", exc)
        return []


def _check_rule_compliance(
    output_text: str,
    rules: list[dict],
) -> list[dict]:
    """Check output against mandatory rules using keyword matching.

    Only "never use/do/create/add/include <X>" rules can be checked
    deterministically from output text alone. Positive directives
    ("always ...") require tool-call trace context and are skipped here.

    Returns a list of violation dicts with keys: rule, category, evidence, severity.
    """
    violations = []
    output_lower = output_text.lower()

    for rule in rules:
        desc = rule["description"]
        m = _NEVER_RE.search(desc)
        if not m:
            continue

        banned_raw = m.group(1).strip()
        # Strip trailing punctuation that may appear in the lesson text.
        banned = re.sub(r"[.,;:!?]+$", "", banned_raw).strip().lower()
        if not banned:
            continue

        if banned in output_lower:
            violations.append(
                {
                    "rule": desc,
                    "category": rule["category"],
                    "evidence": f"Output contains '{banned}'",
                    "severity": "warning",
                }
            )

    return violations


def _log_violations(brain_dir: str, violations: list[dict]) -> None:
    """Emit SELF_REVIEW_VIOLATION events so the learning pipeline can record them."""
    try:
        from gradata._events import emit
        from gradata._paths import BrainContext

        ctx = BrainContext.from_brain_dir(brain_dir)
        for v in violations:
            emit(
                "SELF_REVIEW_VIOLATION",
                source="hook:self_review",
                data={
                    "rule": v["rule"],
                    "category": v["category"],
                    "evidence": v["evidence"],
                    "severity": v["severity"],
                },
                ctx=ctx,
            )
    except Exception as exc:
        _log.debug("_log_violations emit failed: %s", exc)


def _extract_output_text(data: dict) -> str:
    """Pull the text content from the hook payload.

    Claude Code PostToolUse delivers the written/edited text in
    tool_output or output. Fall back through both keys.
    """
    for key in ("tool_output", "output"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def main(data: dict) -> dict | None:
    tool = data.get("tool_name", "")
    if tool not in _REVIEWED_TOOLS:
        return None

    brain_dir = resolve_brain_dir()
    if not brain_dir:
        return None

    output = _extract_output_text(data)
    if not output:
        return None

    rules = _load_mandatory_rules(brain_dir)
    if not rules:
        return None

    violations = _check_rule_compliance(output, rules)
    if violations:
        _log.info(
            "self_review: %d potential violation(s) in %s output",
            len(violations),
            tool,
        )
        _log_violations(brain_dir, violations)

    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
