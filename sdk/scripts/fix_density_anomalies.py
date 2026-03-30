"""
One-time fix for session_metrics density anomalies found in S75 audit.

Anomalies:
  S35: density=0.0 with 2 corrections
  S36: density=0.8 with 0 events (phantom)
  S69: density=0.0 with 5 corrections and 70 outputs
  S64, S67, S68: corrections>0 but density=None

Run: python sdk/scripts/fix_density_anomalies.py
"""

import os
import sqlite3
import sys

DB_PATH = os.environ.get("BRAIN_DIR", "./brain") + "/system.db"


def fix_densities(db_path: str) -> None:
    conn = sqlite3.connect(db_path)

    # Show current state
    print("=== BEFORE ===")
    rows = conn.execute("""
        SELECT sm.session, sm.correction_density, sm.outputs_produced, sm.corrections,
            (SELECT COUNT(*) FROM events WHERE type='CORRECTION' AND session=sm.session) as actual_corr,
            (SELECT COUNT(*) FROM events WHERE type='OUTPUT' AND session=sm.session) as actual_out
        FROM session_metrics sm
        WHERE sm.session IN (35, 36, 64, 67, 68, 69)
        ORDER BY sm.session
    """).fetchall()
    for r in rows:
        print(f"  S{r[0]}: density={r[1]}, outputs={r[2]}, corrections={r[3]}, "
              f"actual_corr={r[4]}, actual_out={r[5]}")

    conn.execute("BEGIN TRANSACTION")

    # Fix each session: recompute density from actual events
    for session in [35, 36, 64, 67, 68, 69]:
        actual_corr = conn.execute(
            "SELECT COUNT(*) FROM events WHERE type='CORRECTION' AND session=?",
            (session,)
        ).fetchone()[0]
        actual_out = conn.execute(
            "SELECT COUNT(*) FROM events WHERE type='OUTPUT' AND session=?",
            (session,)
        ).fetchone()[0]

        if actual_out > 0:
            density = round(actual_corr / actual_out, 6)
        elif actual_corr > 0:
            density = None  # corrections but no outputs = can't compute ratio
        else:
            density = None  # no events = can't compute

        conn.execute(
            "UPDATE session_metrics SET correction_density=?, corrections=? WHERE session=?",
            (density, actual_corr, session)
        )
        print(f"  Fixed S{session}: density={density}, corrections={actual_corr}, outputs={actual_out}")

    conn.execute("COMMIT")

    # Verify
    print("\n=== AFTER ===")
    rows = conn.execute("""
        SELECT session, correction_density, outputs_produced, corrections
        FROM session_metrics
        WHERE session IN (35, 36, 64, 67, 68, 69)
        ORDER BY session
    """).fetchall()
    for r in rows:
        print(f"  S{r[0]}: density={r[1]}, outputs={r[2]}, corrections={r[3]}")

    # Check for any remaining anomalies
    print("\n=== REMAINING ANOMALIES ===")
    anomalies = conn.execute("""
        SELECT session, correction_density, outputs_produced, corrections
        FROM session_metrics
        WHERE (corrections > 0 AND correction_density = 0 AND outputs_produced > 0)
           OR (corrections = 0 AND outputs_produced = 0 AND correction_density IS NOT NULL AND correction_density > 0)
    """).fetchall()
    if anomalies:
        for r in anomalies:
            print(f"  S{r[0]}: density={r[1]}, outputs={r[2]}, corrections={r[3]}")
    else:
        print("  None found. All clean.")

    conn.close()


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)
    fix_densities(DB_PATH)
