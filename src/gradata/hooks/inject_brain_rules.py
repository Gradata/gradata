"""SessionStart hook: inject graduated rules into session context."""
from __future__ import annotations
import os
import re
from pathlib import Path
from gradata.hooks._base import run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "SessionStart",
    "profile": Profile.MINIMAL,
    "timeout": 10000,
}

MAX_RULES = 10
MIN_CONFIDENCE = 0.60
RULE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+\[(RULE|PATTERN):([0-9.]+)\]\s+(\w+):\s+(.+)$"
)


def _parse_lessons(text: str) -> list[dict]:
    lessons = []
    for line in text.splitlines():
        m = RULE_RE.match(line.strip())
        if not m:
            continue
        date, state, conf_str, category, description = m.groups()
        conf = float(conf_str)
        if conf < MIN_CONFIDENCE:
            continue
        lessons.append({
            "date": date,
            "state": state,
            "confidence": conf,
            "category": category,
            "description": description.strip(),
        })
    return lessons


def _score(lesson: dict) -> float:
    conf_norm = (lesson["confidence"] - 0.6) / 0.4
    state_bonus = 1.0 if lesson["state"] == "RULE" else 0.7
    return 0.4 * state_bonus + 0.3 * conf_norm + 0.3 * lesson["confidence"]


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
    lessons = _parse_lessons(text)
    if not lessons:
        return None

    scored = sorted(lessons, key=_score, reverse=True)[:MAX_RULES]

    lines = []
    for r in scored:
        lines.append(f"[{r['state']}:{r['confidence']:.2f}] {r['category']}: {r['description']}")

    block = "<brain-rules>\n" + "\n".join(lines) + "\n</brain-rules>"
    return {"result": block}


if __name__ == "__main__":
    run_hook(main, HOOK_META)
