"""Claude Code PreCompact hook: snapshot bounded Gradata context before compaction."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from gradata._atomic import atomic_write_text
from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "PreCompact",
    "matcher": "manual|auto",
    "profile": Profile.MINIMAL,
    "timeout": 5000,
}
_MAX_TEXT_BYTES = 64_000
_MAX_JSON_BYTES = 128_000


def _safe_filename(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raw = f"precompact-{int(time.time() * 1000)}"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip(".-")
    if not safe:
        safe = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]
    return safe[:120]


def _session_id(data: dict[str, Any]) -> str:
    for key in ("session_id", "sessionId", "conversation_id", "conversationId"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    encoded = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8", errors="replace")).hexdigest()[:16]


def _read_bounded(path: Path, *, limit: int = _MAX_TEXT_BYTES) -> str | None:
    try:
        if not path.is_file():
            return None
        data = path.read_bytes()[:limit]
        return data.decode("utf-8", errors="replace")
    except OSError:
        return None


def _snapshot_path(brain_dir: Path, session_id: str) -> Path:
    return brain_dir / ".precompact-snapshots" / f"{_safe_filename(session_id)}.json"


def _compact_payload(data: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "hook_event_name",
        "session_id",
        "sessionId",
        "transcript_path",
        "cwd",
        "trigger",
        "custom_instructions",
        "model",
    )
    return {key: data[key] for key in keep if key in data}


def _build_snapshot(brain_dir: Path, data: dict[str, Any]) -> dict[str, Any]:
    session_id = _session_id(data)
    relevant_context: dict[str, Any] = {}

    brain_prompt = _read_bounded(brain_dir / "brain_prompt.md")
    if brain_prompt is not None:
        relevant_context["brain_prompt_md"] = brain_prompt

    last_injection = _read_bounded(brain_dir / ".last_injection.json", limit=_MAX_JSON_BYTES)
    if last_injection is not None:
        try:
            relevant_context["last_injection"] = json.loads(last_injection)
        except json.JSONDecodeError:
            relevant_context["last_injection_raw"] = last_injection

    return {
        "schema_version": 1,
        "created_at": time.time(),
        "event": "PreCompact",
        "session_id": session_id,
        "trigger": data.get("trigger"),
        "cwd": data.get("cwd"),
        "transcript_path": data.get("transcript_path"),
        "custom_instructions": data.get("custom_instructions"),
        "brain_dir": str(brain_dir),
        "payload": _compact_payload(data),
        "relevant_context": relevant_context,
        "limits": {
            "max_text_bytes": _MAX_TEXT_BYTES,
            "max_json_bytes": _MAX_JSON_BYTES,
            "transcript_content_captured": False,
        },
    }


def _write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(snapshot, indent=2, sort_keys=True) + "\n")


def main(data: dict[str, Any]) -> None:
    resolved = resolve_brain_dir()
    if not resolved:
        return None
    brain_dir = Path(resolved)
    if not brain_dir.exists():
        return None
    session_id = _session_id(data)
    _write_snapshot(_snapshot_path(brain_dir, session_id), _build_snapshot(brain_dir, data))
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
