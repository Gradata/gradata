"""PreCompact hook: save brain state snapshot before context compaction."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from gradata.hooks._base import run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "PreCompact",
    "matcher": "manual|auto",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}


def _resolve_brain_dir() -> Path | None:
    brain_dir = os.environ.get("GRADATA_BRAIN_DIR") or os.environ.get("BRAIN_DIR")
    if brain_dir:
        p = Path(brain_dir)
        return p if p.exists() else None
    default = Path.home() / ".gradata" / "brain"
    return default if default.exists() else None


def _get_session_number(brain_dir: Path) -> int | None:
    loop_state = brain_dir / "loop-state.md"
    if not loop_state.is_file():
        return None
    try:
        text = loop_state.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "session" in line.lower():
                # Extract number from lines like "Session: 97" or "## Session 97"
                import re
                nums = re.findall(r"\d+", line)
                if nums:
                    return int(nums[-1])
    except Exception:
        pass
    return None


def main(data: dict) -> dict | None:
    try:
        brain_dir = _resolve_brain_dir()
        if not brain_dir:
            return None

        session = _get_session_number(brain_dir)
        compact_type = data.get("type", "unknown") if data else "unknown"

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session": session,
            "compact_type": compact_type,
            "brain_dir": str(brain_dir),
        }

        # Include lesson count if available
        lessons_path = brain_dir / "lessons.md"
        if lessons_path.is_file():
            text = lessons_path.read_text(encoding="utf-8")
            snapshot["lesson_count"] = len([
                l for l in text.splitlines() if l.strip() and not l.startswith("#")
            ])

        snapshot_path = Path(tempfile.gettempdir()) / "gradata-compact-snapshot.json"
        snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

        return {"result": "State saved before compaction"}
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
