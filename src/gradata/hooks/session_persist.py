"""Stop hook: persist session handoff data for cross-session continuity."""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from ._base import resolve_brain_dir, run_hook
from ._profiles import Profile

HOOK_META = {
    "event": "Stop",
    "profile": Profile.STRICT,
    "timeout": 10000,
}


def _get_session_number(brain_dir: Path) -> int | None:
    loop_state = brain_dir / "loop-state.md"
    if not loop_state.is_file():
        return None
    try:
        text = loop_state.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "session" in line.lower():
                nums = re.findall(r"\d+", line)
                if nums:
                    return int(nums[0])
    except Exception:
        pass
    return None


def _get_modified_files() -> list[str]:
    """Get files modified + untracked in current session via git."""
    cwd = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    files = []

    # Staged and unstaged changes
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=cwd, check=False,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            files.extend(f.strip() for f in result.stdout.splitlines() if f.strip())
    except Exception:
        pass

    # Untracked files (not ignored)
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, timeout=5, cwd=cwd, check=False,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            files.extend(f.strip() for f in result.stdout.splitlines() if f.strip())
    except Exception:
        pass

    # Deduplicate while preserving order
    return list(dict.fromkeys(files))


def main(data: dict) -> dict | None:
    try:
        brain_dir_str = resolve_brain_dir()
        if not brain_dir_str:
            return None
        brain_dir = Path(brain_dir_str)

        persist_dir = brain_dir / "sessions" / "persist"
        persist_dir.mkdir(parents=True, exist_ok=True)

        session = _get_session_number(brain_dir)
        modified = _get_modified_files()

        handoff = {
            "timestamp": datetime.now(UTC).isoformat(),
            "session": session,
            "modified_files": modified[:50],
            "file_count": len(modified),
        }

        filename = f"session-{session}.json" if session else "session-unknown.json"
        out_path = persist_dir / filename
        out_path.write_text(json.dumps(handoff, indent=2), encoding="utf-8")
    except Exception:
        pass
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
