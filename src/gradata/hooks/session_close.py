"""Stop hook: emit SESSION_END event and run graduation sweep."""

from __future__ import annotations

from ._base import resolve_brain_dir, run_hook
from ._profiles import Profile

HOOK_META = {
    "event": "Stop",
    "profile": Profile.MINIMAL,
    "timeout": 15000,
}


def _emit_session_end(brain_dir: str) -> None:
    try:
        from .._events import emit
        from .._paths import BrainContext

        ctx = BrainContext.from_brain_dir(brain_dir)
        emit("SESSION_END", source="hook:session_close", data={}, ctx=ctx)
    except Exception:
        pass


def _run_graduation(brain_dir: str) -> None:
    try:
        from pathlib import Path

        from ..enhancements.self_improvement import format_lessons, graduate, parse_lessons

        lessons_path = Path(brain_dir) / "lessons.md"
        if not lessons_path.is_file():
            return
        text = lessons_path.read_text(encoding="utf-8")
        lessons = parse_lessons(text)
        if not lessons:
            return
        active, _graduated = graduate(lessons)
        lessons_path.write_text(format_lessons(active), encoding="utf-8")
    except Exception:
        pass


def _run_tree_consolidation(brain_dir: str) -> None:
    """Post-session tree consolidation: evaluate climbs and contractions."""
    try:
        from pathlib import Path

        from ..enhancements.self_improvement import format_lessons, parse_lessons
        from ..rules.rule_tree import RuleTree

        lessons_path = Path(brain_dir) / "lessons.md"
        if not lessons_path.is_file():
            return
        text = lessons_path.read_text(encoding="utf-8")
        lessons = parse_lessons(text)
        if not lessons:
            return

        # Skip if no lessons have paths (tree not active)
        has_paths = any(l.path for l in lessons)
        if not has_paths:
            return

        tree = RuleTree(lessons)

        # Build session_fires from lessons with paths (use fire_count as proxy)
        # In a full implementation, this would query events for RULE_FIRED events.
        # For now, treat all path-bearing lessons as "fired at their path".
        session_fires: dict[str, list] = {}
        for lesson in lessons:
            if lesson.path and lesson.fire_count > 0:
                session_fires.setdefault(lesson.path, []).append(lesson)

        if not session_fires:
            return

        # Get current session number (approximate from lessons count)
        current_session = max(l.fire_count + l.sessions_since_fire for l in lessons)

        results = tree.consolidate(session_fires, current_session=current_session)

        # Save updated lessons if any changes occurred
        if results["climbed"] > 0 or results["contracted"] > 0:
            lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    except Exception:
        pass


def _flush_retain_queue(brain_dir: str) -> None:
    """Flush any events queued via the RetainOrchestrator batch path.

    Most emits go through the synchronous (dedup-safe) ``emit()``; callers
    that chose the batch path leave events in ``_pending`` until a flush
    point. Session close is the last-chance flush so no queued events are
    lost if the process is torn down immediately after.
    """
    try:
        from .._events import flush_retain
        result = flush_retain(brain_dir)
        if result.get("written"):
            import logging
            logging.getLogger(__name__).info(
                "RetainOrchestrator: flushed %d events at session close",
                result["written"],
            )
    except Exception:
        pass


def main(data: dict) -> dict | None:
    brain_dir = resolve_brain_dir()
    if not brain_dir:
        return None

    _emit_session_end(brain_dir)
    _run_graduation(brain_dir)
    try:
        from pathlib import Path

        from ..enhancements.rule_pipeline import run_rule_pipeline
        _rp_lp = Path(brain_dir) / "lessons.md"
        if _rp_lp.is_file():
            _rp_result = run_rule_pipeline(
                lessons_path=_rp_lp,
                db_path=Path(brain_dir) / "system.db",
                current_session=int(data.get("session_number") or 0),
            )
            if _rp_result.graduated or _rp_result.meta_rules_created or _rp_result.hooks_promoted:
                import logging
                logging.getLogger(__name__).info(
                    "Pipeline: %d graduated, %d meta-rules, %d hooks",
                    len(_rp_result.graduated), len(_rp_result.meta_rules_created),
                    len(_rp_result.hooks_promoted),
                )
    except Exception:
        pass
    _run_tree_consolidation(brain_dir)
    _flush_retain_queue(brain_dir)
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
