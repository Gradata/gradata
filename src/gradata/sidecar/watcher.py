"""
File Watcher Sidecar — Wave 4: Observation Capture.
=====================================================
Detects when the user edits an AI-generated file and emits a CORRECTION
event automatically.  The correction detection problem is the highest-risk
gap in the Gradata SDK: the MCP protocol has no concept of user feedback, so
we close it here with a polling-based sidecar that requires only stdlib.

Design decisions
----------------
* Polling, not inotify/FSEvents/ReadDirectoryChanges.
  Portable across Windows, macOS, Linux without platform-specific APIs.
* SHA-256 content hash as the change signal.
  Avoids false positives from mtime jitter / editor temp files.
* 30-second dedup window.
  Editor auto-save (VSCode, Vim :set autowriteall) fires every few seconds;
  we collapse those saves into a single CORRECTION event.
* Graceful brain integration.
  Tries Brain.emit() first, falls back to _events.emit(), falls back to
  writing a plain JSON file so no correction is ever silently dropped.

Architecture note (SDK layer boundary)
---------------------------------------
This module lives in the brain/ SDK layer.  It is host-agnostic: it does
NOT import CLAUDE.md, hooks, or anything runtime-specific.  All I/O is
through the event system (gradata._events) or the Brain class.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEVERITY_AS_IS = "as-is"        # edit_distance < 0.02
_SEVERITY_MINOR = "minor"        # 0.02 <= edit_distance < 0.10
_SEVERITY_MODERATE = "moderate"  # 0.10 <= edit_distance < 0.40
_SEVERITY_MAJOR = "major"        # 0.40 <= edit_distance < 0.80
_SEVERITY_DISCARDED = "discarded"  # edit_distance >= 0.80

_SOURCE = "sidecar:watcher"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class WatchedFile:
    """Represents an AI-generated file that is being tracked for edits.

    Attributes:
        path: Absolute path to the file on disk.
        original_content: The exact text the AI wrote (used for diff).
        original_hash: SHA-256 hex digest of original_content.
        timestamp: Unix epoch float when the AI wrote the file.
        output_type: Optional label (e.g. ``"email"``, ``"code"``).
    """

    path: str
    original_content: str
    original_hash: str
    timestamp: float
    output_type: str = ""


@dataclass
class FileChange:
    """Represents a detected user edit to a tracked file.

    Attributes:
        path: Absolute path that was edited.
        old_content: The AI-generated version.
        new_content: The version the user saved.
        edit_distance: Normalised Levenshtein ratio in ``[0.0, 1.0]``;
            ``0.0`` = identical, ``1.0`` = completely different.
        severity: One of ``"minor"``, ``"moderate"``, ``"major"``.
        timestamp: Unix epoch float when the change was detected.
    """

    path: str
    old_content: str
    new_content: str
    edit_distance: float
    severity: str
    timestamp: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(text: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8 encoded string."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------


class FileWatcher:
    """Polling-based sidecar that detects user edits to AI-generated files.

    Call :meth:`track` immediately after the AI writes a file.  Then either
    call :meth:`check_all` periodically from your own loop, or call
    :meth:`poll` to start a blocking loop.

    Thread safety: this class is NOT thread-safe.  Use a single instance
    per thread, or protect access with a lock.

    Args:
        watch_dir: Root directory to scope tracked files under.  Files
            outside this directory can still be tracked; this parameter is
            used for logging and future glob-based scanning.
        brain_db: Optional path to a brain directory (contains
            ``system.db`` and ``events.jsonl``).  When supplied the watcher
            uses the Brain event system.  If ``None``, falls back to the
            module-level ``_events.emit()``.

    Example::

        watcher = FileWatcher("/tmp/outputs", brain_db="/path/to/brain")
        watcher.track("/tmp/outputs/email.html", ai_content, output_type="email")
        changes = watcher.check_all()
    """

    def __init__(
        self,
        watch_dir: str | Path,
        brain_db: str | Path | None = None,
    ) -> None:
        self._watch_dir = Path(watch_dir).resolve()
        self._brain_db: Path | None = Path(brain_db).resolve() if brain_db else None

        # path -> WatchedFile; keyed by str(Path.resolve())
        self._watched: dict[str, WatchedFile] = {}

        # All detected changes this session (for audit / replay)
        self._changes: list[FileChange] = []

        # Deduplication: path -> last-emitted timestamp
        self._last_emitted: dict[str, float] = {}

        # How close together saves must be to be deduplicated
        self._dedup_window: float = 30.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def track(self, path: str | Path, content: str, output_type: str = "") -> None:
        """Register a file as AI-generated.

        Call this immediately after writing AI output to disk.  Subsequent
        calls to :meth:`check` or :meth:`check_all` will compare the
        current disk content against this baseline.

        If the file is already tracked, the baseline is refreshed (useful
        when the AI re-generates a file in the same session).

        Args:
            path: Path to the file that was written.
            content: The exact content written by the AI.
            output_type: Optional label (e.g. ``"email"``, ``"code"``,
                ``"doc"``).  Stored on the CORRECTION event for downstream
                analytics.

        Raises:
            ValueError: If the resolved path is outside the watch directory.
        """
        resolved = str(Path(path).resolve())
        watch_dir_str = str(self._watch_dir.resolve())
        if not resolved.startswith(watch_dir_str):
            raise ValueError(
                f"Path {resolved} is outside watch_dir {watch_dir_str}. "
                "Refusing to track files outside the designated directory."
            )
        self._watched[resolved] = WatchedFile(
            path=resolved,
            original_content=content,
            original_hash=_sha256(content),
            timestamp=time.time(),
            output_type=output_type,
        )
        logger.debug("Tracking %s (type=%s)", resolved, output_type or "unset")

    def check(self, path: str | Path) -> FileChange | None:
        """Check whether a single tracked file has been modified.

        Compares the current on-disk hash against the tracked baseline.
        Returns ``None`` if the file is untracked, unreadable, or
        unchanged.  Does NOT call :meth:`process_change`; use
        :meth:`check_all` for the full pipeline.

        Args:
            path: Path to check.

        Returns:
            :class:`FileChange` if a modification was detected, else
            ``None``.
        """
        resolved = str(Path(path).resolve())
        watched = self._watched.get(resolved)
        if watched is None:
            return None

        try:
            current_content = Path(resolved).read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.warning("Cannot read tracked file: %s", resolved)
            return None

        current_hash = _sha256(current_content)
        if current_hash == watched.original_hash:
            return None  # no change

        # Within dedup window?
        now = time.time()
        last = self._last_emitted.get(resolved, 0.0)
        if now - last < self._dedup_window:
            logger.debug(
                "Dedup skip for %s (%.1fs since last emit)",
                resolved,
                now - last,
            )
            return None

        _ned_old = watched.original_content
        if len(_ned_old) + len(current_content) > 50_000:
            _ned_ratio = difflib.SequenceMatcher(None, _ned_old.splitlines(), current_content.splitlines()).ratio()
        else:
            _ned_ratio = difflib.SequenceMatcher(None, _ned_old, current_content).ratio()
        edit_distance = round(1.0 - _ned_ratio, 4)
        try:
            from ..enhancements.ast_severity import (
                ast_severity_enabled,
                classify_ast_severity,
                language_supported,
            )
            _as_sev = classify_ast_severity(
                watched.original_content, current_content,
            ) if ast_severity_enabled() and language_supported(path=resolved) else None
        except Exception:
            _as_sev = None
        severity = _as_sev or (
            _SEVERITY_AS_IS if edit_distance < 0.02
            else _SEVERITY_MINOR if edit_distance < 0.10
            else _SEVERITY_MODERATE if edit_distance < 0.40
            else _SEVERITY_MAJOR if edit_distance < 0.80
            else _SEVERITY_DISCARDED
        )
        return FileChange(
            path=resolved,
            old_content=watched.original_content,
            new_content=current_content,
            edit_distance=edit_distance,
            severity=severity,
            timestamp=now,
        )

    def check_all(self) -> list[FileChange]:
        """Check every tracked file for modifications.

        Calls :meth:`process_change` for each detected change so that
        CORRECTION events are emitted automatically.

        Returns:
            List of :class:`FileChange` objects detected in this sweep.
            An empty list means nothing changed (or nothing is tracked).
        """
        detected: list[FileChange] = []
        for path in list(self._watched):
            change = self.check(path)
            if change is not None:
                self.process_change(change)
                detected.append(change)
        return detected

    def process_change(self, change: FileChange) -> dict:
        """Process a detected change: emit a CORRECTION event and update state.

        Emission priority:
        1. ``brain.emit()`` if a brain directory was supplied.
        2. ``gradata._events.emit()`` (module-level, no Brain instance needed).
        3. Write a JSON sidecar file (``<original>.correction.json``) as a
           last resort so no correction is ever silently dropped.

        The watched baseline is updated to the new content so that
        subsequent edits are measured from the *latest* saved version, not
        the original AI output.  This means repeated refinements each
        produce their own CORRECTION event rather than stacking on top of
        the first.

        Args:
            change: The change to process.

        Returns:
            The emitted event dict (from the brain / events system), or a
            minimal dict if both fail.
        """
        # Mark dedup timestamp before anything async/fallible
        self._last_emitted[change.path] = change.timestamp

        # Build the event payload
        watched = self._watched.get(change.path)
        _bud_lines = list(difflib.unified_diff(
            change.old_content.splitlines(keepends=True),
            change.new_content.splitlines(keepends=True),
            fromfile=f"a/{Path(change.path).name}",
            tofile=f"b/{Path(change.path).name}",
            lineterm="",
        ))
        if len(_bud_lines) > 50:
            _bud_lines = [*_bud_lines[:50], "\n... diff truncated at 50 lines ..."]
        diff_text = "\n".join(_bud_lines)
        event_data: dict = {
            "path": change.path,
            "output_type": watched.output_type if watched else "",
            "edit_distance": change.edit_distance,
            "severity": change.severity,
            "diff": diff_text,
            "original": change.old_content[:500],    # truncated for DB storage
            "modified": change.new_content[:500],
        }
        event_tags = [
            f"severity:{change.severity}",
            "source:sidecar",
        ]
        if watched and watched.output_type:
            event_tags.append(f"output_type:{watched.output_type}")

        emitted: dict = {}
        emitted = self._try_emit_via_brain(event_data, event_tags, change)
        if not emitted:
            try:
                from .. import _events as _tem_events
                emitted = _tem_events.emit("CORRECTION", _SOURCE, event_data, event_tags) or {}
            except Exception as _tem_exc:
                logger.debug("Module-level _events.emit failed: %s", _tem_exc)
        if not emitted:
            emitted = self._emit_fallback_json(change, event_data)

        # Append to local audit list
        self._changes.append(change)

        # Refresh baseline so the next check measures from the latest version
        if watched is not None:
            self._watched[change.path] = WatchedFile(
                path=change.path,
                original_content=change.new_content,
                original_hash=_sha256(change.new_content),
                timestamp=change.timestamp,
                output_type=watched.output_type,
            )

        logger.info(
            "CORRECTION emitted — %s | severity=%s | edit_distance=%.3f",
            Path(change.path).name,
            change.severity,
            change.edit_distance,
        )
        return emitted

    def poll(self, interval: float = 2.0, max_iterations: int = 0) -> None:
        """Blocking poll loop that checks all tracked files periodically.

        Runs until interrupted (``KeyboardInterrupt``) or until
        ``max_iterations`` sweeps have completed.

        Args:
            interval: Seconds to sleep between sweeps.  Defaults to
                ``2.0``.  Values below ``0.5`` are clamped to ``0.5`` to
                avoid busy-looping.
            max_iterations: Maximum number of sweeps.  ``0`` means run
                indefinitely.

        Example::

            watcher = FileWatcher("/tmp/outputs")
            watcher.track("/tmp/outputs/draft.md", ai_text)
            watcher.poll(interval=3.0)  # blocks until Ctrl-C
        """
        interval = max(0.5, interval)
        iteration = 0
        logger.info(
            "FileWatcher polling %s every %.1fs (max_iterations=%d)",
            self._watch_dir,
            interval,
            max_iterations,
        )
        try:
            while True:
                changes = self.check_all()
                if changes:
                    logger.info(
                        "Sweep %d: detected %d change(s)", iteration + 1, len(changes)
                    )
                iteration += 1
                if max_iterations and iteration >= max_iterations:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("FileWatcher stopped after %d iteration(s).", iteration)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _try_emit_via_brain(
        self,
        data: dict,
        tags: list[str],
        change: FileChange,
    ) -> dict:
        """Attempt to emit via a Brain instance.

        Args:
            data: Event payload dict.
            tags: Event tag list.
            change: The originating change (used to call brain.correct if
                available).

        Returns:
            Event dict on success, empty dict on failure.
        """
        if self._brain_db is None:
            return {}
        try:
            from ..brain import Brain

            brain = Brain(self._brain_db)

            # If Brain exposes a .correct() helper, use it; otherwise emit
            # a raw CORRECTION event so downstream analytics work.
            if hasattr(brain, "correct"):
                return brain.correct(  # type: ignore[attr-defined]
                    change.old_content, change.new_content
                ) or {}
            return brain.emit("CORRECTION", _SOURCE, data, tags) or {}
        except Exception as exc:
            logger.debug("Brain emit failed: %s", exc)
            return {}

    def _emit_fallback_json(self, change: FileChange, data: dict) -> dict:
        """Write a ``.correction.json`` sidecar file as an absolute fallback.

        Called only when both Brain and module-level emission fail.  Writes
        a JSON file next to the changed file so the event is never silently
        lost.  The file is named
        ``<original_filename>.correction.<unix_ts>.json``.

        Args:
            change: The change being recorded.
            data: Event payload dict (written verbatim to the JSON file).

        Returns:
            A minimal event dict confirming the fallback write.
        """
        stem = Path(change.path).name
        ts_int = int(change.timestamp)
        sidecar_path = Path(change.path).parent / f"{stem}.correction.{ts_int}.json"
        payload = {
            "type": "CORRECTION",
            "source": _SOURCE,
            "ts": change.timestamp,
            "data": data,
        }
        try:
            sidecar_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.warning(
                "Fallback: CORRECTION written to %s", sidecar_path
            )
            return {"type": "CORRECTION", "source": _SOURCE, "fallback_path": str(sidecar_path)}
        except OSError as exc:
            logger.error("All emission paths failed for %s: %s", change.path, exc)
            return {}
