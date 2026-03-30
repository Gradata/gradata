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

BRAIN_PATH = Path(os.environ.get("BRAIN_DIR", "C:/Users/olive/SpritesWork/brain"))
SPRITES_WORK = Path(os.environ.get("WORKING_DIR", "C:/Users/olive/OneDrive/Desktop/Sprites Work"))
PYTHON = os.environ.get("PYTHON_PATH", "C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe")
DB_PATH = BRAIN_PATH / "system.db"


def detect_session() -> int:
    """Detect current (active) session number from loop-state.md.

    loop-state.md records the last COMPLETED session (e.g. 'Session 35 Close').
    The active session is always last_completed + 1.
    """
    import re
    loop_state = BRAIN_PATH / "loop-state.md"
    if loop_state.exists():
        text = loop_state.read_text(encoding="utf-8")
        m = re.search(r"Session\s+(\d+)", text)
        if m:
            return int(m.group(1)) + 1
    return 0


def emit_stale_data(file_path: str, age_days: int, threshold_days: int):
    """Emit a STALE_DATA event for a file that hasn't been updated recently."""
    try:
        import subprocess
        import json as _json
        python = PYTHON
        data = _json.dumps({
            "file": file_path,
            "age_days": age_days,
            "threshold_days": threshold_days,
            "severity": "critical" if age_days > threshold_days * 2 else "warning",
        })
        tags = _json.dumps(["staleness:" + str(age_days) + "d", "file:" + Path(file_path).name])
        subprocess.run(
            [python, str(BRAIN_PATH / "scripts" / "events.py"),
             "emit", "STALE_DATA", "hook:session_start_reminder", data, tags],
            capture_output=True, text=True, timeout=5
        )
    except Exception:
        pass  # Non-blocking


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
            emit_stale_data(str(patterns), age_days, 14)
    else:
        alerts.append(("WARNING", "PATTERNS.md not found"))

    # 3b. loop-state.md staleness (should update every session)
    loop_state = BRAIN_PATH / "loop-state.md"
    if loop_state.exists():
        ls_age = (datetime.now() - datetime.fromtimestamp(loop_state.stat().st_mtime)).days
        if ls_age > 7:
            alerts.append(("WARNING", f"loop-state.md last updated {ls_age} days ago"))
            emit_stale_data(str(loop_state), ls_age, 7)

    # 3c. startup-brief.md staleness (should update every session)
    startup_brief = SPRITES_WORK / "domain" / "pipeline" / "startup-brief.md"
    if startup_brief.exists():
        sb_age = (datetime.now() - datetime.fromtimestamp(startup_brief.stat().st_mtime)).days
        if sb_age > 7:
            alerts.append(("WARNING", f"startup-brief.md last updated {sb_age} days ago"))
            emit_stale_data(str(startup_brief), sb_age, 7)

    # 4. brain/.git active
    if not (BRAIN_PATH / ".git").exists():
        alerts.append(("CRITICAL", "brain/.git missing — version control inactive"))

    # 5. CLAUDE.md line count
    claude_md = SPRITES_WORK / "CLAUDE.md"
    if claude_md.exists():
        lines = len(claude_md.read_text(encoding="utf-8").splitlines())
        if lines > 80:
            alerts.append(("WARNING", f"CLAUDE.md at {lines} lines (target: <60, limit: 80)"))

    # 6. events.jsonl exists (v2.0 backbone) — auto-create if missing
    events_file = BRAIN_PATH / "events.jsonl"
    if not events_file.exists():
        try:
            events_file.touch()
            alerts.append(("AUTO-FIXED", "events.jsonl was missing — created empty file"))
        except Exception:
            alerts.append(("WARNING", "events.jsonl missing — run: python brain/scripts/events.py init"))

    # 7. Config validation (settings.json, agent manifests, codebase health)
    try:
        import subprocess
        python = PYTHON
        validator = BRAIN_PATH / "scripts" / "config_validator.py"
        if validator.exists():
            result = subprocess.run(
                [python, str(validator), "--quick"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                fails = [l.strip() for l in result.stdout.splitlines() if "[FAIL]" in l]
                if fails:
                    alerts.append(("WARNING", f"Config: {len(fails)} issue(s) — run config_validator.py"))
    except Exception:
        pass  # Non-blocking

    # 8. Brain RAG freshness (launch.py health check)
    try:
        import subprocess
        python = PYTHON
        launch = BRAIN_PATH / "scripts" / "launch.py"
        if launch.exists():
            result = subprocess.run(
                [python, str(launch), "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode in (0, 1) and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                for issue in data.get("issues", []):
                    severity = issue.get("severity", "").lower()
                    msg = issue.get("message", "unknown issue")
                    issue_type = issue.get("type", "")
                    if severity in ("warning", "error"):
                        alerts.append(("WARNING", f"Brain RAG: {msg}"))
                    elif issue_type == "embedding_drift":
                        alerts.append(("INFO", f"Brain RAG: {msg}"))
    except Exception:
        pass  # Non-blocking

    # 9. Previous session gates written (catches incomplete wrap-ups)
    try:
        session = detect_session()
        prev = session - 1
        if prev > 0:
            conn = sqlite3.connect(str(DB_PATH))
            count = conn.execute(
                "SELECT COUNT(*) FROM session_gates WHERE session = ?", (prev,)
            ).fetchone()[0]
            conn.close()
            if count == 0:
                alerts.append(("WARNING", f"S{prev} wrap-up incomplete — no gates written to DB. Run validator to backfill."))
    except Exception:
        pass  # Non-blocking

    return alerts


def _audit_has_backing(name: str) -> bool:
    """Check if an audit has a real skill/script/CLI tool behind it."""
    import shutil

    # Check for skill files, command files, or brain scripts
    candidates = [
        SPRITES_WORK / ".claude" / "commands" / f"{name}.md",
        SPRITES_WORK / "skills" / name / "SKILL.md",
        SPRITES_WORK / "skills" / name.replace("-", "_") / "SKILL.md",
        BRAIN_PATH / "scripts" / f"{name}.py",
        BRAIN_PATH / "scripts" / f"{name.replace('-', '_')}.py",
    ]
    if any(p.exists() for p in candidates):
        return True

    # Check for globally installed CLI tools (e.g. agnix-lint -> agnix)
    cli_name = name.split("-")[0]  # agnix-lint -> agnix
    if shutil.which(cli_name):
        return True

    return False


def check_periodic_audits(session: int) -> list:
    """Check if any periodic audits are due. Validates usefulness first.

    Audits without a backing skill/script are auto-removed from the DB
    so they don't clutter the startup banner.
    """
    due = []
    if not DB_PATH.exists():
        return due

    try:
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(
            "SELECT audit_name, frequency, next_due_session FROM periodic_audits WHERE next_due_session <= ?",
            (session,)
        ).fetchall()

        orphans = []
        for r in rows:
            name, freq, due_at = r[0], r[1], r[2]
            if _audit_has_backing(name):
                due.append({"name": name, "frequency": freq, "due_at": due_at})
            else:
                orphans.append(name)

        # Auto-remove orphan audits (no backing file = dead weight)
        for name in orphans:
            conn.execute("DELETE FROM periodic_audits WHERE audit_name = ?", (name,))
        if orphans:
            conn.commit()

        conn.close()
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
        healthy_count = 7  # Number of checks that passed
        output_parts.append(f"\u2705 {healthy_count}/{healthy_count} system checks healthy")

    # --- Periodic Audits (absorbed from periodic-audits.md) ---
    due_audits = check_periodic_audits(session)  # detect_session() already returns active session
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
