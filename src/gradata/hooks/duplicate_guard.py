"""PreToolUse hook: block file creation when a similar file already exists."""
from __future__ import annotations

import logging
import os
import re
from difflib import SequenceMatcher
from pathlib import Path

from gradata.hooks._base import run_hook
from gradata.hooks._profiles import Profile

_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "PreToolUse",
    "matcher": "Write",
    "profile": Profile.STRICT,
    "timeout": 3000,
    "blocking": True,
}

WATCHED_DIRS = ["src/gradata/", "sdk/", ".claude/hooks/", "brain/scripts/"]
SIMILARITY_THRESHOLD = 0.55


def _normalize(name: str) -> str:
    """Normalize filename for comparison: lowercase, strip numbers/separators."""
    name = Path(name).stem.lower()
    name = re.sub(r"[_\-.\s]+", "", name)
    name = re.sub(r"\d+", "", name)
    return name


def _similarity(a: str, b: str) -> float:
    na, nb = _normalize(a), _normalize(b)
    if na == nb:
        return 1.0
    # Length short-circuit: reject if length difference alone exceeds threshold
    max_len = max(len(na), len(nb))
    if max_len == 0:
        return 1.0
    if abs(len(na) - len(nb)) / max_len > 0.45:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _find_similar(target_path: str, project_root: str) -> list[tuple[str, float]]:
    if not _normalize(target_path):
        return []

    similar = []
    root = Path(project_root)

    for watched in WATCHED_DIRS:
        watched_dir = root / watched
        if not watched_dir.exists():
            continue
        try:
            for f in watched_dir.rglob("*.py"):
                if f.name.startswith("__"):
                    continue
                sim = _similarity(target_path, f.name)
                if sim > SIMILARITY_THRESHOLD:
                    rel = str(f.relative_to(root))
                    similar.append((rel, sim))
        except Exception as exc:
            _log.debug("Error scanning %s: %s", watched, exc)
            continue

    similar.sort(key=lambda x: x[1], reverse=True)
    return similar[:5]


def _in_watched_dir(file_path: str) -> bool:
    path_normalized = file_path.replace("\\", "/")
    return any(d in path_normalized for d in WATCHED_DIRS)


def main(data: dict) -> dict | None:
    try:
        tool_input = data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return None

        # Resolve to absolute path to prevent relative path bypass
        file_path = str(Path(file_path).resolve())

        # Only guard new files in watched directories
        if not _in_watched_dir(file_path):
            return None

        if Path(file_path).exists():
            return None  # File already exists, this is an overwrite

        # Find project root
        project_root = os.environ.get("CLAUDE_PROJECT_DIR", "")
        if project_root:
            project_root = str(Path(project_root).resolve())
        else:
            # Walk up from file path to find .git
            p = Path(file_path).parent
            while p != p.parent:
                if (p / ".git").exists():
                    project_root = str(p)
                    break
                p = p.parent
        if not project_root:
            return None

        similar = _find_similar(file_path, project_root)
        if not similar:
            return None

        names = ", ".join(f"{name} ({sim:.0%})" for name, sim in similar[:3])
        return {
            "decision": "block",
            "reason": (
                f"BLOCKED: You're creating \"{Path(file_path).name}\" but similar file(s) "
                f"already exist: {names}. Read the existing file first. "
                f"If it does what you need, edit it instead."
            ),
        }
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
