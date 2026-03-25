"""
init-db.py — Initialize the Sprites.ai sales system SQLite database.
Creates system.db with all core tables and seeds from current system state.
"""

import sqlite3
import os
from datetime import datetime

BRAIN_DIR = os.environ.get("BRAIN_DIR", "C:/Users/olive/SpritesWork/brain")
DB_PATH = os.path.join(BRAIN_DIR, "system.db")

def create_tables(cur):
    """Create all core tables."""

    cur.execute("""
    CREATE TABLE IF NOT EXISTS deals (
        id INTEGER PRIMARY KEY,
        prospect_name TEXT NOT NULL,
        company TEXT NOT NULL,
        stage TEXT NOT NULL,
        deal_id INTEGER,
        value REAL,
        icp_score INTEGER,
        health_score REAL,
        close_probability REAL,
        days_in_stage INTEGER,
        touches_without_reply INTEGER,
        last_touch_date TEXT,
        next_touch_date TEXT,
        objection_severity TEXT DEFAULT 'none',
        engagement_signals TEXT,
        calibrated BOOLEAN DEFAULT 0,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cross_wires (
        id INTEGER PRIMARY KEY,
        connection TEXT NOT NULL,
        rule TEXT NOT NULL,
        fires INTEGER DEFAULT 0,
        value_produced INTEGER DEFAULT 0,
        value_rate REAL,
        status TEXT DEFAULT 'ACTIVE',
        last_fired TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('TRIGGER','INTENT','COMPETITIVE','SOCIAL','MARKET')),
        prospect TEXT,
        company TEXT,
        signal TEXT NOT NULL,
        source TEXT,
        relevance INTEGER CHECK(relevance BETWEEN 1 AND 10),
        action_taken TEXT,
        processed BOOLEAN DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS frameworks (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        times_used INTEGER DEFAULT 0,
        conversion_rate REAL,
        best_persona TEXT,
        worst_persona TEXT,
        default_for TEXT,
        confidence TEXT DEFAULT '[INSUFFICIENT]',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS smoke_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session INTEGER NOT NULL,
        check_type TEXT NOT NULL,
        result TEXT CHECK(result IN ('PASS','FAIL','N/A')),
        root_cause TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session INTEGER NOT NULL,
        date TEXT NOT NULL,
        research INTEGER,
        quality INTEGER,
        process INTEGER,
        learning INTEGER,
        outcomes INTEGER,
        auditor_avg REAL,
        loop_avg REAL,
        combined_avg REAL,
        lowest_dim TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS convergence (
        id INTEGER PRIMARY KEY,
        indicator TEXT NOT NULL UNIQUE,
        current_value REAL,
        threshold REAL,
        status TEXT DEFAULT 'NOT CONVERGED',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS session_metrics (
        session INTEGER PRIMARY KEY,
        date TEXT NOT NULL,
        session_type TEXT NOT NULL DEFAULT 'full',
        outputs_produced INTEGER DEFAULT 0,
        outputs_unedited INTEGER DEFAULT 0,
        corrections INTEGER DEFAULT 0,
        first_draft_acceptance REAL,
        correction_density REAL,
        source_coverage REAL,
        confidence_calibration REAL,
        gate_pass_count INTEGER,
        gate_total_count INTEGER,
        gate_pass_rate REAL,
        gate_result TEXT CHECK(gate_result IN ('PASS','FAIL')),
        growth_reply_rate REAL,
        growth_deal_velocity REAL,
        growth_pipeline_trend REAL,
        growth_win_rate REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS session_gates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session INTEGER NOT NULL,
        check_name TEXT NOT NULL,
        passed BOOLEAN NOT NULL,
        detail TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_session_gates_session ON session_gates(session)")


def seed_deals(cur):
    """Seed 7 deals from pipeline snapshot (loop-state.md, 2026-03-18)."""
    deals = [
        (1, 'Tim Sok', 'Henge', 'proposal-made', 167, 1000, 9, None, None, 7, 0, '2026-03-18', '2026-03-25', 'none', None, 0),
        (2, 'Kevin Gilsdorf', 'Kindle Point', 'proposal-made', 162, 300, 7, None, None, 5, 0, '2026-03-18', '2026-03-23', 'none', None, 0),
        (3, 'Hassan Ali', 'Ugly Ads', 'demo-done', 168, 500, 6, None, None, 3, 0, '2026-03-17', '2026-03-20', 'none', None, 0),
        (4, 'Jennifer Liginski', 'Renovation Brands', 'no-show-fu', 147, 60, 9, None, None, 14, 0, None, '2026-03-20', 'none', None, 0),
        (5, 'Celia Young', 'i-screen', 'proposal-made', 161, 500, 4, None, None, 0, 0, None, '2026-03-21', 'none', None, 0),
        (6, 'Olivia Gomez', 'Shahram Khaledi', 'proposal-made', 159, 60, 3, None, None, 2, 0, None, '2026-03-23', 'none', None, 0),
        (7, 'Alison Binkley', 'INNOCEAN Canada', 'demo-scheduled', 160, 1000, 8, None, None, 0, 0, None, '2026-04-07', 'none', None, 0),
    ]
    cur.executemany("""
        INSERT OR REPLACE INTO deals
        (id, prospect_name, company, stage, deal_id, value, icp_score, health_score,
         close_probability, days_in_stage, touches_without_reply, last_touch_date,
         next_touch_date, objection_severity, engagement_signals, calibrated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, deals)


def seed_cross_wires(cur):
    """Seed 7 event connections from system-patterns.md (all at 0 fires)."""
    wires = [
        (1, 'Auditor -> Gates', 'R34', 0, 0, None, 'ACTIVE', None),
        (2, 'Gates -> Lessons', 'R35', 0, 0, None, 'ACTIVE', None),
        (3, 'Lessons -> CARL', 'R36', 0, 0, None, 'ACTIVE', None),
        (4, 'Smoke -> Lessons', 'R37', 0, 0, None, 'ACTIVE', None),
        (5, 'Rubric Drift -> Tighten', 'R38', 0, 0, None, 'ACTIVE', None),
        (6, 'Fallback -> Reorder', 'R39', 0, 0, None, 'ACTIVE', None),
        (7, 'PATTERNS -> Gates', 'R40', 0, 0, None, 'ACTIVE', None),
    ]
    cur.executemany("""
        INSERT OR REPLACE INTO cross_wires
        (id, connection, rule, fires, value_produced, value_rate, status, last_fired)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, wires)


def seed_frameworks(cur):
    """Seed 5 frameworks from system-patterns.md."""
    frameworks = [
        (1, 'CCQ', 0, None, None, None, None, '[INSUFFICIENT]'),
        (2, 'Gap Selling', 0, None, None, None, None, '[INSUFFICIENT]'),
        (3, 'JOLT', 0, None, None, None, None, '[INSUFFICIENT]'),
        (4, 'SPIN', 0, None, None, None, None, '[INSUFFICIENT]'),
        (5, 'Challenger', 0, None, None, None, None, '[INSUFFICIENT]'),
    ]
    cur.executemany("""
        INSERT OR REPLACE INTO frameworks
        (id, name, times_used, conversion_rate, best_persona, worst_persona, default_for, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, frameworks)


def seed_convergence(cur):
    """Seed 5 convergence indicators from system-patterns.md."""
    indicators = [
        (1, 'Sessions since last new lesson', 0, 3, 'NOT CONVERGED'),
        (2, 'Sessions since last rule change', 0, 3, 'NOT CONVERGED'),
        (3, 'Sessions since last gate catch', 0, 3, 'NOT CONVERGED'),
        (4, 'Avg audit score (last 5)', 8.06, 9.0, 'NOT CONVERGED'),
        (5, 'Cross-wire dormancy rate', 0, 50, 'NOT CONVERGED'),
    ]
    cur.executemany("""
        INSERT OR REPLACE INTO convergence
        (id, indicator, current_value, threshold, status)
        VALUES (?, ?, ?, ?, ?)
    """, indicators)


def seed_audit_scores(cur):
    """Seed session 3 and 4 audit scores from audit-log.md."""
    scores = [
        # Session 3 (final after post-wrap supplement)
        (3, '2026-03-18', 8, 8, 9, 10, 6, 8.2, 8.17, 8.18, 'Outcomes'),
        # Session 4
        (4, '2026-03-18', 8, 8, 7, 9, 5, 7.4, 8.67, 8.03, 'Outcomes'),
    ]
    cur.executemany("""
        INSERT INTO audit_scores
        (session, date, research, quality, process, learning, outcomes,
         auditor_avg, loop_avg, combined_avg, lowest_dim)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, scores)


def main():
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Remove existing DB to start fresh
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Enable WAL mode for better concurrent read performance
    cur.execute("PRAGMA journal_mode=WAL")

    print("Creating tables...")
    create_tables(cur)

    print("Seeding deals (7)...")
    seed_deals(cur)

    print("Seeding event connections (7)...")
    seed_cross_wires(cur)

    print("Seeding frameworks (5)...")
    seed_frameworks(cur)

    print("Seeding convergence indicators (5)...")
    seed_convergence(cur)

    print("Seeding audit scores (sessions 3-4)...")
    seed_audit_scores(cur)

    conn.commit()

    # Print summary
    print("\n" + "=" * 60)
    print("DATABASE INITIALIZED SUCCESSFULLY")
    print("=" * 60)
    print(f"Path: {DB_PATH}")
    print()

    tables = ['deals', 'cross_wires', 'signals', 'frameworks',
              'smoke_checks', 'audit_scores', 'convergence']

    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  {table:20s} {count:3d} rows")

    print()
    print("Pipeline snapshot:")
    cur.execute("SELECT prospect_name, company, stage, value FROM deals ORDER BY value DESC")
    for row in cur.fetchall():
        print(f"  {row[0]:20s} | {row[1]:20s} | {row[2]:15s} | ${row[3]:,.0f}")

    print()
    print("Audit history:")
    cur.execute("SELECT session, combined_avg, lowest_dim FROM audit_scores ORDER BY session")
    for row in cur.fetchall():
        print(f"  Session {row[0]}: {row[1]:.2f} combined (lowest: {row[2]})")

    conn.close()
    print("\nDone. Query with: python tools/query-db.py \"SELECT * FROM deals\"")


if __name__ == "__main__":
    main()
