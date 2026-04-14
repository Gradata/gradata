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

try:
    from gradata.enhancements.meta_rules import (
        INJECTABLE_META_SOURCES,
        format_meta_rules_for_prompt,
    )
    from gradata.enhancements.meta_rules_storage import load_meta_rules
except ImportError:
    format_meta_rules_for_prompt = None  # type: ignore[assignment]
    load_meta_rules = None  # type: ignore[assignment]
    INJECTABLE_META_SOURCES = frozenset()  # type: ignore[assignment]

_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "SessionStart",
    "profile": Profile.MINIMAL,
    "timeout": 10000,
}

MAX_RULES = 10
MIN_CONFIDENCE = 0.60
MAX_META_RULES = 5  # meta-rules are high-level principles — separate cap from MAX_RULES


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

    lines = [
        f"[{r.state.name}:{r.confidence:.2f}] {r.category}: {r.description}"
        for r in scored
    ]

    rules_block = "<brain-rules>\n" + "\n".join(lines) + "\n</brain-rules>"

    # Also inject tier-1 meta-rules (compound principles across 3+ lessons).
    # Without this, meta-rules are created + stored but never reach the LLM.
    # Quality gate: only inject metas whose principle text was LLM-synthesized
    # or human-curated. Deterministic auto-generated principles (the OSS
    # default) are excluded — the 2026-04-14 ablation (432 trials) showed they
    # regress correctness on Sonnet (-1.1%), DeepSeek (-1.4%), and halve the
    # qwen14b lift from +8.1% to +2.9%. Better to inject nothing than noise.
    meta_block = ""
    db_path = Path(brain_dir) / "system.db"
    if load_meta_rules and format_meta_rules_for_prompt and db_path.is_file():
        try:
            metas = load_meta_rules(db_path)
        except Exception as exc:
            _log.debug("meta-rule load failed (%s) — skipping injection", exc)
            metas = []
        injectable = [
            m for m in metas
            if getattr(m, "source", "deterministic") in INJECTABLE_META_SOURCES
        ]
        if injectable:
            top_metas = sorted(
                injectable, key=lambda m: getattr(m, "confidence", 0.0), reverse=True,
            )[:MAX_META_RULES]
            formatted = format_meta_rules_for_prompt(top_metas, context=context)
            if formatted:
                meta_block = "\n<brain-meta-rules>\n" + formatted + "\n</brain-meta-rules>"
        elif metas:
            _log.debug(
                "Skipped meta-rule injection: %d metas in DB, none with "
                "injectable source (llm_synth or human_curated)",
                len(metas),
            )

    return {"result": rules_block + meta_block}


if __name__ == "__main__":
    run_hook(main, HOOK_META)
