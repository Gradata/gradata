"""Stop hook: emit SESSION_END event and run graduation sweep."""
from __future__ import annotations
import os
from pathlib import Path
from gradata.hooks._base import run_hook
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
    brain_dir = os.environ.get("GRADATA_BRAIN_DIR") or os.environ.get("BRAIN_DIR")
    if not brain_dir:
        default = Path.home() / ".gradata" / "brain"
        if default.exists():
            brain_dir = str(default)
        else:
            return None

    _emit_session_end(brain_dir)
    _run_graduation(brain_dir)
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
