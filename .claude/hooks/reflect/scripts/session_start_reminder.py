#!/usr/bin/env python3
"""Session start hook — pending learnings + system health + periodic audits.

v2.0: Absorbs gap-scanner.md startup checks and periodic-audits.md schedule.
Cross-platform compatible (Windows, macOS, Linux).
"""
import sys
import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Fix Windows encoding for emoji output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.reflect_utils import load_queue, get_cleanup_period_days

BRAIN_PATH = Path("C:/Users/olive/SpritesWork/brain")
SPRITES_WORK = Path("C:/Users/olive/OneDrive/Desktop/Sprites Work")
DB_PATH = BRAIN_PATH / "system.db"


def detect_session() -> int:
    """Detect current session number from loop-state.md."""
    import re
    loop_state = BRAIN_PATH / "loop-state.md"
    if loop_state.exists():
        text = loop_state.read_text(encoding="utf-8")
        m = re.search(r"Session\s+(\d+)", text)
        if m:
            return int(m.group(1))
    return 0


def system_health_checks() -> list:
    """Run gap-scanner startup checks. Returns list of (status, message) tuples."""
    alerts = []

    # 1. Brain vault readable with prospect files
    prospects_dir = BRAIN_PATH / "prospects"
    if not prospects_dir.exists() or not list(prospects_dir.glob("*.md")):
        alerts.append(("CRITICAL", "brain/prospects/ empty or missing"))

    # 2. system.db readable
    if not DB_PATH.exists():
        alerts.append(("CRITICAL", "system.db missing"))
    else:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("SELECT 1 FROM events LIMIT 1")
            conn.close()
        except Exception as e:
            alerts.append(("WARNING", f"system.db query failed: {e}"))

    # 3. PATTERNS.md exists and not ancient
    patterns = BRAIN_PATH / "emails" / "PATTERNS.md"
    if patterns.exists():
        age_days = (datetime.now() - datetime.fromtimestamp(patterns.stat().st_mtime)).days
        if age_days > 14:
            alerts.append(("WARNING", f"PATTERNS.md last updated {age_days} days ago"))
    else:
        alerts.append(("WARNING", "PATTERNS.md not found"))

    # 4. brain/.git active
    if not (BRAIN_PATH / ".git").exists():
        alerts.append(("CRITICAL", "brain/.git missing — version control inactive"))

    # 5. CLAUDE.md line count
    claude_md = SPRITES_WORK / "CLAUDE.md"
    if claude_md.exists():
        lines = len(claude_md.read_text(encoding="utf-8").splitlines())
        if lines > 80:
            alerts.append(("WARNING", f"CLAUDE.md at {lines} lines (target: <60, limit: 80)"))

    # 6. events.jsonl exists (v2.0 backbone)
    events_file = BRAIN_PATH / "events.jsonl"
    if not events_file.exists():
        alerts.append(("WARNING", "events.jsonl missing — run: python brain/scripts/events.py init"))

    return alerts


def check_periodic_audits(session: int) -> list:
    """Check if any periodic audits are due. Returns list of due audit names."""
    due = []
    if not DB_PATH.exists():
        return due

    try:
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(
            "SELECT audit_name, frequency, next_due_session FROM periodic_audits WHERE next_due_session <= ?",
            (session,)
        ).fetchall()
        conn.close()
        due = [{"name": r[0], "frequency": r[1], "due_at": r[2]} for r in rows]
    except Exception:
        pass  # Table may not exist yet

    return due


def check_session_persist() -> dict:
    """Read latest session-persist file for continuity."""
    persist_dir = BRAIN_PATH / "sessions" / "persist"
    if not persist_dir.exists():
        return {}

    files = sorted(persist_dir.glob("session-*.json"), reverse=True)
    if not files:
        return {}

    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    """Main entry point."""
    # Check if reminder is disabled via environment variable
    if os.environ.get("CLAUDE_REFLECT_REMINDER", "true").lower() == "false":
        return 0

    session = detect_session()
    output_parts = []

    # --- Pending Learnings (original functionality) ---
    cleanup_days = get_cleanup_period_days()
    if cleanup_days is None or cleanup_days <= 30:
        print(f"\n\u26a0\ufe0f  Claude Code deletes sessions after {cleanup_days or 30} days.")
        print(f"   claude-reflect needs session history for /reflect and /reflect-skills.")
        print(f"   Extend retention: add {{\"cleanupPeriodDays\": 99999}} to ~/.claude/settings.json")

    items = load_queue()
    if items:
        count = len(items)
        output_parts.append(f"\U0001f4da {count} pending learning(s) — run /reflect to review")

    # --- System Health (absorbed from gap-scanner.md) ---
    alerts = system_health_checks()
    critical = [a for a in alerts if a[0] == "CRITICAL"]
    warnings = [a for a in alerts if a[0] == "WARNING"]

    if critical:
        for level, msg in critical:
            output_parts.append(f"\U0001f6a8 CRITICAL: {msg}")
    if warnings:
        for level, msg in warnings:
            output_parts.append(f"\u26a0\ufe0f  {msg}")

    if not alerts:
        healthy_count = 6  # Number of checks that passed
        output_parts.append(f"\u2705 {healthy_count}/{healthy_count} system checks healthy")

    # --- Periodic Audits (absorbed from periodic-audits.md) ---
    due_audits = check_periodic_audits(session + 1)  # Check for NEXT session (current = session + 1)
    if due_audits:
        names = ", ".join(a["name"] for a in due_audits)
        output_parts.append(f"\U0001f4cb Audits due this session: {names}")

    # --- Session Persistence (new v2.0) ---
    persist = check_session_persist()
    if persist and persist.get("files_modified"):
        n_files = len(persist["files_modified"])
        output_parts.append(f"\U0001f4be Last session touched {n_files} files (auto-persisted)")

    # --- Output ---
    if output_parts:
        print(f"\n{'='*50}")
        for part in output_parts:
            print(f"  {part}")
        print(f"{'='*50}\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # Never block on errors - just log and exit 0
        print(f"Warning: session_start_reminder.py error: {e}", file=sys.stderr)
        sys.exit(0)
