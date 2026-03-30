#!/usr/bin/env python3
"""PostToolUse hook: checks tool output against active graduated rules.

Reads JSON from stdin (Claude Code hook format), extracts tool output,
runs rule_verifier.verify_rules(), logs results, and surfaces violations.

Advisory only — never blocks tool execution.
"""

import json
import os
import re
import sys
from pathlib import Path

# Fast exit for tools that don't need verification
SKIP_TOOLS = {"Read", "Glob", "Grep", "WebSearch", "WebFetch", "Agent",
              "TaskCreate", "TaskUpdate", "TaskGet", "TaskList",
              "SendMessage", "Skill", "ToolSearch"}


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return

    tool_name = data.get("tool_name", "")

    # Skip tools that don't produce verifiable output
    if tool_name in SKIP_TOOLS:
        return

    # Extract output text to verify
    tool_output = data.get("tool_output", "")
    if isinstance(tool_output, dict):
        tool_output = json.dumps(tool_output)
    if not tool_output or len(tool_output) < 20:
        return

    # Truncate very long outputs for performance (verify first 4K)
    text = tool_output[:4096]

    # Load active rules from lessons.md
    lessons_path = _find_lessons()
    if not lessons_path:
        return

    rules = _parse_rules_fast(lessons_path)
    if not rules:
        return

    # Import rule_verifier from SDK
    sdk_path = os.path.join(
        os.environ.get("WORKING_DIR",
                       "C:/Users/olive/OneDrive/Desktop/Sprites Work"),
        "sdk", "src"
    )
    if sdk_path not in sys.path:
        sys.path.insert(0, sdk_path)

    try:
        from gradata.enhancements.rule_verifier import verify_rules
    except ImportError:
        return

    results = verify_rules(text, rules)
    violations = [r for r in results if not r.passed]

    if not violations:
        return

    # Log to events.jsonl
    _log_event(violations, tool_name)

    # Surface violations as advisory message
    lines = []
    for v in violations[:3]:  # Cap at 3 to keep output short
        lines.append(f"[rule-verify] {v.rule_category}: {v.violation_detail}")
        if v.output_snippet:
            lines.append(f"  snippet: {v.output_snippet[:80]}")

    msg = "\n".join(lines)
    print(json.dumps({"result": msg}))


def _find_lessons() -> Path | None:
    """Find lessons.md — check brain dir then .claude/."""
    brain_dir = os.environ.get("BRAIN_DIR", "C:/Users/olive/SpritesWork/brain")
    p = Path(brain_dir) / "lessons.md"
    if p.is_file():
        return p

    working = os.environ.get(
        "WORKING_DIR", "C:/Users/olive/OneDrive/Desktop/Sprites Work"
    )
    p = Path(working) / ".claude" / "lessons.md"
    if p.is_file():
        return p

    return None


# Fast regex for lesson lines: [DATE] [STATE:CONF] CATEGORY: description
_LESSON_RE = re.compile(
    r"\[[\d-]+\]\s+"
    r"\[(PATTERN|RULE)[:\d.]*\]\s+"
    r"(\w[\w_/]*?):\s+"
    r"(.+)"
)


def _parse_rules_fast(path: Path) -> list[dict]:
    """Parse only PATTERN/RULE graduated lessons (skip INSTINCT)."""
    rules = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return rules

    for line in text.splitlines():
        m = _LESSON_RE.match(line.strip())
        if m:
            rules.append({
                "category": m.group(2),
                "description": m.group(3),
            })
    return rules


def _log_event(violations, tool_name: str):
    """Append verification event to events.jsonl."""
    from datetime import datetime, timezone
    events_path = os.environ.get("BRAIN_DIR", "C:/Users/olive/SpritesWork/brain")
    events_file = Path(events_path) / "events.jsonl"
    try:
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "RULE_VERIFICATION",
            "source": "hook.rule-verify-post-tool",
            "tool": tool_name,
            "violations": len(violations),
            "categories": list({v.rule_category for v in violations}),
        }
        with open(events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass  # Never block on logging failure


if __name__ == "__main__":
    main()