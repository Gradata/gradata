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
        from gradata._events import emit, EventType
        emit(EventType.SESSION_END, source="hook:session_close", data={}, brain_dir=brain_dir)
    except Exception:
        pass


def _run_graduation(brain_dir: str) -> None:
    try:
        from gradata.enhancements.self_improvement import graduation_sweep
        graduation_sweep(brain_dir=brain_dir)
    except Exception:
        pass


def main(data: dict) -> dict | None:
    brain_dir = resolve_brain_dir()
    if not brain_dir:
        return None

    _emit_session_end(brain_dir)
    _run_graduation(brain_dir)
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
