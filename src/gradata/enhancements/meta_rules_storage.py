"""
Meta-Rule SQLite Persistence — load/save for meta_rules and super_meta_rules tables.
=====================================================================================
All database I/O for meta-rules lives here.  Core logic and discovery live in
``meta_rules.py``; tier-2/3 super-meta-rule logic lives in ``super_meta_rules.py``.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

from gradata._types import RuleTransferScope
from gradata.enhancements.meta_rules import TIER_SUPER_META, MetaRule, SuperMetaRule

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Meta-Rule DDL
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS meta_rules (
    id TEXT PRIMARY KEY,
    principle TEXT NOT NULL,
    source_categories TEXT,
    source_lesson_ids TEXT,
    confidence REAL,
    created_session INTEGER,
    last_validated_session INTEGER,
    scope TEXT,
    examples TEXT,
    context_weights TEXT
);
"""

_ADD_CONTEXT_WEIGHTS_SQL = (
    "ALTER TABLE meta_rules ADD COLUMN context_weights TEXT"
)

_ADD_APPLIES_WHEN_SQL = (
    "ALTER TABLE meta_rules ADD COLUMN applies_when TEXT"
)

_ADD_NEVER_WHEN_SQL = (
    "ALTER TABLE meta_rules ADD COLUMN never_when TEXT"
)

_ADD_TRANSFER_SCOPE_SQL = (
    "ALTER TABLE meta_rules ADD COLUMN transfer_scope TEXT DEFAULT 'personal'"
)


def ensure_table(db_path: str | Path) -> None:
    """Create the meta_rules table if it does not exist.

    Also migrates existing tables by adding the ``context_weights``
    column when it is missing (backward-compatible upgrade).

    Args:
        db_path: Path to the SQLite database file.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(_CREATE_TABLE_SQL)
        # Migrate: add columns if table existed before this version
        for stmt in (_ADD_CONTEXT_WEIGHTS_SQL, _ADD_APPLIES_WHEN_SQL, _ADD_NEVER_WHEN_SQL, _ADD_TRANSFER_SCOPE_SQL):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # Column already exists
        conn.commit()
    finally:
        conn.close()


def save_meta_rules(db_path: str | Path, metas: list[MetaRule]) -> int:
    """Persist meta-rules to system.db, replacing all existing rows.

    Args:
        db_path: Path to the SQLite database file.
        metas: Meta-rules to save.

    Returns:
        Number of meta-rules saved.
    """
    ensure_table(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM meta_rules")
        for meta in metas:
            conn.execute(
                """INSERT INTO meta_rules
                   (id, principle, source_categories, source_lesson_ids,
                    confidence, created_session, last_validated_session,
                    scope, examples, context_weights, applies_when, never_when,
                    transfer_scope)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    meta.id,
                    meta.principle,
                    json.dumps(meta.source_categories),
                    json.dumps(meta.source_lesson_ids),
                    meta.confidence,
                    meta.created_session,
                    meta.last_validated_session,
                    json.dumps(meta.scope),
                    json.dumps(meta.examples),
                    json.dumps(meta.context_weights),
                    json.dumps(meta.applies_when),
                    json.dumps(meta.never_when),
                    meta.transfer_scope.value,
                ),
            )
        conn.commit()
        return len(metas)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_meta_rules(db_path: str | Path) -> list[MetaRule]:
    """Load meta-rules from system.db.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of :class:`MetaRule` objects, sorted by confidence
        descending.  Empty list if the table does not exist.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        # Check if table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_rules'"
        )
        if not cursor.fetchone():
            return []

        rows = conn.execute(
            """SELECT id, principle, source_categories, source_lesson_ids,
                      confidence, created_session, last_validated_session,
                      scope, examples, context_weights, applies_when, never_when,
                      transfer_scope
               FROM meta_rules
               ORDER BY confidence DESC"""
        ).fetchall()

        # Map stored strings back to enum values
        _SCOPE_MAP = {s.value: s for s in RuleTransferScope}

        metas: list[MetaRule] = []
        for row in rows:
            metas.append(MetaRule(
                id=row[0],
                principle=row[1],
                source_categories=json.loads(row[2]) if row[2] else [],
                source_lesson_ids=json.loads(row[3]) if row[3] else [],
                confidence=row[4] or 0.0,
                created_session=row[5] or 0,
                last_validated_session=row[6] or 0,
                scope=json.loads(row[7]) if row[7] else {},
                examples=json.loads(row[8]) if row[8] else [],
                context_weights=json.loads(row[9]) if row[9] else {"default": 1.0},
                applies_when=json.loads(row[10]) if row[10] else [],
                never_when=json.loads(row[11]) if row[11] else [],
                transfer_scope=_SCOPE_MAP.get(row[12], RuleTransferScope.PERSONAL) if row[12] else RuleTransferScope.PERSONAL,
            ))
        return metas
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Super-Meta-Rule DDL
# ---------------------------------------------------------------------------

_CREATE_SUPER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS super_meta_rules (
    id TEXT PRIMARY KEY,
    abstraction TEXT NOT NULL,
    source_meta_rule_ids TEXT,
    tier INTEGER,
    confidence REAL,
    context_weights TEXT,
    source_categories TEXT,
    created_session INTEGER,
    last_validated_session INTEGER,
    scope TEXT,
    examples TEXT
);
"""

_ADD_SUPER_APPLIES_WHEN_SQL = (
    "ALTER TABLE super_meta_rules ADD COLUMN applies_when TEXT"
)

_ADD_SUPER_NEVER_WHEN_SQL = (
    "ALTER TABLE super_meta_rules ADD COLUMN never_when TEXT"
)

_ADD_SUPER_TRANSFER_SCOPE_SQL = (
    "ALTER TABLE super_meta_rules ADD COLUMN transfer_scope TEXT DEFAULT 'personal'"
)


def ensure_super_table(db_path: str | Path) -> None:
    """Create the super_meta_rules table if it does not exist.

    Also migrates existing tables by adding ``applies_when`` and
    ``never_when`` columns when missing (backward-compatible upgrade).

    Args:
        db_path: Path to the SQLite database file.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(_CREATE_SUPER_TABLE_SQL)
        for stmt in (_ADD_SUPER_APPLIES_WHEN_SQL, _ADD_SUPER_NEVER_WHEN_SQL, _ADD_SUPER_TRANSFER_SCOPE_SQL):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # Column already exists
        conn.commit()
    finally:
        conn.close()


def save_super_meta_rules(db_path: str | Path, supers: list[SuperMetaRule]) -> int:
    """Persist super-meta-rules to system.db, replacing all existing rows.

    Args:
        db_path: Path to the SQLite database file.
        supers: Super-meta-rules to save (tier 2 and 3).

    Returns:
        Number of super-meta-rules saved.
    """
    ensure_super_table(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM super_meta_rules")
        for s in supers:
            conn.execute(
                """INSERT INTO super_meta_rules
                   (id, abstraction, source_meta_rule_ids, tier,
                    confidence, context_weights, source_categories,
                    created_session, last_validated_session, scope, examples,
                    applies_when, never_when, transfer_scope)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    s.id,
                    s.abstraction,
                    json.dumps(s.source_meta_rule_ids),
                    s.tier,
                    s.confidence,
                    json.dumps(s.context_weights),
                    json.dumps(s.source_categories),
                    s.created_session,
                    s.last_validated_session,
                    json.dumps(s.scope),
                    json.dumps(s.examples),
                    json.dumps(s.applies_when),
                    json.dumps(s.never_when),
                    s.transfer_scope.value,
                ),
            )
        conn.commit()
        return len(supers)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_super_meta_rules(db_path: str | Path) -> list[SuperMetaRule]:
    """Load super-meta-rules from system.db.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of :class:`SuperMetaRule` objects, sorted by tier descending
        then confidence descending.  Empty list if table does not exist.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='super_meta_rules'"
        )
        if not cursor.fetchone():
            return []

        rows = conn.execute(
            """SELECT id, abstraction, source_meta_rule_ids, tier,
                      confidence, context_weights, source_categories,
                      created_session, last_validated_session, scope, examples,
                      applies_when, never_when, transfer_scope
               FROM super_meta_rules
               ORDER BY tier DESC, confidence DESC"""
        ).fetchall()

        _SCOPE_MAP = {s.value: s for s in RuleTransferScope}

        supers: list[SuperMetaRule] = []
        for row in rows:
            supers.append(SuperMetaRule(
                id=row[0],
                abstraction=row[1],
                source_meta_rule_ids=json.loads(row[2]) if row[2] else [],
                tier=row[3] or TIER_SUPER_META,
                confidence=row[4] or 0.0,
                context_weights=json.loads(row[5]) if row[5] else {"default": 1.0},
                source_categories=json.loads(row[6]) if row[6] else [],
                created_session=row[7] or 0,
                last_validated_session=row[8] or 0,
                scope=json.loads(row[9]) if row[9] else {},
                examples=json.loads(row[10]) if row[10] else [],
                applies_when=json.loads(row[11]) if row[11] else [],
                never_when=json.loads(row[12]) if row[12] else [],
                transfer_scope=_SCOPE_MAP.get(row[13], RuleTransferScope.PERSONAL) if row[13] else RuleTransferScope.PERSONAL,
            ))
        return supers
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Correction Pattern Tracking (cross-session)
# ---------------------------------------------------------------------------

# Severity weights for pattern graduation scoring (different scale from
# self_improvement.SEVERITY_WEIGHTS which is for confidence-delta math)
PATTERN_SEVERITY_WEIGHTS = {"major": 2.0, "rewrite": 2.5, "moderate": 1.5, "minor": 1.0, "trivial": 0.5}


def ensure_pattern_table(db_path: str | Path) -> None:
    """Create correction_patterns table if it doesn't exist."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS correction_patterns (
                pattern_hash TEXT NOT NULL,
                category TEXT NOT NULL,
                representative_text TEXT NOT NULL,
                session_id INTEGER NOT NULL,
                severity TEXT DEFAULT 'minor',
                severity_weight REAL DEFAULT 1.0,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(pattern_hash, session_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_hash
            ON correction_patterns(pattern_hash)
        """)
        conn.commit()
    finally:
        conn.close()


def upsert_correction_pattern(
    db_path: str | Path,
    pattern_hash: str,
    category: str,
    representative_text: str,
    session_id: int,
    severity: str = "minor",
) -> None:
    """Record a correction pattern occurrence for a session."""
    ensure_pattern_table(db_path)
    weight = PATTERN_SEVERITY_WEIGHTS.get(severity, 1.0)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT INTO correction_patterns
               (pattern_hash, category, representative_text, session_id, severity, severity_weight)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(pattern_hash, session_id) DO UPDATE SET
                 severity = CASE WHEN excluded.severity_weight > severity_weight
                                THEN excluded.severity ELSE severity END,
                 severity_weight = MAX(severity_weight, excluded.severity_weight),
                 representative_text = excluded.representative_text
            """,
            (pattern_hash, category, representative_text, session_id, severity, weight),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_correction_patterns_batch(
    db_path: str | Path,
    patterns: list[tuple[str, str, str, int, str]],
) -> int:
    """Batch upsert multiple correction patterns in one connection.

    Each tuple: (pattern_hash, category, representative_text, session_id, severity).
    Returns number of rows upserted.
    """
    if not patterns:
        return 0
    ensure_pattern_table(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        rows = []
        for pattern_hash, category, representative_text, session_id, severity in patterns:
            weight = PATTERN_SEVERITY_WEIGHTS.get(severity, 1.0)
            rows.append((pattern_hash, category, representative_text, session_id, severity, weight))
        conn.executemany(
            """INSERT INTO correction_patterns
               (pattern_hash, category, representative_text, session_id, severity, severity_weight)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(pattern_hash, session_id) DO UPDATE SET
                 severity = CASE WHEN excluded.severity_weight > severity_weight
                                THEN excluded.severity ELSE severity END,
                 severity_weight = MAX(severity_weight, excluded.severity_weight),
                 representative_text = excluded.representative_text
            """,
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def query_graduation_candidates(
    db_path: str | Path,
    min_sessions: int = 2,
    min_score: float = 3.0,
) -> list[dict]:
    """Find correction patterns ready for meta-rule graduation.

    Returns patterns where:
    - Distinct sessions >= min_sessions
    - Sum of severity weights >= min_score
    """
    ensure_pattern_table(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """WITH representative AS (
                 SELECT
                   pattern_hash,
                   category,
                   representative_text,
                   ROW_NUMBER() OVER (PARTITION BY pattern_hash ORDER BY created_at DESC) AS rn
                 FROM correction_patterns
               ),
               aggregates AS (
                 SELECT
                   pattern_hash,
                   COUNT(DISTINCT session_id) AS distinct_sessions,
                   SUM(severity_weight) AS weighted_score,
                   MIN(created_at) AS first_seen,
                   MAX(created_at) AS last_seen,
                   GROUP_CONCAT(DISTINCT session_id) AS session_ids
                 FROM correction_patterns
                 GROUP BY pattern_hash
                 HAVING COUNT(DISTINCT session_id) >= ?
                    AND SUM(severity_weight) >= ?
               )
               SELECT
                 r.pattern_hash,
                 r.category,
                 r.representative_text,
                 a.distinct_sessions,
                 a.weighted_score,
                 a.first_seen,
                 a.last_seen,
                 a.session_ids
               FROM representative r
               INNER JOIN aggregates a ON r.pattern_hash = a.pattern_hash
               WHERE r.rn = 1
               ORDER BY a.weighted_score DESC
            """,
            (min_sessions, min_score),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
