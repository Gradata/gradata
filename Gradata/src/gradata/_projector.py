"""
Memory projector: SQLite + lessons.md → file-tree projection for LLM Memory tools.
=================================================================================

Council architecture (April 2026): SQLite remains source-of-truth for the event
log, FSRS state, and audit trail. The projector emits a deterministic file tree
that Anthropic's Memory tool (and analogous OpenAI / Gemini context features)
can JIT-pull, so callers stop cat-injecting the entire ruleset on every turn.

Activation entropy (NOT topic) is the sharding key. Five files map to five
injection regimes:

    voice.md         — fires every draft, cache-friendly prefix
    decisions.md     — sparse rubrics, recall on demand
    process.md       — deterministic hooks (out of prompt entirely; documented here)
    preferences.md   — volatile, recall on demand (bad cache target)
    relations.md     — entity-keyed, looked up at mention time

Why files, not a single dump: physical-path isolation lets the rentable-brain
SKU namespace `/personas/<id>/memories/` read-only and `/users/<id>/overlay/`
writable without ACL plumbing. The path IS the routing primitive.

Determinism: same lesson set in → byte-identical output. No timestamps, no
random ordering. Critical for caching and for the audit trail.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from gradata._types import ELIGIBLE_STATES, Lesson, LessonState

if TYPE_CHECKING:
    from gradata.brain import Brain

_log = logging.getLogger("gradata.projector")

# ─── Activation-entropy classifier ────────────────────────────────────────────
# Maps each lesson's category onto the file that best matches its FIRING
# pattern, not its semantic topic. A "voice" rule fires on every draft → goes
# to the cache-friendly prefix. A "decision" rule fires once per session → goes
# to a tool-call file. Two rules that look similar in topic can land in
# different files if they fire at different rates.

# Voice rules: high-fire, low-entropy. Tone, formatting, openers/closers,
# canonical phrases. Cheapest at every-call-cache.
_VOICE_CATEGORIES = frozenset(
    {
        "DRAFTING",
        "FORMAT",
        "FORMATTING",
        "CONTENT",
        "EMAIL",
        "VOICE",
        "STYLE",
        "TONE",
    }
)

# Decision rules: sparse, high-leverage. Pricing rubrics, escalation triggers,
# accept/reject heuristics. Pulled on demand.
_DECISION_CATEGORIES = frozenset(
    {
        "ACCURACY",
        "FACTUAL",
        "DATA_INTEGRITY",
        "DECISION",
        "JUDGMENT",
        "ARCHITECTURE",
        "CODE",
    }
)

# Process rules: deterministic, code-not-prompt. Documented here for humans;
# enforcement happens via hooks/CI.
_PROCESS_CATEGORIES = frozenset(
    {
        "PROCESS",
        "WORKFLOW",
        "GIT",
        "CI",
    }
)

# Preferences: volatile, user-specific knobs. "Use Polestar over Poetry",
# "always pin Python 3.11", etc.
_PREFERENCE_CATEGORIES = frozenset(
    {
        "PREFERENCE",
        "TOOL",
        "ENVIRONMENT",
        "CONTEXT",
    }
)

# Relations: entity-keyed (people, accounts, projects). Looked up at mention.
_RELATION_CATEGORIES = frozenset(
    {
        "RELATION",
        "PERSON",
        "ACCOUNT",
        "CLIENT",
    }
)

# Five canonical filenames. Order matters: it's the on-disk read order.
_VOICE = "voice.md"
_DECISIONS = "decisions.md"
_PROCESS = "process.md"
_PREFERENCES = "preferences.md"
_RELATIONS = "relations.md"

_ALL_FILES = (_VOICE, _DECISIONS, _PROCESS, _PREFERENCES, _RELATIONS)


def _classify(lesson: Lesson) -> str:
    """Pick the destination file for a lesson by its activation regime.

    Falls back to ``decisions.md`` (the safest mid-entropy bucket) when the
    category doesn't match any explicit set. Never raises.
    """
    cat = (lesson.category or "").upper()
    if cat in _VOICE_CATEGORIES:
        return _VOICE
    if cat in _DECISION_CATEGORIES:
        return _DECISIONS
    if cat in _PROCESS_CATEGORIES:
        return _PROCESS
    if cat in _PREFERENCE_CATEGORIES:
        return _PREFERENCES
    if cat in _RELATION_CATEGORIES:
        return _RELATIONS
    return _DECISIONS


@dataclass(frozen=True)
class ProjectionResult:
    """Outcome of a single project() call.

    ``files_written`` lists the paths that actually changed on disk;
    unchanged files are skipped to keep mtimes stable for caching layers.
    ``digest`` is a content hash over the FULL projection (every file,
    sorted), letting callers cheaply detect "nothing changed since last
    project()" without diffing.
    """

    memories_dir: Path
    files_written: tuple[str, ...]
    files_unchanged: tuple[str, ...]
    rules_total: int
    rules_by_file: dict[str, int]
    digest: str


def _render_voice(rules: list[Lesson]) -> str:
    """Voice prefix — terse, every-call cacheable.

    No headers per rule, no metadata. Just the rule text, one per line,
    deterministically sorted. The whole point is to keep this small enough
    that the 4096-token cache write tax pays back in 5+ reads/session.
    """
    if not rules:
        return _empty_section("voice")
    lines = ["# voice — applies to every draft", ""]
    for r in sorted(rules, key=_lesson_sort_key):
        lines.append(f"- {r.description.strip()}")
    return "\n".join(lines) + "\n"


def _render_decisions(rules: list[Lesson]) -> str:
    """Decision rubrics — recalled on demand, not in default prompt."""
    if not rules:
        return _empty_section("decisions")
    lines = [
        "# decisions — recall when the task touches accuracy, judgment, or architecture",
        "",
    ]
    for r in sorted(rules, key=_lesson_sort_key):
        lines.append(f"## {r.category}: {r.description.strip()}")
        if r.root_cause:
            lines.append(f"- root cause: {r.root_cause.strip()}")
        if r.example_draft and r.example_corrected:
            lines.append("- example:")
            lines.append(f"  - draft: {_truncate(r.example_draft, 200)}")
            lines.append(f"  - corrected: {_truncate(r.example_corrected, 200)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_process(rules: list[Lesson]) -> str:
    """Process rules — typically enforced by hooks; documented here for humans."""
    if not rules:
        return _empty_section("process")
    lines = [
        "# process — enforced deterministically (hooks/CI). Documented here for humans.",
        "",
    ]
    for r in sorted(rules, key=_lesson_sort_key):
        lines.append(f"- [{r.state.value}] {r.description.strip()}")
    return "\n".join(lines) + "\n"


def _render_preferences(rules: list[Lesson]) -> str:
    """Preference knobs — volatile, recall on demand."""
    if not rules:
        return _empty_section("preferences")
    lines = ["# preferences — recall when picking tools, environments, or defaults", ""]
    for r in sorted(rules, key=_lesson_sort_key):
        lines.append(f"- {r.description.strip()}")
    return "\n".join(lines) + "\n"


def _render_relations(rules: list[Lesson]) -> str:
    """Entity-keyed rules — looked up at mention time."""
    if not rules:
        return _empty_section("relations")
    lines = ["# relations — recall when an entity is named in the draft", ""]
    for r in sorted(rules, key=_lesson_sort_key):
        lines.append(f"- {r.description.strip()}")
    return "\n".join(lines) + "\n"


_RENDERERS = {
    _VOICE: _render_voice,
    _DECISIONS: _render_decisions,
    _PROCESS: _render_process,
    _PREFERENCES: _render_preferences,
    _RELATIONS: _render_relations,
}


def _empty_section(name: str) -> str:
    """Empty file is still meaningful — Memory tool sees an empty bucket
    rather than a missing file and routes around it."""
    return f"# {name}\n\n(no rules graduated to this bucket yet)\n"


def _truncate(s: str, n: int) -> str:
    s = s.strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _lesson_sort_key(l: Lesson) -> tuple:
    """Stable sort: confidence desc, then category asc, then description asc.

    Determinism matters more than aesthetics. Two callers projecting the
    same brain at the same instant must produce byte-identical output —
    that's how prompt caching and the integrity audit both stay honest.
    """
    return (-round(l.confidence, 4), l.category or "", l.description or "")


def project(
    brain: "Brain",
    *,
    output_dir: Path | None = None,
    include_states: Iterable[LessonState] = ELIGIBLE_STATES,
    dry_run: bool = False,
) -> ProjectionResult:
    """Project the brain's eligible lessons to a file tree under ``memories/``.

    Parameters
    ----------
    brain:
        The :class:`gradata.brain.Brain` to project. Lessons are read via the
        existing ``brain._load_lessons()`` accessor — no schema coupling.
    output_dir:
        Defaults to ``<brain_dir>/memories/``. Override for tests or for the
        rentable-brain SKU's per-user namespacing.
    include_states:
        Lesson states that survive the filter. Defaults to PATTERN+RULE
        (the same ELIGIBLE_STATES used by injection today). Tests can pass
        broader sets.
    dry_run:
        When True, render files in memory but do not touch disk. Returned
        ``files_written``/``files_unchanged`` reflect what *would* have
        been written.

    Returns
    -------
    ProjectionResult — dirs/paths written, counts, content digest.
    """
    out = output_dir or (brain.dir / "memories")
    out.mkdir(parents=True, exist_ok=True)

    eligible_states = frozenset(include_states)
    lessons = [l for l in brain._load_lessons() if l.state in eligible_states]

    buckets: dict[str, list[Lesson]] = {name: [] for name in _ALL_FILES}
    for l in lessons:
        buckets[_classify(l)].append(l)

    files_written: list[str] = []
    files_unchanged: list[str] = []
    digest = hashlib.sha256()
    counts: dict[str, int] = {}

    for name in _ALL_FILES:
        rendered = _RENDERERS[name](buckets[name])
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(rendered.encode("utf-8"))
        digest.update(b"\xff")
        counts[name] = len(buckets[name])

        target = out / name
        existing = target.read_text(encoding="utf-8") if target.exists() else None
        if existing == rendered:
            files_unchanged.append(name)
            continue

        if not dry_run:
            # Atomic-ish: write to .tmp then replace. Avoids torn reads from
            # a Memory tool polling concurrently.
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_text(rendered, encoding="utf-8")
            tmp.replace(target)
        files_written.append(name)

    _log.info(
        "projector: wrote %d/%d files (digest=%s)",
        len(files_written),
        len(_ALL_FILES),
        digest.hexdigest()[:12],
    )
    return ProjectionResult(
        memories_dir=out,
        files_written=tuple(files_written),
        files_unchanged=tuple(files_unchanged),
        rules_total=len(lessons),
        rules_by_file=counts,
        digest=digest.hexdigest(),
    )


__all__ = ["ProjectionResult", "project"]
