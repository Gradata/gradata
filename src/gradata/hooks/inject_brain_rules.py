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
from gradata.rules.rule_ranker import rank_rules

try:
    from gradata.enhancements.self_improvement import is_hook_enforced, parse_lessons
except ImportError:
    parse_lessons = None
    is_hook_enforced = None  # type: ignore[assignment]

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
    """Back-compat scorer. Kept so existing tests / callers keep working.

    Prefer :func:`rank_rules` directly for new code — it supports BM25 context
    relevance and optional Thompson sampling. This function is a simple
    state/confidence blend retained for tie-breaking snapshots.
    """
    conf = lesson["confidence"] if isinstance(lesson, dict) else lesson.confidence
    state = lesson["state"] if isinstance(lesson, dict) else lesson.state.name
    conf_norm = (conf - MIN_CONFIDENCE) / (1.0 - MIN_CONFIDENCE)
    state_bonus = 1.0 if state == "RULE" else 0.7
    return 0.4 * state_bonus + 0.3 * conf_norm + 0.3 * conf


def _lesson_to_rule_dict(lesson) -> dict:
    """Flatten a Lesson object (or dict) into the shape rank_rules expects.

    Carries Beta posterior fields (alpha / beta_param) through so Thompson
    sampling works when ``GRADATA_THOMPSON_RANKING=1``.
    """
    if isinstance(lesson, dict):
        return dict(lesson)
    return {
        "id": getattr(lesson, "description", ""),
        "description": getattr(lesson, "description", ""),
        "category": getattr(lesson, "category", ""),
        "confidence": float(getattr(lesson, "confidence", 0.5)),
        "fire_count": int(getattr(lesson, "fire_count", 0)),
        "last_session": 0,  # not tracked on Lesson — recency degrades gracefully
        "alpha": float(getattr(lesson, "alpha", 1.0)),
        "beta_param": float(getattr(lesson, "beta_param", 1.0)),
        "state": lesson.state.name if hasattr(lesson, "state") else "PATTERN",
        "_lesson": lesson,  # stash original for output formatting
    }


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
    # Phase 5 rule-to-hook auto-promotion: rules enforced by an installed
    # generated hook (metadata.how_enforced == "hooked", or legacy "[hooked]"
    # description prefix) are applied deterministically, so injecting them as
    # text wastes context. Hook removal clears the marker and re-enables text
    # injection automatically.
    if is_hook_enforced is not None:
        filtered = [lesson for lesson in filtered if not is_hook_enforced(lesson)]
    if not filtered:
        return None

    # Wiki-aware selection: find categories relevant to session context
    context = (
        data.get("session_type", "")
        or data.get("task_type", "")
        or Path.cwd().name
    )
    wiki_cats = _wiki_categories(context)

    # Route everything through the unified rule_ranker. Wiki-matched categories
    # become a wiki_boost signal (+0.3 on context component) rather than a
    # hard pre-filter, so BM25 + Thompson can still surface strong cross-
    # category matches when the wiki miss-matches.
    rule_dicts = [_lesson_to_rule_dict(lesson) for lesson in filtered]
    wiki_boost: dict[str, float] = {}
    if wiki_cats:
        for rd in rule_dicts:
            if rd.get("category", "").upper() in wiki_cats:
                wiki_boost[rd["id"]] = 0.3

    context_keywords = [
        kw for kw in (
            data.get("session_type", ""),
            data.get("task_type", ""),
            context,
        )
        if kw
    ]

    # Derive a per-session seed for deterministic Thompson sampling.
    session_seed = data.get("session_number") or data.get("session_id")
    if isinstance(session_seed, str):
        try:
            session_seed = int(session_seed)
        except ValueError:
            session_seed = abs(hash(session_seed)) % (2**31)

    ranked = rank_rules(
        rule_dicts,
        current_session=int(data.get("session_number") or 0),
        task_type=data.get("task_type") or data.get("session_type") or None,
        context_keywords=context_keywords or None,
        max_rules=MAX_RULES,
        wiki_boost=wiki_boost or None,
        session_seed=session_seed if isinstance(session_seed, int) else None,
    )
    scored: list = []
    for rd in ranked:
        lesson = rd.get("_lesson")
        if lesson is not None:
            scored.append(lesson)
    _log.debug(
        "Unified injection: %d ranked (wiki_boost=%d)",
        len(scored), len(wiki_boost),
    )

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
        # Wrap the entire load -> filter -> format pipeline. A partially corrupt
        # system.db can deserialize successfully (e.g. JSON `null` for
        # source_lesson_ids) and then blow up later with TypeError inside the
        # formatter. We must degrade to rules-only rather than aborting
        # SessionStart.
        try:
            metas = load_meta_rules(db_path)
            injectable = [
                m for m in metas
                if getattr(m, "source", "deterministic") in INJECTABLE_META_SOURCES
            ]
            if injectable:
                # Build a sanitized condition_context from the hook payload so
                # applies_when / never_when are honored during SessionStart.
                # We only forward small, string-shaped fields the rule engine
                # uses for gating — no file contents, transcripts, or secrets.
                condition_context = {
                    k: data[k]
                    for k in ("session_type", "task_type", "source", "cwd")
                    if isinstance(data.get(k), (str, int, float, bool))
                }
                if context and "context" not in condition_context:
                    condition_context["context"] = context

                # Pass the full injectable set with `limit=MAX_META_RULES` so
                # the cap is applied AFTER context-aware ranking inside the
                # formatter. Pre-slicing by raw confidence would let a
                # lower-confidence rule with a strong context weight get
                # silently excluded.
                formatted = format_meta_rules_for_prompt(
                    injectable,
                    context=context,
                    condition_context=condition_context,
                    limit=MAX_META_RULES,
                )
                if formatted:
                    meta_block = (
                        "\n<brain-meta-rules>\n"
                        + formatted
                        + "\n</brain-meta-rules>"
                    )
            elif metas:
                _log.debug(
                    "Skipped meta-rule injection: %d metas in DB, none with "
                    "injectable source (llm_synth or human_curated)",
                    len(metas),
                )
        except Exception as exc:
            _log.debug(
                "meta-rule pipeline failed (%s) — degrading to rules-only", exc,
            )
            meta_block = ""

    return {"result": rules_block + meta_block}


if __name__ == "__main__":
    run_hook(main, HOOK_META)
