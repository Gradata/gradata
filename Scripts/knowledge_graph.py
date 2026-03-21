#!/usr/bin/env python3
"""
Knowledge Graph / Decision Ontology (Palantir-inspired)
Sprites.ai Sales Agent — Session 6

Maps relationships between prospects, companies, personas, angles, objections,
and case studies — then uses those relationships to inform future decisions.

Usage:
  python knowledge_graph.py add-entity <type> <name> [metadata_json]
  python knowledge_graph.py add-relationship <from_type:from_name> <relationship> <to_type:to_name> [strength]
  python knowledge_graph.py log-decision <deal_id> <session> <stage> <data_used> <logic_applied> <action_taken>
  python knowledge_graph.py query-similar <type:name>
  python knowledge_graph.py query-playbook <persona>
  python knowledge_graph.py query-decision-chain <deal_id>
"""

import sqlite3
import argparse
import sys
import json
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

DB_PATH = "C:/Users/olive/SpritesWork/brain/system.db"

VALID_ENTITY_TYPES = {
    'prospect', 'company', 'industry', 'persona',
    'angle', 'objection', 'case_study', 'framework'
}


# ---------------------------------------------------------------------------
# DB SETUP
# ---------------------------------------------------------------------------

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    cursor = conn.cursor()

    # Entities table
    cursor.execute('''CREATE TABLE IF NOT EXISTS entities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL CHECK(type IN ('prospect','company','industry','persona','angle','objection','case_study','framework')),
        name TEXT NOT NULL,
        metadata TEXT,
        created TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(type, name)
    )''')

    # Relationships table
    cursor.execute('''CREATE TABLE IF NOT EXISTS relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_id INTEGER NOT NULL,
        to_id INTEGER NOT NULL,
        relationship TEXT NOT NULL,
        strength REAL DEFAULT 0.5,
        evidence_count INTEGER DEFAULT 1,
        last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (from_id) REFERENCES entities(id),
        FOREIGN KEY (to_id) REFERENCES entities(id)
    )''')

    # Decision chain table (Palantir's data+logic+action)
    cursor.execute('''CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deal_id INTEGER,
        session INTEGER,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        stage TEXT,
        data_used TEXT,
        logic_applied TEXT,
        action_taken TEXT,
        outcome TEXT DEFAULT 'pending',
        outcome_date TEXT
    )''')

    conn.commit()


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def parse_type_name(value, label="entity"):
    """Parse 'type:name' format. Raises SystemExit on bad input."""
    if ':' not in value:
        print(f"ERROR: {label} must be in format type:name (e.g. prospect:John Smith)")
        sys.exit(1)
    entity_type, name = value.split(':', 1)
    entity_type = entity_type.strip().lower()
    name = name.strip()
    if entity_type not in VALID_ENTITY_TYPES:
        print(f"ERROR: Invalid entity type '{entity_type}'. Valid types: {', '.join(sorted(VALID_ENTITY_TYPES))}")
        sys.exit(1)
    if not name:
        print(f"ERROR: Name cannot be empty in {label}")
        sys.exit(1)
    return entity_type, name


def get_or_create_entity(cursor, entity_type, name, metadata=None):
    """Return existing entity id or insert and return new id."""
    cursor.execute(
        "SELECT id FROM entities WHERE type = ? AND name = ?",
        (entity_type, name)
    )
    row = cursor.fetchone()
    if row:
        return row['id'], False
    cursor.execute(
        "INSERT INTO entities (type, name, metadata, created) VALUES (?, ?, ?, ?)",
        (entity_type, name, metadata, _now())
    )
    return cursor.lastrowid, True


def strength_badge(strength, evidence_count):
    """Return a human-readable strength label."""
    if evidence_count < 3:
        return f"{strength:.2f} [INSUFFICIENT DATA]"
    if strength >= 0.8:
        return f"{strength:.2f} [STRONG]"
    if strength >= 0.5:
        return f"{strength:.2f} [MODERATE]"
    if strength >= 0.2:
        return f"{strength:.2f} [WEAK]"
    return f"{strength:.2f} [VERY WEAK — review]"


# ---------------------------------------------------------------------------
# COMMANDS
# ---------------------------------------------------------------------------

def cmd_add_entity(args):
    entity_type = args.type.strip().lower()
    name = args.name.strip()
    metadata = args.metadata

    if entity_type not in VALID_ENTITY_TYPES:
        print(f"ERROR: Invalid type '{entity_type}'. Valid: {', '.join(sorted(VALID_ENTITY_TYPES))}")
        sys.exit(1)

    # Validate metadata JSON if provided
    if metadata:
        try:
            json.loads(metadata)
        except json.JSONDecodeError as e:
            print(f"ERROR: metadata must be valid JSON — {e}")
            sys.exit(1)

    conn = get_connection()
    init_db(conn)
    cursor = conn.cursor()

    entity_id, created = get_or_create_entity(cursor, entity_type, name, metadata)
    conn.commit()
    conn.close()

    if created:
        print(f"CREATED entity | id={entity_id} | type={entity_type} | name={name}")
    else:
        print(f"EXISTS entity | id={entity_id} | type={entity_type} | name={name} (no change)")


def cmd_add_relationship(args):
    from_type, from_name = parse_type_name(args.from_entity, "from_entity")
    to_type, to_name = parse_type_name(args.to_entity, "to_entity")
    relationship = args.relationship.strip()

    strength = 0.5
    if args.strength is not None:
        try:
            strength = float(args.strength)
            if not (0.0 <= strength <= 1.0):
                print("ERROR: strength must be between 0.0 and 1.0")
                sys.exit(1)
        except ValueError:
            print(f"ERROR: strength must be a number, got '{args.strength}'")
            sys.exit(1)

    conn = get_connection()
    init_db(conn)
    cursor = conn.cursor()

    from_id, from_created = get_or_create_entity(cursor, from_type, from_name)
    to_id, to_created = get_or_create_entity(cursor, to_type, to_name)

    # Check if relationship already exists
    cursor.execute(
        "SELECT id, strength, evidence_count FROM relationships WHERE from_id=? AND to_id=? AND relationship=?",
        (from_id, to_id, relationship)
    )
    existing = cursor.fetchone()

    now = _now()

    if existing:
        # Update: average the new strength in, increment evidence
        new_evidence = existing['evidence_count'] + 1
        new_strength = round(
            (existing['strength'] * existing['evidence_count'] + strength) / new_evidence,
            4
        )
        # Cap to [0.0, 1.0]
        new_strength = max(0.0, min(1.0, new_strength))
        cursor.execute(
            "UPDATE relationships SET strength=?, evidence_count=?, last_updated=? WHERE id=?",
            (new_strength, new_evidence, now, existing['id'])
        )
        conn.commit()
        conn.close()
        print(f"UPDATED relationship | id={existing['id']} | {from_type}:{from_name} --[{relationship}]--> {to_type}:{to_name}")
        print(f"  strength: {existing['strength']:.2f} → {new_strength:.2f} | evidence_count: {new_evidence}")
    else:
        cursor.execute(
            "INSERT INTO relationships (from_id, to_id, relationship, strength, evidence_count, last_updated) VALUES (?,?,?,?,?,?)",
            (from_id, to_id, relationship, strength, 1, now)
        )
        rel_id = cursor.lastrowid
        conn.commit()
        conn.close()
        print(f"CREATED relationship | id={rel_id} | {from_type}:{from_name} --[{relationship}]--> {to_type}:{to_name}")
        print(f"  strength: {strength:.2f} | evidence_count: 1")

    if from_created:
        print(f"  (auto-created entity: {from_type}:{from_name})")
    if to_created:
        print(f"  (auto-created entity: {to_type}:{to_name})")


def cmd_log_decision(args):
    conn = get_connection()
    init_db(conn)
    cursor = conn.cursor()

    now = _now()
    cursor.execute(
        '''INSERT INTO decisions (deal_id, session, timestamp, stage, data_used, logic_applied, action_taken, outcome)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')''',
        (args.deal_id, args.session, now, args.stage, args.data_used, args.logic_applied, args.action_taken)
    )
    decision_id = cursor.lastrowid
    conn.commit()
    conn.close()

    print(f"LOGGED decision | id={decision_id} | deal_id={args.deal_id} | session={args.session} | stage={args.stage}")
    print(f"  data_used:     {args.data_used}")
    print(f"  logic_applied: {args.logic_applied}")
    print(f"  action_taken:  {args.action_taken}")
    print(f"  outcome:       pending")
    print(f"  timestamp:     {now}")


def cmd_query_similar(args):
    entity_type, name = parse_type_name(args.entity)

    conn = get_connection()
    init_db(conn)
    cursor = conn.cursor()

    # Find the entity
    cursor.execute("SELECT id FROM entities WHERE type=? AND name=?", (entity_type, name))
    row = cursor.fetchone()
    if not row:
        print(f"NOT FOUND: {entity_type}:{name}")
        print("Tip: use 'add-entity' to register it first.")
        conn.close()
        sys.exit(1)

    entity_id = row['id']

    # Get all relationships FROM this entity
    cursor.execute('''
        SELECT r.relationship, r.strength, r.evidence_count,
               e.type AS to_type, e.name AS to_name, e.metadata
        FROM relationships r
        JOIN entities e ON e.id = r.to_id
        WHERE r.from_id = ?
        ORDER BY r.strength DESC, r.evidence_count DESC
    ''', (entity_id,))
    outgoing = cursor.fetchall()

    # Get all relationships TO this entity
    cursor.execute('''
        SELECT r.relationship, r.strength, r.evidence_count,
               e.type AS from_type, e.name AS from_name, e.metadata
        FROM relationships r
        JOIN entities e ON e.id = r.from_id
        WHERE r.to_id = ?
        ORDER BY r.strength DESC, r.evidence_count DESC
    ''', (entity_id,))
    incoming = cursor.fetchall()

    conn.close()

    print(f"\n=== SIMILAR / CONNECTED: {entity_type.upper()}:{name} ===\n")

    if not outgoing and not incoming:
        print("No relationships found. Use 'add-relationship' to build the graph.")
        return

    if outgoing:
        print(f"--- Outgoing relationships ({len(outgoing)}) ---")
        for r in outgoing:
            badge = strength_badge(r['strength'], r['evidence_count'])
            meta = f" | metadata: {r['metadata']}" if r['metadata'] else ""
            print(f"  --[{r['relationship']}]--> {r['to_type']}:{r['to_name']}")
            print(f"    strength: {badge} | evidence: {r['evidence_count']}{meta}")
        print()

    if incoming:
        print(f"--- Incoming relationships ({len(incoming)}) ---")
        for r in incoming:
            badge = strength_badge(r['strength'], r['evidence_count'])
            meta = f" | metadata: {r['metadata']}" if r['metadata'] else ""
            print(f"  {r['from_type']}:{r['from_name']} --[{r['relationship']}]-->")
            print(f"    strength: {badge} | evidence: {r['evidence_count']}{meta}")
        print()


def cmd_query_playbook(args):
    persona = args.persona.strip()

    conn = get_connection()
    init_db(conn)
    cursor = conn.cursor()

    # Find the persona entity
    cursor.execute("SELECT id FROM entities WHERE type='persona' AND name=?", (persona,))
    row = cursor.fetchone()

    print(f"\n=== PLAYBOOK: {persona.upper()} ===\n")

    if not row:
        print(f"Persona '{persona}' not found in graph.")
        print("Tip: use 'add-entity persona {name}' then build relationships via 'add-relationship'.")
        conn.close()
        return

    persona_id = row['id']

    # Best angles (angle --responds_to_angle--> persona or persona --responds_to--> angle)
    cursor.execute('''
        SELECT e.name AS angle_name, r.strength, r.evidence_count, r.relationship
        FROM relationships r
        JOIN entities e ON e.id = r.from_id
        WHERE r.to_id = ? AND e.type = 'angle'
        ORDER BY r.strength DESC, r.evidence_count DESC
    ''', (persona_id,))
    angles_incoming = cursor.fetchall()

    cursor.execute('''
        SELECT e.name AS angle_name, r.strength, r.evidence_count, r.relationship
        FROM relationships r
        JOIN entities e ON e.id = r.to_id
        WHERE r.from_id = ? AND e.type = 'angle'
        ORDER BY r.strength DESC, r.evidence_count DESC
    ''', (persona_id,))
    angles_outgoing = cursor.fetchall()

    # Common objections
    cursor.execute('''
        SELECT e.name AS obj_name, r.strength, r.evidence_count, r.relationship
        FROM relationships r
        JOIN entities e ON e.id = r.to_id
        WHERE r.from_id = ? AND e.type = 'objection'
        ORDER BY r.evidence_count DESC, r.strength DESC
    ''', (persona_id,))
    objections = cursor.fetchall()

    # Winning frameworks
    cursor.execute('''
        SELECT e.name AS fw_name, r.strength, r.evidence_count, r.relationship
        FROM relationships r
        JOIN entities e ON e.id = r.to_id
        WHERE r.from_id = ? AND e.type = 'framework'
        ORDER BY r.strength DESC, r.evidence_count DESC
    ''', (persona_id,))
    frameworks = cursor.fetchall()

    # Case studies that worked
    cursor.execute('''
        SELECT e.name AS cs_name, r.strength, r.evidence_count, r.relationship
        FROM relationships r
        JOIN entities e ON e.id = r.to_id
        WHERE r.from_id = ? AND e.type = 'case_study'
        ORDER BY r.strength DESC, r.evidence_count DESC
    ''', (persona_id,))
    case_studies = cursor.fetchall()

    all_angles = list(angles_incoming) + list(angles_outgoing)
    # Deduplicate by angle_name keeping highest strength
    seen = {}
    for a in all_angles:
        if a['angle_name'] not in seen or a['strength'] > seen[a['angle_name']]['strength']:
            seen[a['angle_name']] = a
    all_angles = sorted(seen.values(), key=lambda x: (x['strength'], x['evidence_count']), reverse=True)

    if all_angles:
        print("BEST ANGLES (ranked by strength):")
        for i, a in enumerate(all_angles, 1):
            badge = strength_badge(a['strength'], a['evidence_count'])
            auto = " *** AUTO-RECOMMEND ***" if a['strength'] >= 0.8 and a['evidence_count'] >= 5 else ""
            print(f"  {i}. {a['angle_name']} | {badge}{auto}")
        print()
    else:
        print("BEST ANGLES: none recorded yet\n")

    if objections:
        print("COMMON OBJECTIONS (ranked by frequency):")
        for i, o in enumerate(objections, 1):
            badge = strength_badge(o['strength'], o['evidence_count'])
            flag = " [REVIEW — LOW STRENGTH]" if o['strength'] < 0.2 and o['evidence_count'] >= 5 else ""
            print(f"  {i}. {o['obj_name']} | {badge} | occurrences: {o['evidence_count']}{flag}")
        print()
    else:
        print("COMMON OBJECTIONS: none recorded yet\n")

    if frameworks:
        print("WINNING FRAMEWORKS (ranked by strength):")
        for i, f in enumerate(frameworks, 1):
            badge = strength_badge(f['strength'], f['evidence_count'])
            auto = " *** AUTO-PROMOTE CANDIDATE ***" if f['strength'] >= 0.8 and f['evidence_count'] >= 5 else ""
            print(f"  {i}. {f['fw_name']} | {badge}{auto}")
        print()
    else:
        print("WINNING FRAMEWORKS: none recorded yet\n")

    if case_studies:
        print("RELEVANT CASE STUDIES (ranked by strength):")
        for i, cs in enumerate(case_studies, 1):
            badge = strength_badge(cs['strength'], cs['evidence_count'])
            print(f"  {i}. {cs['cs_name']} | {badge}")
        print()
    else:
        print("RELEVANT CASE STUDIES: none recorded yet\n")

    conn.close()


def cmd_query_decision_chain(args):
    deal_id = args.deal_id

    conn = get_connection()
    init_db(conn)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM decisions WHERE deal_id=? ORDER BY timestamp ASC",
        (deal_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    print(f"\n=== DECISION CHAIN: deal_id={deal_id} ===\n")

    if not rows:
        print(f"No decisions logged for deal_id={deal_id}.")
        print("Tip: use 'log-decision' after each key action on this deal.")
        return

    pending = sum(1 for r in rows if r['outcome'] == 'pending')
    won = sum(1 for r in rows if r['outcome'] == 'won')
    lost = sum(1 for r in rows if r['outcome'] == 'lost')

    print(f"Total decisions: {len(rows)} | pending: {pending} | won: {won} | lost: {lost}\n")

    for r in rows:
        outcome_label = r['outcome'].upper() if r['outcome'] != 'pending' else 'PENDING'
        print(f"[{r['timestamp']}] Session {r['session']} | Stage: {r['stage']} | Outcome: {outcome_label}")
        print(f"  Data used:     {r['data_used']}")
        print(f"  Logic applied: {r['logic_applied']}")
        print(f"  Action taken:  {r['action_taken']}")
        if r['outcome_date']:
            print(f"  Outcome date:  {r['outcome_date']}")
        print()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Graph / Decision Ontology — Sprites.ai Sales Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python knowledge_graph.py add-entity persona "agency_owner"
  python knowledge_graph.py add-entity angle "time-savings"
  python knowledge_graph.py add-entity objection "too expensive"
  python knowledge_graph.py add-relationship "persona:agency_owner" responds_to "angle:time-savings" 0.7
  python knowledge_graph.py add-relationship "persona:agency_owner" raises "objection:too expensive" 0.6
  python knowledge_graph.py log-decision 12345 6 "cold_outreach" "PATTERNS.md,Pipedrive" "CCQ+time-savings angle" "Sent cold email v1"
  python knowledge_graph.py query-similar "prospect:John Smith"
  python knowledge_graph.py query-playbook "agency_owner"
  python knowledge_graph.py query-decision-chain 12345
        """
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    # add-entity
    p_ae = subparsers.add_parser('add-entity', help='Register an entity in the ontology')
    p_ae.add_argument('type', help=f'Entity type: {", ".join(sorted(VALID_ENTITY_TYPES))}')
    p_ae.add_argument('name', help='Entity name')
    p_ae.add_argument('metadata', nargs='?', default=None, help='Optional JSON metadata string')

    # add-relationship
    p_ar = subparsers.add_parser('add-relationship', help='Add or update a relationship between two entities')
    p_ar.add_argument('from_entity', help='Source entity in format type:name')
    p_ar.add_argument('relationship', help='Relationship label (e.g. responds_to, raises, countered_by, won_with)')
    p_ar.add_argument('to_entity', help='Target entity in format type:name')
    p_ar.add_argument('strength', nargs='?', default=None, help='Initial strength 0.0-1.0 (default 0.5)')

    # log-decision
    p_ld = subparsers.add_parser('log-decision', help='Log a decision made on a deal')
    p_ld.add_argument('deal_id', type=int, help='Pipedrive deal ID')
    p_ld.add_argument('session', type=int, help='Session number')
    p_ld.add_argument('stage', help='Deal stage at time of decision')
    p_ld.add_argument('data_used', help='What data informed the decision')
    p_ld.add_argument('logic_applied', help='What logic/framework was applied')
    p_ld.add_argument('action_taken', help='What action was executed')

    # query-similar
    p_qs = subparsers.add_parser('query-similar', help='Find entities connected to this one, ranked by relationship strength')
    p_qs.add_argument('entity', help='Entity in format type:name')

    # query-playbook
    p_qp = subparsers.add_parser('query-playbook', help='Best angles, common objections, winning frameworks for a persona')
    p_qp.add_argument('persona', help='Persona name (e.g. agency_owner, solo_founder, pe_rollup)')

    # query-decision-chain
    p_qd = subparsers.add_parser('query-decision-chain', help='Full decision history for a deal')
    p_qd.add_argument('deal_id', type=int, help='Pipedrive deal ID')

    args = parser.parse_args()

    # Initialize DB regardless of command (idempotent)
    conn = get_connection()
    init_db(conn)
    conn.close()

    dispatch = {
        'add-entity': cmd_add_entity,
        'add-relationship': cmd_add_relationship,
        'log-decision': cmd_log_decision,
        'query-similar': cmd_query_similar,
        'query-playbook': cmd_query_playbook,
        'query-decision-chain': cmd_query_decision_chain,
    }

    dispatch[args.command](args)


if __name__ == '__main__':
    main()
