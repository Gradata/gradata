"""
Git Backfill — Bootstrap a brain from git history.
====================================================
Walks git log, extracts diffs, classifies corrections, and bootstraps
a brain with historical data. A new brain can start with months of
learning from day one.

Usage::

    from gradata.enhancements.git_backfill import backfill_from_git

    stats = backfill_from_git(
        brain=brain,
        repo_path=".",
        lookback_days=90,
        file_patterns=["*.py", "*.md", "*.ts"],
    )
    print(stats)  # {"commits_scanned": 150, "corrections_captured": 43, ...}

Or via Brain method::

    brain.backfill_from_git(repo_path=".", lookback_days=90)
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

__all__ = [
    "BackfillStats",
    "backfill_from_git",
    "scan_git_diffs",
]


@dataclass
class _GitResult:
    """Result of a `_git` invocation.

    ``completed`` is set when the subprocess ran to completion (even with
    non-zero exit). ``error`` is set when the subprocess failed to launch
    or timed out — callers can surface ``type(error).__name__`` and
    ``str(error)`` in log messages to preserve root cause.
    """

    completed: subprocess.CompletedProcess | None = None
    error: Exception | None = None

    @property
    def ok(self) -> bool:
        return self.completed is not None and self.completed.returncode == 0


class BackfillStats:
    """Statistics from a git backfill operation."""

    def __init__(self) -> None:
        self.commits_scanned: int = 0
        self.files_analyzed: int = 0
        self.corrections_captured: int = 0
        self.corrections_skipped: int = 0
        self.errors: int = 0
        self.severities: dict[str, int] = {}
        self.categories: dict[str, int] = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "commits_scanned": self.commits_scanned,
            "files_analyzed": self.files_analyzed,
            "corrections_captured": self.corrections_captured,
            "corrections_skipped": self.corrections_skipped,
            "errors": self.errors,
            "severities": self.severities,
            "categories": self.categories,
        }


def scan_git_diffs(
    repo_path: str | Path = ".",
    lookback_days: int = 90,
    file_patterns: list[str] | None = None,
    max_commits: int = 500,
    max_diff_lines: int = 200,
) -> list[dict[str, Any]]:
    """Scan git history and extract before/after diffs.

    Args:
        repo_path: Path to the git repository.
        lookback_days: How far back to scan.
        file_patterns: Glob patterns to filter files (e.g. ["*.py", "*.md"]).
        max_commits: Maximum commits to process.
        max_diff_lines: Skip diffs larger than this (too noisy for learning).

    Returns:
        List of dicts with 'commit', 'file', 'old', 'new', 'date' keys.
    """
    repo_path = Path(repo_path).resolve()
    since_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    def _git(args: list[str], timeout: int = 10) -> _GitResult:
        try:
            completed = subprocess.run(
                ["git", *args],
                capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace", cwd=str(repo_path),
            )
            return _GitResult(completed=completed)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            return _GitResult(error=exc)

    # Get commit hashes AND commit dates in one pass ("<hash> <iso-date>").
    # Avoids N+1 subprocesses (previously one `git log -1` per commit).
    result = _git(
        ["log", f"--since={since_date}", "--format=%H %cI", f"-{max_commits}"],
        timeout=30,
    )
    if result.completed is None:
        exc = result.error
        _log.warning(
            "git not available at %s: %s: %s",
            repo_path,
            type(exc).__name__ if exc else "UnknownError",
            exc,
        )
        return []
    if result.completed.returncode != 0:
        _log.warning(
            "git log failed at %s (rc=%d): %s",
            repo_path,
            result.completed.returncode,
            result.completed.stderr.strip(),
        )
        return []

    commit_entries: list[tuple[str, str]] = []
    for line in result.completed.stdout.strip().splitlines():
        parts = line.strip().split(" ", 1)
        if not parts or not parts[0]:
            continue
        commit_hash = parts[0]
        commit_date = parts[1] if len(parts) > 1 else ""
        commit_entries.append((commit_hash, commit_date))

    if not commit_entries:
        return []

    diffs: list[dict[str, Any]] = []
    patterns = file_patterns or ["*.py", "*.md", "*.ts", "*.js", "*.txt"]

    for commit_hash, commit_date in commit_entries:
        files_result = _git(["diff-tree", "--no-commit-id", "-r", "--name-only", commit_hash])
        if not files_result.ok:
            if files_result.error is not None:
                _log.warning(
                    "git diff-tree failed at %s for %s: %s: %s",
                    repo_path, commit_hash[:8],
                    type(files_result.error).__name__, files_result.error,
                )
            elif files_result.completed is not None:
                _log.warning(
                    "git diff-tree failed at %s for %s (rc=%d): %s",
                    repo_path, commit_hash[:8],
                    files_result.completed.returncode,
                    (files_result.completed.stderr or files_result.completed.stdout or "").strip(),
                )
            continue

        assert files_result.completed is not None
        filtered_files = [
            f.strip() for f in files_result.completed.stdout.strip().splitlines()
            if any(Path(f.strip()).match(p) for p in patterns)
        ]

        for file_path in filtered_files[:10]:  # Cap files per commit
            old_result = _git(["show", f"{commit_hash}~1:{file_path}"])
            new_result = _git(["show", f"{commit_hash}:{file_path}"])
            old_content = old_result.completed.stdout if old_result.ok and old_result.completed else ""
            new_content = new_result.completed.stdout if new_result.ok and new_result.completed else ""

            if not old_content or not new_content or old_content == new_content:
                continue

            # Skip huge diffs (too noisy)
            old_lines = old_content.count("\n")
            new_lines = new_content.count("\n")
            if abs(old_lines - new_lines) > max_diff_lines:
                continue
            if max(old_lines, new_lines) > max_diff_lines * 5:
                continue

            diffs.append({
                "commit": commit_hash[:8],
                "file": file_path,
                "old": old_content[:5000],
                "new": new_content[:5000],
                "date": commit_date,
            })

    return diffs


def backfill_from_git(
    brain: Any,
    repo_path: str | Path = ".",
    lookback_days: int = 90,
    file_patterns: list[str] | None = None,
    max_commits: int = 500,
    session_label: int = 0,
) -> BackfillStats:
    """Bootstrap a brain from git history.

    Scans git diffs and feeds them as corrections to the brain.
    Each diff becomes a brain.correct() call with the old content
    as draft and new content as final.

    Args:
        brain: A Brain instance to backfill.
        repo_path: Path to the git repository.
        lookback_days: How far back to scan.
        file_patterns: Glob patterns to filter files.
        max_commits: Maximum commits to process.
        session_label: Session number to tag backfilled events with.

    Returns:
        BackfillStats with counts and categories.
    """
    stats = BackfillStats()

    diffs = scan_git_diffs(
        repo_path=repo_path,
        lookback_days=lookback_days,
        file_patterns=file_patterns,
        max_commits=max_commits,
    )

    stats.commits_scanned = len(set(d["commit"] for d in diffs))
    stats.files_analyzed = len(diffs)

    for diff in diffs:
        try:
            event = brain.correct(
                draft=diff["old"],
                final=diff["new"],
                session=session_label if session_label > 0 else None,
            )

            data = event.get("data", {})
            severity = data.get("severity", "unknown")
            category = data.get("category", "UNKNOWN")

            # Skip trivial diffs (as-is = no real correction)
            if severity == "as-is":
                stats.corrections_skipped += 1
                continue

            stats.corrections_captured += 1
            stats.severities[severity] = stats.severities.get(severity, 0) + 1
            stats.categories[category] = stats.categories.get(category, 0) + 1

        except ValueError:
            # draft == final, empty inputs, etc.
            stats.corrections_skipped += 1
        except Exception as e:
            _log.warning("Backfill error on %s: %s", diff.get("file", "?"), e)
            stats.errors += 1

    _log.info(
        "Git backfill: %d commits, %d corrections captured, %d skipped",
        stats.commits_scanned,
        stats.corrections_captured,
        stats.corrections_skipped,
    )

    return stats
