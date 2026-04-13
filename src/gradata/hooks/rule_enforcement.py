"""PreToolUse hook: inject RULE-tier lessons as reminders before code edits."""
from __future__ import annotations

from pathlib import Path

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

try:
    from gradata.enhancements.self_improvement import parse_lessons
except ImportError:
    parse_lessons = None

HOOK_META = {
    "event": "PreToolUse",
    "matcher": "Write|Edit|MultiEdit",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}

MAX_REMINDERS = 5


def main(data: dict) -> dict | None:
    if parse_lessons is None:
        return None

    brain_dir = resolve_brain_dir()
    if not brain_dir:
        return None

    lessons_path = Path(brain_dir) / "lessons.md"
    if not lessons_path.is_file():
        return None

    text = lessons_path.read_text(encoding="utf-8")
    all_lessons = parse_lessons(text)
    rule_lessons = [lesson for lesson in all_lessons if lesson.state.name == "RULE"]

    # Dedup: skip rules whose description is marked [hooked] — a generated
    # PreToolUse hook under .claude/hooks/pre-tool/generated/ is enforcing them
    # deterministically, so firing the soft text reminder here is noise.
    rule_lessons = [
        lesson for lesson in rule_lessons
        if not lesson.description.lstrip().startswith("[hooked]")
    ]

    if not rule_lessons:
        return None

    rules = []
    for lesson in rule_lessons[:MAX_REMINDERS]:
        desc = lesson.description
        truncated = desc[:120] + "..." if len(desc) > 120 else desc
        rules.append(f"[RULE:{lesson.confidence:.2f}] {lesson.category}: {truncated}")

    block = "ACTIVE RULES (learned from corrections):\n" + "\n".join(f"  • {r}" for r in rules)
    return {"result": block}


if __name__ == "__main__":
    run_hook(main, HOOK_META)
