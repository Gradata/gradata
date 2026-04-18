"""PreCompact hook: save brain state snapshot before context compaction."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ._base import resolve_brain_dir, run_hook
from ._profiles import Profile

HOOK_META = {
    "event": "PreCompact",
    "matcher": "manual|auto",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}


def _get_session_number(brain_dir: Path) -> int | None:
    loop_state = brain_dir / "loop-state.md"
    if not loop_state.is_file():
        return None
    try:
        text = loop_state.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "session" in line.lower():
                # Extract number from lines like "Session: 97" or "## Session 97"
                nums = re.findall(r"\d+", line)
                if nums:
                    return int(nums[0])
    except Exception:
        pass
    return None


def main(data: dict) -> dict | None:
    try:
        brain_dir_str = resolve_brain_dir()
        if not brain_dir_str:
            return None
        brain_dir = Path(brain_dir_str)

        session = _get_session_number(brain_dir)
        compact_type = data.get("type", "unknown") if data else "unknown"

        snapshot = {
            "timestamp": datetime.now(UTC).isoformat(),
            "session": session,
            "compact_type": compact_type,
            "brain_dir": str(brain_dir),
        }

        # Include lesson count if available
        lessons_path = brain_dir / "lessons.md"
        if lessons_path.is_file():
            text = lessons_path.read_text(encoding="utf-8")
            snapshot["lesson_count"] = len([
                line for line in text.splitlines() if line.strip() and not line.startswith("#")
            ])

        if hasattr(os, "getuid"):
            uid = os.getuid()
        else:
            try:
                uid = os.getlogin()
            except OSError:
                uid = f"pid{os.getpid()}"
        user_tmp = Path(tempfile.gettempdir()) / f"gradata-{uid}"
        user_tmp.mkdir(parents=True, exist_ok=True)
        dir_hash = hashlib.md5(str(brain_dir).encode()).hexdigest()[:8]
        snapshot_path = user_tmp / f"compact-snapshot-{dir_hash}.json"
        snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

        return {"result": "State saved before compaction"}
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
