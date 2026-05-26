"""Claude Code PreCompact hook: snapshot brain context before compaction."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gradata._atomic import atomic_write_text
from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "PreCompact",
    "matcher": "manual|auto",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}

SNAPSHOT_DIR_NAME = ".precompact-snapshots"
MAX_FILE_CHARS = 200_000
_CONTEXT_FILES = (
    "lessons.md",
    "rules.md",
    "meta-rules.json",
    "brain.manifest.json",
    "handoff.md",
    "handoff.json",
)
_SAFE_SESSION_ID = re.compile(r"[^A-Za-z0-9_.-]+")


def _session_id(payload: dict[str, Any]) -> str:
    raw: Any = payload.get("session_id") or payload.get("sessionId")
    session = payload.get("session")
    if not raw and isinstance(session, dict):
        raw = session.get("id")
    if not isinstance(raw, str) or not raw.strip():
        raw = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]
    safe = _SAFE_SESSION_ID.sub("-", raw.strip()).strip(".-")
    return safe or "unknown-session"


def _read_context_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    truncated = len(text) > MAX_FILE_CHARS
    if truncated:
        text = text[:MAX_FILE_CHARS]
    return {
        "path": path.name,
        "chars": path.stat().st_size,
        "truncated": truncated,
        "content": text,
    }


def _brain_context(brain_dir: Path) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    context: dict[str, Any] = {"files": files}
    for rel in _CONTEXT_FILES:
        item = _read_context_file(brain_dir / rel)
        if item is not None:
            files[rel] = item
            context[rel.replace(".", "_").replace("-", "_")] = item["content"]
    return context


def write_snapshot(payload: dict[str, Any], brain_dir: Path) -> Path:
    """Write a PreCompact snapshot and return its path."""
    session_id = _session_id(payload)
    snapshot_dir = brain_dir / SNAPSHOT_DIR_NAME
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{session_id}.json"

    snapshot = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "hook_event_name": "PreCompact",
        "session_id": session_id,
        "compact_type": payload.get("type") or payload.get("compact_type") or payload.get("trigger"),
        "trigger": payload.get("trigger") or payload.get("type") or payload.get("compact_type"),
        "brain_dir": str(brain_dir),
        "payload": payload,
        "context": _brain_context(brain_dir),
    }
    atomic_write_text(snapshot_path, json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    return snapshot_path


def main(data: dict) -> dict | None:
    brain_dir_str = resolve_brain_dir()
    if not brain_dir_str:
        return None
    try:
        path = write_snapshot(data or {}, Path(brain_dir_str))
    except Exception:
        return None
    return {"result": f"PreCompact snapshot saved to {path}"}


if __name__ == "__main__":
    run_hook(main, HOOK_META)
