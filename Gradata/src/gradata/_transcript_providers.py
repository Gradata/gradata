"""Layer 0: TranscriptSource implementations for retroactive sweep.

Two implementations:
  ProviderTranscriptSource — reads Claude Code's native JSONL at
      ~/.claude/projects/{hash}/{session_id}.jsonl.
  GradataTranscriptSource  — reads brain/sessions/{session_id}/transcript.jsonl
      written by non-Anthropic middleware via _transcript.log_turn().

Session close tries ProviderTranscriptSource first; falls back to
GradataTranscriptSource. Both expose the same interface so the sweep
is source-agnostic.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

_log = logging.getLogger(__name__)


_VALID_SESSION_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _validate_session_id(session_id: str | None) -> bool:
    """Same path-traversal guard as gradata._transcript._validate_session_id."""
    if not session_id or not isinstance(session_id, str):
        return False
    if ".." in session_id or "/" in session_id or "\\" in session_id:
        return False
    return bool(_VALID_SESSION_RE.match(session_id))


def _safe_mtime(p: Path) -> float:
    """Return file mtime or -1 if stat fails. Used as a sort key."""
    try:
        return p.stat().st_mtime
    except OSError:
        return -1.0


class ProviderTranscriptSource:
    """Reads turns from Claude Code's native ~/.claude/projects/ JSONL.

    Claude Code writes one JSONL file per session. Entries look like:
        {"type": "user",      "message": {"content": "..."}, ...}
        {"type": "assistant", "message": {"content": [...]}, ...}

    Content can be a plain string or a list of content blocks. Non-text
    blocks (tool_use, images) are flagged as has_non_text=True and their
    content is dropped to avoid bloating the in-memory sweep.
    """

    def __init__(self, session_id: str | None) -> None:
        # Reject path-traversal session ids before they get joined into a path.
        if session_id is not None and not _validate_session_id(session_id):
            _log.debug("ProviderTranscriptSource rejecting invalid session_id")
            session_id = None
        self._session_id = session_id
        self._path: Path | None = self._locate()

    def _locate(self) -> Path | None:
        projects = Path.home() / ".claude" / "projects"
        if not projects.is_dir():
            return None
        try:
            all_dirs = [d for d in projects.iterdir() if d.is_dir()]
        except OSError:
            return None

        if self._session_id:
            for d in all_dirs:
                candidate = d / f"{self._session_id}.jsonl"
                if candidate.is_file():
                    return candidate

        # Fallback: most-recently modified JSONL across all project dirs.
        all_jsonls: list[Path] = []
        for d in all_dirs:
            try:
                all_jsonls.extend(f for f in d.iterdir() if f.suffix == ".jsonl")
            except OSError:
                continue
        return max(all_jsonls, key=_safe_mtime) if all_jsonls else None

    def available(self) -> bool:
        return self._path is not None and self._path.is_file()

    def turns(self) -> list[dict]:
        """Return normalised turns: [{role, content, has_non_text, ts}]."""
        if not self.available():
            return []
        result: list[dict] = []
        try:
            with self._path.open(encoding="utf-8", errors="replace") as fh:  # type: ignore[union-attr]
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(entry, dict):
                        continue
                    turn_type = entry.get("type", "")
                    if turn_type not in ("user", "assistant"):
                        continue
                    msg = entry.get("message") or {}
                    raw_content = msg.get("content") if isinstance(msg, dict) else None
                    ts = entry.get("timestamp", "")

                    if isinstance(raw_content, str):
                        result.append(
                            {
                                "role": turn_type,
                                "content": raw_content,
                                "has_non_text": False,
                                "ts": ts,
                            }
                        )
                    elif isinstance(raw_content, list):
                        text_parts: list[str] = []
                        has_non_text = False
                        for block in raw_content:
                            if not isinstance(block, dict):
                                continue
                            btype = block.get("type", "")
                            if btype == "text":
                                text_value = block.get("text", "")
                                if not isinstance(text_value, str):
                                    _log.debug(
                                        "skipping non-str text block: %r",
                                        type(text_value).__name__,
                                    )
                                    continue
                                text_parts.append(text_value)
                            else:
                                has_non_text = True
                        result.append(
                            {
                                "role": turn_type,
                                "content": "\n".join(text_parts) or None,
                                "has_non_text": has_non_text,
                                "ts": ts,
                            }
                        )
        except OSError as exc:
            _log.debug("ProviderTranscriptSource read failed: %s", exc)
        return result


class GradataTranscriptSource:
    """Reads turns from brain/sessions/{session_id}/transcript.jsonl.

    Written by non-Anthropic middleware via gradata._transcript.log_turn().
    """

    def __init__(self, brain_dir: str, session_id: str | None) -> None:
        self._brain_dir = brain_dir
        self._session_id = session_id

    def _path(self) -> Path | None:
        if not self._session_id:
            return None
        if not _validate_session_id(self._session_id):
            _log.debug("GradataTranscriptSource rejecting invalid session_id")
            return None
        p = Path(self._brain_dir) / "sessions" / self._session_id / "transcript.jsonl"
        return p if p.is_file() else None

    def available(self) -> bool:
        return self._path() is not None

    def turns(self) -> list[dict]:
        """Return all turns written by log_turn()."""
        path = self._path()
        if path is None:
            return []
        result: list[dict] = []
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(entry, dict):
                        result.append(entry)
        except OSError as exc:
            _log.debug("GradataTranscriptSource read failed: %s", exc)
        return result


def get_transcript_source(
    brain_dir: str, session_id: str | None
) -> ProviderTranscriptSource | GradataTranscriptSource | None:
    """Return the best available transcript source, or None if neither has data.

    Prefers ProviderTranscriptSource (Claude Code native) over
    GradataTranscriptSource (middleware-written). Returns None when neither
    has a usable file so callers can skip the sweep cleanly.
    """
    provider = ProviderTranscriptSource(session_id)
    if provider.available():
        return provider

    gradata = GradataTranscriptSource(brain_dir, session_id)
    if gradata.available():
        return gradata

    return None
