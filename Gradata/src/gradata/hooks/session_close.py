"""Stop hook: gated graduation/pipeline/tree sweep.

Fires on every Stop (end of every turn) because Claude Code has no
"real" session-end signal. Running the full waterfall on every turn is
expensive and pollutes the brain with redundant SESSION_END rows, so
this hook gates the heavy work on "was there a new correction/edit
since last run?". If not, it only flushes the retain queue (cheap) and
returns.

Gating model:
    <brain>/.last_close_ts    ISO timestamp of the last heavy-work run.
                              Created on first trigger; updated only when
                              work actually fires.

Trigger event types (any new row since last_close_ts fires the waterfall):
    CORRECTION, LESSON_CHANGE, RULE_FAILURE, IMPLICIT_FEEDBACK,
    OUTPUT_ACCEPTED, AGENT_OUTCOME, RULE_PATCHED

On first run (no stamp file) we wait until any trigger row exists and
then run the waterfall against the full event history; the stamp file
is written only after a successful pass.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "Stop",
    "profile": Profile.MINIMAL,
    "timeout": 15000,
}

STAMP_FILE = ".last_close_ts"

TRIGGER_TYPES = (
    "CORRECTION",
    "LESSON_CHANGE",
    "RULE_FAILURE",
    "IMPLICIT_FEEDBACK",
    "OUTPUT_ACCEPTED",
    "AGENT_OUTCOME",
    "RULE_PATCHED",
)


def _read_stamp(brain_dir: Path) -> str | None:
    p = brain_dir / STAMP_FILE
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _write_stamp(brain_dir: Path, ts: str) -> None:
    with contextlib.suppress(OSError):
        (brain_dir / STAMP_FILE).write_text(ts, encoding="utf-8")


def _has_new_triggers(brain_dir: Path, since: str | None, until: str) -> bool:
    """True iff any TRIGGER_TYPES event rows exist in ``(since, until]``.

    Bounding the query on ``until`` prevents the later stamp write from
    falsely marking rows that arrive mid-waterfall as processed.
    """
    db = brain_dir / "system.db"
    if not db.is_file():
        return False
    placeholders = ",".join("?" * len(TRIGGER_TYPES))
    sql = f"SELECT 1 FROM events WHERE type IN ({placeholders}) AND ts <= ?"
    params: tuple = (*TRIGGER_TYPES, until)
    if since:
        sql += " AND ts > ?"
        params = (*params, since)
    sql += " LIMIT 1"
    try:
        with sqlite3.connect(db) as conn:
            row = conn.execute(sql, params).fetchone()
        return row is not None
    except sqlite3.Error as e:
        _log.debug("trigger check failed: %s", e)
        return False


def _run_graduation(brain_dir: str) -> None:
    try:
        from gradata.enhancements.self_improvement import format_lessons, graduate, parse_lessons

        lessons_path = Path(brain_dir) / "lessons.md"
        if not lessons_path.is_file():
            return
        text = lessons_path.read_text(encoding="utf-8")
        lessons = parse_lessons(text)
        if not lessons:
            return
        active, _ = graduate(lessons)
        lessons_path.write_text(format_lessons(active), encoding="utf-8")
    except Exception as e:
        _log.debug("graduation skipped: %s", e)


def _run_tree_consolidation(brain_dir: str) -> None:
    try:
        from gradata.enhancements.self_improvement import format_lessons, parse_lessons
        from gradata.rules.rule_tree import RuleTree

        lessons_path = Path(brain_dir) / "lessons.md"
        if not lessons_path.is_file():
            return
        text = lessons_path.read_text(encoding="utf-8")
        lessons = parse_lessons(text)
        if not lessons:
            return

        if not any(l.path for l in lessons):
            return

        tree = RuleTree(lessons)
        session_fires: dict[str, list] = {}
        for lesson in lessons:
            if lesson.path and lesson.fire_count > 0:
                session_fires.setdefault(lesson.path, []).append(lesson)

        if not session_fires:
            return

        current_session = max(l.fire_count + l.sessions_since_fire for l in lessons)
        results = tree.consolidate(session_fires, current_session=current_session)

        if results["climbed"] > 0 or results["contracted"] > 0:
            lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    except Exception as e:
        _log.debug("tree consolidation skipped: %s", e)


def _run_pipeline(brain_dir: str, data: dict) -> None:
    try:
        from gradata.enhancements.rule_pipeline import run_rule_pipeline

        lessons_path = Path(brain_dir) / "lessons.md"
        db_path = Path(brain_dir) / "system.db"
        if not lessons_path.is_file():
            return
        current_session = int(data.get("session_number") or 0)
        result = run_rule_pipeline(
            lessons_path=lessons_path,
            db_path=db_path,
            current_session=current_session,
        )
        if result.graduated or result.meta_rules_created or result.hooks_promoted:
            _log.info(
                "Pipeline: %d graduated, %d meta-rules, %d hooks",
                len(result.graduated),
                len(result.meta_rules_created),
                len(result.hooks_promoted),
            )
    except Exception as e:
        _log.debug("pipeline skipped: %s", e)


def _refresh_brain_prompt(brain_dir: str, data: dict) -> None:
    """Regenerate brain_prompt.md after graduation mutated lessons.md.

    Synthesizes a fresh <brain-wisdom> block via Opus on every close that
    fired the pipeline (gated by the _has_new_triggers check in main()).
    Failures log at debug level — injection falls back to fragmented format
    if the file is stale or missing, so a failed refresh never breaks a
    session start.
    """
    try:
        from gradata.enhancements.rule_synthesizer import synthesize_rules_block
        from gradata.enhancements.self_improvement._confidence import parse_lessons

        bd = Path(brain_dir)
        lessons_path = bd / "lessons.md"
        if not lessons_path.is_file():
            return
        lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
        filtered = [
            l
            for l in lessons
            if l.state.name in ("RULE", "PATTERN") and (l.confidence or 0.0) >= 0.60
        ]
        if not filtered:
            return
        mandatory_lines = [
            f"[MANDATORY] {l.category}: {l.description}"
            for l in filtered
            if l.state.name == "RULE"
            and (l.confidence or 0.0) >= 0.90
            and int(getattr(l, "fire_count", 0) or 0) >= 10
        ]
        individual_lines = [
            f"[{l.state.name}:{float(l.confidence or 0.0):.2f} fires:{int(getattr(l, 'fire_count', 0) or 0)}] "
            f"{(l.category or 'GENERAL').strip()}: {(l.description or '').strip()}"
            for l in filtered
        ]
        block = synthesize_rules_block(
            brain_dir=bd,
            mandatory_lines=mandatory_lines,
            cluster_lines=[],
            individual_lines=individual_lines,
            meta_block="",
            disposition_block="",
            task_type="general",
            context="general",
        )
        if not block:
            return
        content = block
        if content.startswith("<brain-wisdom>"):
            content = content[len("<brain-wisdom>") :].lstrip("\n")
        if content.endswith("</brain-wisdom>"):
            content = content[: -len("</brain-wisdom>")].rstrip("\n")
        header = (
            "<!-- AUTO-GENERATED by session_close._refresh_brain_prompt -->\n"
            "<!-- Source of truth: lessons.md. Do not edit directly; next -->\n"
            "<!-- graduation-triggering session will regenerate this file. -->\n\n"
        )
        (bd / "brain_prompt.md").write_text(header + content + "\n", encoding="utf-8")
        _log.info("brain_prompt.md refreshed (%d chars)", len(content))
    except Exception as e:
        _log.debug("brain_prompt refresh skipped: %s", e)


def _flush_retain_queue(brain_dir: str) -> None:
    """Always runs — cheap + essential so no queued events are lost."""
    try:
        from gradata._events import flush_retain

        result = flush_retain(brain_dir)
        if result.get("written"):
            _log.info("RetainOrchestrator: flushed %d events", result["written"])
    except Exception as e:
        _log.debug("retain flush skipped: %s", e)


def main(data: dict) -> dict | None:
    brain_dir_str = resolve_brain_dir()
    if not brain_dir_str:
        return None

    brain_dir = Path(brain_dir_str)

    # Always flush: cheap and never idempotent from a data-loss standpoint.
    _flush_retain_queue(brain_dir_str)

    # Gate the heavy waterfall on "did anything interesting happen?"
    last_ts = _read_stamp(brain_dir)
    upper_bound = datetime.now(UTC).isoformat()
    if not _has_new_triggers(brain_dir, last_ts, upper_bound):
        return None

    _run_graduation(brain_dir_str)
    _run_pipeline(brain_dir_str, data)
    _run_tree_consolidation(brain_dir_str)
    _refresh_brain_prompt(brain_dir_str, data)

    _write_stamp(brain_dir, upper_bound)
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
