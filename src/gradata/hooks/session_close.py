"""Stop hook: emit SESSION_END event and run graduation sweep."""
from __future__ import annotations
from gradata.hooks._base import run_hook, resolve_brain_dir
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "Stop",
    "profile": Profile.MINIMAL,
    "timeout": 15000,
}


def _emit_session_end(brain_dir: str) -> None:
    try:
        from gradata._events import emit
        from gradata._paths import BrainContext
        ctx = BrainContext.from_brain_dir(brain_dir)
        emit("SESSION_END", source="hook:session_close", data={}, ctx=ctx)
    except Exception:
        pass


def _run_graduation(brain_dir: str) -> None:
    try:
        from pathlib import Path
        from gradata.enhancements.self_improvement import parse_lessons, graduate, format_lessons
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


def _review_rule_failures(brain_dir: str) -> None:
    """Background review fork: check for RULE_FAILURE events and apply patches."""
    try:
        from gradata.brain import Brain

        brain = Brain(brain_dir)
        failures = brain.query_events(event_type="RULE_FAILURE", last_n_sessions=1, limit=50)
        if not failures:
            return

        from gradata.enhancements.self_healing import review_rule_failures
        patches = review_rule_failures(failures)

        for patch in patches:
            if not patch.get("retroactive_test", {}).get("passes"):
                continue
            brain.patch_rule(
                category=patch["category"],
                old_description=patch["original_description"],
                new_description=patch["proposed_description"],
                reason=f"Self-healing: {patch['retroactive_test'].get('reason', 'passed retroactive test')}",
            )
    except Exception:
        pass


def main(data: dict) -> dict | None:
    brain_dir = resolve_brain_dir()
    if not brain_dir:
        return None

    _emit_session_end(brain_dir)
    _run_graduation(brain_dir)
    _review_rule_failures(brain_dir)
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
