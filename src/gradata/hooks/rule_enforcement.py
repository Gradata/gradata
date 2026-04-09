"""PreToolUse hook: inject RULE-tier lessons as reminders before code edits."""
from __future__ import annotations
import os
import re
from pathlib import Path
from gradata.hooks._base import run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "PreToolUse",
    "matcher": "Write|Edit|MultiEdit",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}

RULE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\[RULE:([0-9.]+)\]\s+(\w+):\s+(.+)$")
MAX_REMINDERS = 5


def main(data: dict) -> dict | None:
    brain_dir = os.environ.get("GRADATA_BRAIN_DIR") or os.environ.get("BRAIN_DIR")
    if not brain_dir:
        default = Path.home() / ".gradata" / "brain"
        if default.exists():
            brain_dir = str(default)
        else:
            return None

    lessons_path = Path(brain_dir) / "lessons.md"
    if not lessons_path.is_file():
        return None

    text = lessons_path.read_text(encoding="utf-8")
    rules = []
    for line in text.splitlines():
        m = RULE_RE.match(line.strip())
        if m:
            conf, category, desc = m.groups()
            truncated = desc[:120] + "..." if len(desc) > 120 else desc
            rules.append(f"[RULE:{conf}] {category}: {truncated}")

    if not rules:
        return None

    top = rules[:MAX_REMINDERS]
    block = "ACTIVE RULES (learned from corrections):\n" + "\n".join(f"  • {r}" for r in top)
    return {"result": block}


if __name__ == "__main__":
    run_hook(main, HOOK_META)
