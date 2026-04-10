"""SessionStart hook: inject graduated rules into session context.

Wiki-aware mode: when brain/wiki/concepts/rule-*.md pages exist,
uses qmd semantic search to find rules relevant to the current
session context instead of brute-force top-10 by confidence.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

try:
    from gradata.enhancements.self_improvement import parse_lessons
except ImportError:
    parse_lessons = None

_log = logging.getLogger(__name__)

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


def _wiki_categories(context: str) -> set[str]:
    """Query qmd for rule wiki pages matching context, return matched categories.

    Searches brain wiki for pages whose path matches rule-{category}.md.
    Returns empty set on any failure so caller falls back to brute-force.
    """
    if not context:
        return set()
    # On Windows, qmd is an npm bash script — Python can't exec .CMD wrappers
    # directly, so we route through Git Bash. On Unix, qmd runs natively.
    if sys.platform == "win32":
        git_bash = shutil.which("bash", path="C:/Program Files/Git/bin")
        if git_bash:
            cmd = [git_bash, "-c", f'qmd search "{context}" -c brain -n 10']
        else:
            return set()  # no bash = no qmd on Windows
    else:
        cmd = ["qmd", "search", context, "-c", "brain", "-n", "10"]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=2, encoding="utf-8",
        )
        if proc.returncode != 0:
            return set()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return set()

    categories: set[str] = set()
    for line in proc.stdout.splitlines():
        # qmd paths: qmd://brain/wiki/concepts/rule-code.md:N
        if "wiki/concepts/rule-" in line:
            try:
                segment = line.split("wiki/concepts/rule-")[1]
                cat = segment.split(".md")[0].upper().replace("-", "_")
                categories.add(cat)
            except (IndexError, ValueError):
                continue
    return categories


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
    filtered = [
        lesson for lesson in all_lessons
        if lesson.state.name in ("RULE", "PATTERN") and lesson.confidence >= MIN_CONFIDENCE
    ]
    if not filtered:
        return None

    # Wiki-aware selection: find categories relevant to session context
    context = (
        data.get("session_type", "")
        or data.get("task_type", "")
        or Path.cwd().name
    )
    wiki_cats = _wiki_categories(context)

    if wiki_cats:
        boosted = [lesson for lesson in filtered if lesson.category.upper() in wiki_cats]
        rest = [lesson for lesson in filtered if lesson.category.upper() not in wiki_cats]
        boosted_sorted = sorted(boosted, key=_score, reverse=True)[:MAX_RULES]
        rest_sorted = sorted(rest, key=_score, reverse=True)
        remaining = MAX_RULES - len(boosted_sorted)
        scored = (boosted_sorted + rest_sorted[:max(0, remaining)])[:MAX_RULES]
        _log.debug(
            "Wiki-aware injection: %d boosted (%s), %d fill",
            len(boosted_sorted), wiki_cats, min(len(rest_sorted), max(0, remaining)),
        )
    else:
        scored = sorted(filtered, key=_score, reverse=True)[:MAX_RULES]

    lines = []
    for r in scored:
        lines.append(f"[{r.state.name}:{r.confidence:.2f}] {r.category}: {r.description}")

    block = "<brain-rules>\n" + "\n".join(lines) + "\n</brain-rules>"
    return {"result": block}


if __name__ == "__main__":
    run_hook(main, HOOK_META)
