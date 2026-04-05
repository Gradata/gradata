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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

__all__ = [
    "backfill_from_git",
    "scan_git_diffs",
    "BackfillStats",
]


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

    # Get commit hashes
    if not repo_path.exists():
        return []

    try:
        result = subprocess.run(
            ["git", "log", f"--since={since_date}", "--format=%H", f"-{max_commits}"],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace",
            cwd=str(repo_path),
        )
        if result.returncode != 0:
            _log.warning("git log failed: %s", result.stderr)
            return []
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        _log.warning("git not available: %s", e)
        return []

    commits = [h.strip() for h in result.stdout.strip().splitlines() if h.strip()]
    if not commits:
        return []

    diffs: list[dict[str, Any]] = []
    patterns = file_patterns or ["*.py", "*.md", "*.ts", "*.js", "*.txt"]

    for commit_hash in commits:
        try:
            # Get files changed in this commit
            files_result = subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", commit_hash],
                capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace",
                cwd=str(repo_path),
            )
            if files_result.returncode != 0:
                continue

            changed_files = files_result.stdout.strip().splitlines()

            # Filter by patterns
            filtered_files = []
            for f in changed_files:
                f = f.strip()
                if any(Path(f).match(p) for p in patterns):
                    filtered_files.append(f)

            # Get date
            date_result = subprocess.run(
                ["git", "log", "-1", "--format=%aI", commit_hash],
                capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace",
                cwd=str(repo_path),
            )
            commit_date = date_result.stdout.strip() if date_result.returncode == 0 else ""

            for file_path in filtered_files[:10]:  # Cap files per commit
                try:
                    # Get old version (parent)
                    old_result = subprocess.run(
                        ["git", "show", f"{commit_hash}~1:{file_path}"],
                        capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace",
                        cwd=str(repo_path),
                    )
                    old_content = old_result.stdout if old_result.returncode == 0 else ""

                    # Get new version
                    new_result = subprocess.run(
                        ["git", "show", f"{commit_hash}:{file_path}"],
                        capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace",
                        cwd=str(repo_path),
                    )
                    new_content = new_result.stdout if new_result.returncode == 0 else ""

                    # Skip if no meaningful diff
                    if not old_content or not new_content:
                        continue
                    if old_content == new_content:
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

                except (subprocess.TimeoutExpired, Exception):
                    continue

        except (subprocess.TimeoutExpired, Exception):
            continue

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
