"""Safety-net backfill for rows inserted with NULL tenant_id.

Migration 001 backfilled existing rows. Only ``_events.py`` currently
passes tenant_id on new inserts; other call sites (rule_provenance,
meta_rules, brain_fts_content, correction_patterns, activity_log,
prep_outcomes, lesson_transitions, pending_approvals, rule_relationships,
etc.) still write NULL until they're wired in a follow-up pass.

This script fills those NULLs with the primary tenant UUID. Safe to run
as a post-session hook (wrap-up) or on a schedule. Idempotent.

Usage:
    python src/gradata/_migrations/fill_null_tenant.py --brain C:/.../brain
    python src/gradata/_migrations/fill_null_tenant.py --brain C:/.../brain --dry-run
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "migrations"))
from _runner import column_exists, resolve_brain_db, table_exists  # type: ignore[import-not-found]  # noqa: E402
from tenant_uuid import read_tenant_id  # type: ignore[import-not-found]  # noqa: E402


# Per-tenant tables with tenant_id that are NOT fully wired in the SDK yet.
# Safe to backfill because the local SDK is single-tenant per brain.
#
# IMPORTANT: This list deliberately EXCLUDES the mixed-visibility tables
# (meta_rules, frameworks, rule_relationships). In those tables, ``tenant_id
# IS NULL`` is the sentinel for "global / shareable across brains", so
# backfilling NULLs would silently capture legitimate global rows into the
# primary tenant. Migration 001 leaves them NULL on purpose.
CANDIDATE_TABLES: list[str] = [
    "deals",
    "signals",
    "audit_scores",
    "gate_triggers",
    "lesson_applications",
    "entities",
    "relationships",
    "decisions",
    "pipeline_snapshots",
    "daily_metrics",
    "activity_log",
    "prep_outcomes",
    "events",
    "facts",
    "session_metrics",
    "session_gates",
    "output_classifications",
    "correction_severity",
    "ablation_log",
    "rule_provenance",
    "correction_patterns",
    "tasks",
    "agent_jobs",
    "demo_recordings",
    "pending_approvals",
    "brain_embeddings",
    "brain_fts_content",
    "enrichment_queue",
    "enrichment_processed_files",
    "rule_canary",
    "lesson_transitions",
    "sync_state",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brain", help="Brain directory or system.db path")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = resolve_brain_db(args.brain)
    if not db_path.exists():
        print(f"ERROR: brain DB not found at {db_path}", file=sys.stderr)
        return 2

    brain_dir = db_path.parent
    tid = read_tenant_id(brain_dir)
    if not tid:
        print(
            f"ERROR: no tenant UUID in {brain_dir}/.tenant_id - run migration 001 first",
            file=sys.stderr,
        )
        return 2

    print(f"Brain  : {db_path}")
    print(f"Tenant : {tid}")
    print(f"Mode   : {'dry-run' if args.dry_run else 'apply'}")
    print()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA busy_timeout=5000")

    total = 0
    touched: list[tuple[str, int]] = []
    try:
        for t in CANDIDATE_TABLES:
            if not table_exists(conn, t):
                continue
            if not column_exists(conn, t, "tenant_id"):
                continue
            cnt = conn.execute(
                f"SELECT COUNT(*) FROM {t} WHERE tenant_id IS NULL"
            ).fetchone()[0]
            if not cnt:
                continue
            if args.dry_run:
                touched.append((t, cnt))
                total += cnt
                continue
            cur = conn.execute(
                f"UPDATE {t} SET tenant_id = ? WHERE tenant_id IS NULL",
                (tid,),
            )
            if cur.rowcount:
                touched.append((t, cur.rowcount))
                total += cur.rowcount
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()

    if not touched:
        print("no NULL tenant_id rows found")
        return 0

    for t, n in touched:
        print(f"  {t:32s} {n:>8} rows")
    verb = "would backfill" if args.dry_run else "backfilled"
    print(f"\n{verb} {total} rows across {len(touched)} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
