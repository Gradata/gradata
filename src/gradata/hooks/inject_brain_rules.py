"""SessionStart hook: inject graduated rules into session context."""
from __future__ import annotations
from pathlib import Path
from gradata.hooks._base import run_hook, resolve_brain_dir
from gradata.hooks._profiles import Profile

try:
    from gradata.enhancements.self_improvement import parse_lessons
except ImportError:
    parse_lessons = None

HOOK_META = {
    "event": "SessionStart",
    "profile": Profile.MINIMAL,
    "timeout": 10000,
}

MAX_RULES = 10
MIN_CONFIDENCE = 0.60


def _score(lesson) -> float:
    """Score a lesson dict or Lesson object for injection priority."""
    conf = lesson["confidence"] if isinstance(lesson, dict) else lesson.confidence
    state = lesson["state"] if isinstance(lesson, dict) else lesson.state.name
    conf_norm = (conf - MIN_CONFIDENCE) / (1.0 - MIN_CONFIDENCE)
    state_bonus = 1.0 if state == "RULE" else 0.7
    return 0.4 * state_bonus + 0.3 * conf_norm + 0.3 * conf


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
    filtered = [lesson for lesson in all_lessons if lesson.state.name in ("RULE", "PATTERN") and lesson.confidence >= MIN_CONFIDENCE]
    if not filtered:
        return None

    scored = sorted(filtered, key=_score, reverse=True)[:MAX_RULES]

    lines = []
    for r in scored:
        lines.append(f"[{r.state.name}:{r.confidence:.2f}] {r.category}: {r.description}")

    block = "<brain-rules>\n" + "\n".join(lines) + "\n</brain-rules>"
    return {"result": block}


if __name__ == "__main__":
    run_hook(main, HOOK_META)
