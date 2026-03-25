#!/usr/bin/env python3
"""
Usage Analytics for Sprites Work Sales Agent System
Tracks rule fires, gate triggers, lesson applications, and calibration events.
Connects to: C:/Users/olive/SpritesWork/brain/system.db
"""

import sqlite3
import sys
import argparse
from datetime import datetime, timezone, timedelta


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

import os
BRAIN_DIR = os.environ.get("BRAIN_DIR", "C:/Users/olive/SpritesWork/brain")
DB_PATH = os.path.join(BRAIN_DIR, "system.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rule_fires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL,
            domain TEXT NOT NULL,
            session INTEGER,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            context TEXT,
            outcome TEXT CHECK(outcome IN ('applied', 'skipped', 'overridden'))
        );

        CREATE TABLE IF NOT EXISTS gate_triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gate_name TEXT NOT NULL,
            session INTEGER,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            result TEXT CHECK(result IN ('passed', 'failed', 'caught_issue')),
            issue_caught TEXT
        );

        CREATE TABLE IF NOT EXISTS lesson_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id TEXT NOT NULL,
            session INTEGER,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            scenario TEXT,
            prevented_mistake INTEGER CHECK(prevented_mistake IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS calibration_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session INTEGER,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            output_type TEXT NOT NULL,
            self_score REAL,
            oliver_score REAL,
            delta REAL
        );

        CREATE TABLE IF NOT EXISTS chaos_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session INTEGER,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            target_rule TEXT NOT NULL,
            test_description TEXT,
            result TEXT CHECK(result IN ('caught', 'missed')),
            response_detail TEXT
        );

        CREATE TABLE IF NOT EXISTS canonical_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session INTEGER,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            action_type TEXT NOT NULL,
            prospect TEXT,
            company TEXT,
            persona TEXT,
            angle TEXT,
            tone TEXT,
            framework TEXT,
            gate_result TEXT,
            patterns_checked INTEGER DEFAULT 0,
            self_score REAL,
            oliver_score REAL,
            rules_fired TEXT,
            lessons_applied TEXT,
            chaos_test TEXT,
            experiment TEXT,
            outcome TEXT DEFAULT 'pending'
        );
    """)
    conn.commit()


def cmd_log_rule(args):
    conn = get_connection()
    init_tables(conn)
    context = args.context if args.context else None
    conn.execute(
        "INSERT INTO rule_fires (rule_id, domain, session, timestamp, context, outcome) VALUES (?, ?, ?, ?, ?, ?)",
        (args.rule_id, args.domain, args.session, utcnow(), context, args.outcome)
    )
    conn.commit()
    print(f"Logged rule fire: {args.rule_id} | domain={args.domain} | session={args.session} | outcome={args.outcome}")
    conn.close()


def cmd_log_gate(args):
    conn = get_connection()
    init_tables(conn)
    issue = args.issue_caught if args.issue_caught else None
    conn.execute(
        "INSERT INTO gate_triggers (gate_name, session, timestamp, result, issue_caught) VALUES (?, ?, ?, ?, ?)",
        (args.gate_name, args.session, utcnow(), args.result, issue)
    )
    conn.commit()
    print(f"Logged gate trigger: {args.gate_name} | session={args.session} | result={args.result}")
    conn.close()


def cmd_log_lesson(args):
    conn = get_connection()
    init_tables(conn)
    prevented = 1 if str(args.prevented).lower() in ('1', 'true', 'yes') else 0
    conn.execute(
        "INSERT INTO lesson_applications (lesson_id, session, timestamp, scenario, prevented_mistake) VALUES (?, ?, ?, ?, ?)",
        (args.lesson_id, args.session, utcnow(), args.scenario, prevented)
    )
    conn.commit()
    print(f"Logged lesson application: {args.lesson_id} | session={args.session} | prevented={bool(prevented)}")
    conn.close()


def cmd_log_calibration(args):
    conn = get_connection()
    init_tables(conn)
    delta = round(args.oliver_score - args.self_score, 2)
    conn.execute(
        "INSERT INTO calibration_events (session, timestamp, output_type, self_score, oliver_score, delta) VALUES (?, ?, ?, ?, ?, ?)",
        (args.session, utcnow(), args.output_type, args.self_score, args.oliver_score, delta)
    )
    conn.commit()
    print(f"Logged calibration: {args.output_type} | session={args.session} | self={args.self_score} oliver={args.oliver_score} delta={delta:+.1f}")
    conn.close()


def cmd_log_chaos(args):
    conn = get_connection()
    init_tables(conn)
    description = args.test_description if args.test_description else None
    detail = args.response_detail if args.response_detail else None
    conn.execute(
        "INSERT INTO chaos_tests (session, timestamp, target_rule, test_description, result, response_detail) VALUES (?, ?, ?, ?, ?, ?)",
        (args.session, utcnow(), args.target_rule, description, args.result, detail)
    )
    conn.commit()
    print(f"Logged chaos test: {args.target_rule} | session={args.session} | result={args.result}")
    conn.close()


def cmd_log_canonical(args):
    conn = get_connection()
    init_tables(conn)
    patterns_checked = 1 if args.patterns else 0
    conn.execute(
        """INSERT INTO canonical_logs
           (session, timestamp, action_type, prospect, company, persona, angle, tone, framework,
            gate_result, patterns_checked, self_score, rules_fired, lessons_applied, chaos_test, experiment)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            args.session, utcnow(), args.action_type,
            args.prospect, args.company, args.persona,
            args.angle, args.tone, args.framework,
            args.gate, patterns_checked, args.self_score,
            args.rules, args.lessons, args.chaos_test, args.experiment
        )
    )
    conn.commit()
    print(f"Logged canonical: {args.action_type} | session={args.session} | prospect={args.prospect} | company={args.company}")
    conn.close()


def cmd_report(args):
    session = args.session_number
    conn = get_connection()
    init_tables(conn)

    print(f"\n=== Analytics Report (Session {session}) ===")

    # --- Rules ---
    rule_rows = conn.execute(
        "SELECT rule_id, COUNT(*) as cnt FROM rule_fires WHERE session = ? GROUP BY rule_id ORDER BY cnt DESC",
        (session,)
    ).fetchall()
    total_rule_fires = sum(r['cnt'] for r in rule_rows)
    top_rule = rule_rows[0] if rule_rows else None
    top_rule_str = f"{top_rule['rule_id']} ({top_rule['cnt']} fires)" if top_rule else "none"

    # Rules that fired historically but NOT this session
    all_rules = conn.execute("SELECT DISTINCT rule_id FROM rule_fires").fetchall()
    session_rule_ids = {r['rule_id'] for r in rule_rows}
    never_fired_this = [r['rule_id'] for r in all_rules if r['rule_id'] not in session_rule_ids]
    never_str = ", ".join(never_fired_this) if never_fired_this else "none"

    print(f"Rules: {total_rule_fires} fires this session | Top: {top_rule_str} | Never fired: [{never_str}]")

    # --- Gates ---
    gate_rows = conn.execute(
        "SELECT result, COUNT(*) as cnt FROM gate_triggers WHERE session = ? GROUP BY result",
        (session,)
    ).fetchall()
    gate_map = {r['result']: r['cnt'] for r in gate_rows}
    total_gates = sum(gate_map.values())
    caught = gate_map.get('caught_issue', 0)
    rubber_stamped = gate_map.get('passed', 0)
    failed = gate_map.get('failed', 0)
    print(f"Gates: {total_gates} triggers | Caught issues: {caught} | Rubber-stamped: {rubber_stamped} | Failed: {failed}")

    # --- Lessons ---
    lesson_rows = conn.execute(
        "SELECT prevented_mistake, COUNT(*) as cnt FROM lesson_applications WHERE session = ? GROUP BY prevented_mistake",
        (session,)
    ).fetchall()
    lesson_map = {r['prevented_mistake']: r['cnt'] for r in lesson_rows}
    total_lessons = sum(lesson_map.values())
    prevented_count = lesson_map.get(1, 0)
    not_prevented = lesson_map.get(0, 0)
    print(f"Lessons: {total_lessons} applied | Prevented: {prevented_count} mistakes | Failed: {not_prevented}")

    # --- Calibration ---
    cal_rows = conn.execute(
        "SELECT delta FROM calibration_events WHERE session = ?",
        (session,)
    ).fetchall()
    if cal_rows:
        avg_delta = sum(r['delta'] for r in cal_rows) / len(cal_rows)
        drift_status = "DRIFTING" if abs(avg_delta) >= 2.0 else "HEALTHY"
        print(f"Calibration: avg_delta = {avg_delta:+.2f} | Drift: {drift_status}")
    else:
        print("Calibration: no events this session")

    # --- Top 5 all-time rules ---
    print(f"\n=== Top 5 most-fired rules (all time) ===")
    top5 = conn.execute(
        "SELECT rule_id, domain, COUNT(*) as cnt FROM rule_fires GROUP BY rule_id ORDER BY cnt DESC LIMIT 5"
    ).fetchall()
    if top5:
        for rank, row in enumerate(top5, 1):
            print(f"  {rank}. {row['rule_id']} [{row['domain']}] — {row['cnt']} fires")
    else:
        print("  No rule fire data yet.")

    # --- Kill candidates: rules not fired in 30+ sessions ---
    print(f"\n=== Rules with 0 fires in 30+ sessions (kill candidates) ===")
    # Find the current max session across all data
    max_session_row = conn.execute("SELECT MAX(session) as mx FROM rule_fires").fetchone()
    max_session = max_session_row['mx'] if max_session_row and max_session_row['mx'] else session
    cutoff_session = max_session - 30

    if cutoff_session > 0:
        kill_candidates = conn.execute("""
            SELECT rule_id, MAX(session) as last_session
            FROM rule_fires
            GROUP BY rule_id
            HAVING MAX(session) <= ?
            ORDER BY last_session ASC
        """, (cutoff_session,)).fetchall()
        if kill_candidates:
            for row in kill_candidates:
                print(f"  {row['rule_id']} — last fired session {row['last_session']}")
        else:
            print("  None. All rules fired within 30 sessions.")
    else:
        print(f"  Not enough session history (need 30+ sessions, currently at session {max_session}).")

    # --- Chaos Tests ---
    print(f"\n=== Chaos Tests ===")
    chaos_rows = conn.execute(
        "SELECT result, COUNT(*) as cnt FROM chaos_tests WHERE session = ? GROUP BY result",
        (session,)
    ).fetchall()
    chaos_map = {r['result']: r['cnt'] for r in chaos_rows}
    total_chaos = sum(chaos_map.values())
    caught_chaos = chaos_map.get('caught', 0)
    missed_chaos = chaos_map.get('missed', 0)
    catch_rate = round((caught_chaos / total_chaos) * 100) if total_chaos > 0 else 0
    print(f"Total: {total_chaos} | Caught: {caught_chaos} | Missed: {missed_chaos} | Catch rate: {catch_rate}%")

    missed_tests = conn.execute(
        "SELECT target_rule, test_description FROM chaos_tests WHERE session = ? AND result = 'missed'",
        (session,)
    ).fetchall()
    if missed_tests:
        print("Missed tests (system holes):")
        for row in missed_tests:
            desc = f" — {row['test_description']}" if row['test_description'] else ""
            print(f"  - {row['target_rule']}{desc}")
    else:
        print("Missed tests: none")

    # --- Canonical Log Summary ---
    print(f"\n=== Canonical Log Summary ===")
    canonical_rows = conn.execute(
        "SELECT action_type, angle, tone FROM canonical_logs WHERE session = ?",
        (session,)
    ).fetchall()
    total_actions = len(canonical_rows)
    print(f"Actions this session: {total_actions}")

    if canonical_rows:
        # Most common action type
        from collections import Counter
        action_counts = Counter(r['action_type'] for r in canonical_rows if r['action_type'])
        if action_counts:
            top_action, top_action_cnt = action_counts.most_common(1)[0]
            print(f"Most common action type: {top_action} ({top_action_cnt} times)")

        # Most used angle
        angle_counts = Counter(r['angle'] for r in canonical_rows if r['angle'])
        top_angle = angle_counts.most_common(1)[0][0] if angle_counts else "none"

        # Most used tone
        tone_counts = Counter(r['tone'] for r in canonical_rows if r['tone'])
        top_tone = tone_counts.most_common(1)[0][0] if tone_counts else "none"

        print(f"Most used angle: {top_angle} | Most used tone: {top_tone}")
    else:
        print("No canonical log entries this session.")

    conn.close()
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Sprites Work Usage Analytics — log and query sales agent activity"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # log-rule
    p_rule = subparsers.add_parser("log-rule", help="Log a CARL rule fire")
    p_rule.add_argument("rule_id", help="Rule identifier (e.g. LOOP_RULE_34)")
    p_rule.add_argument("domain", help="Domain (e.g. loop, agents, global)")
    p_rule.add_argument("session", type=int, help="Session number")
    p_rule.add_argument("outcome", choices=["applied", "skipped", "overridden"])
    p_rule.add_argument("context", nargs="?", default=None, help="Optional context note")
    p_rule.set_defaults(func=cmd_log_rule)

    # log-gate
    p_gate = subparsers.add_parser("log-gate", help="Log a gate trigger")
    p_gate.add_argument("gate_name", help="Gate name (e.g. Pre-Draft, Demo-Prep)")
    p_gate.add_argument("session", type=int, help="Session number")
    p_gate.add_argument("result", choices=["passed", "failed", "caught_issue"])
    p_gate.add_argument("issue_caught", nargs="?", default=None, help="Description of caught issue (if any)")
    p_gate.set_defaults(func=cmd_log_gate)

    # log-lesson
    p_lesson = subparsers.add_parser("log-lesson", help="Log a lesson application")
    p_lesson.add_argument("lesson_id", help="Lesson identifier")
    p_lesson.add_argument("session", type=int, help="Session number")
    p_lesson.add_argument("scenario", help="Short description of the scenario")
    p_lesson.add_argument("prevented", help="Did it prevent a mistake? (1/0 or true/false)")
    p_lesson.set_defaults(func=cmd_log_lesson)

    # log-calibration
    p_cal = subparsers.add_parser("log-calibration", help="Log a self-score vs Oliver-score calibration event")
    p_cal.add_argument("session", type=int, help="Session number")
    p_cal.add_argument("output_type", help="Type of output scored (e.g. email, demo-prep)")
    p_cal.add_argument("self_score", type=float, help="Claude's self-assessed score")
    p_cal.add_argument("oliver_score", type=float, help="Oliver's actual score")
    p_cal.set_defaults(func=cmd_log_calibration)

    # log-chaos
    p_chaos = subparsers.add_parser("log-chaos", help="Log a chaos test result (GLOBAL_RULE_12)")
    p_chaos.add_argument("session", type=int, help="Session number")
    p_chaos.add_argument("target_rule", help="Rule or gate being tested (e.g. LOOP_RULE_1, Pre-Draft)")
    p_chaos.add_argument("result", choices=["caught", "missed"], help="Whether the system caught the chaos injection")
    p_chaos.add_argument("test_description", nargs="?", default=None, help="What was attempted (optional)")
    p_chaos.add_argument("response_detail", nargs="?", default=None, help="How/why it was caught or missed (optional)")
    p_chaos.set_defaults(func=cmd_log_chaos)

    # log-canonical
    p_canon = subparsers.add_parser("log-canonical", help="Log a canonical log line (Stripe-inspired) for a major action")
    p_canon.add_argument("session", type=int, help="Session number")
    p_canon.add_argument("action_type", help="Type of action (e.g. email_draft, demo_prep, cold_call)")
    p_canon.add_argument("--prospect", default=None, help="Prospect name")
    p_canon.add_argument("--company", default=None, help="Company name")
    p_canon.add_argument("--persona", default=None, help="Persona tag (e.g. agency_owner, solo_founder)")
    p_canon.add_argument("--angle", default=None, help="Angle used (e.g. time-savings, case-study)")
    p_canon.add_argument("--tone", default=None, help="Tone used (e.g. direct, consultative)")
    p_canon.add_argument("--framework", default=None, help="Email framework (e.g. CCQ, inbound, follow-up)")
    p_canon.add_argument("--gate", default=None, dest="gate", help="Gate result (e.g. pre-draft:PASSED)")
    p_canon.add_argument("--patterns", type=int, default=0, help="1 if PATTERNS.md was checked, 0 if not")
    p_canon.add_argument("--self-score", type=float, default=None, dest="self_score", help="Self-assessed quality score")
    p_canon.add_argument("--rules", default=None, help="Comma-separated rules fired (e.g. LOOP_1,LOOP_2)")
    p_canon.add_argument("--lessons", default=None, help="Comma-separated lessons applied (e.g. L45,L69)")
    p_canon.add_argument("--chaos-test", default=None, dest="chaos_test", help="Chaos test run during this action (or 'none')")
    p_canon.add_argument("--experiment", default=None, help="Experiment tag if applicable (e.g. breakup-with-referral:variant_b)")
    p_canon.set_defaults(func=cmd_log_canonical)

    # report
    p_report = subparsers.add_parser("report", help="Generate analytics report for a session")
    p_report.add_argument("session_number", type=int, help="Session number to report on")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
