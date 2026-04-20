"""Tests: every wired INSERT site writes a non-null tenant_id.

Each test inserts one row via the SDK function and asserts that
the resulting DB row has tenant_id IS NOT NULL.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixture: isolated brain_dir with a known tenant UUID
# ---------------------------------------------------------------------------

TEST_TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture()
def brain_dir(tmp_path: Path) -> Path:
    d = tmp_path / "brain"
    d.mkdir()
    # Plant a deterministic tenant UUID so assertions are unambiguous.
    (d / ".tenant_id").write_text(TEST_TENANT, encoding="utf-8")
    return d


@pytest.fixture()
def db_path(brain_dir: Path) -> Path:
    return brain_dir / "system.db"


# ---------------------------------------------------------------------------
# Helper: create tables needed by each module (mimics what run_migrations does)
# ---------------------------------------------------------------------------

def _make_rule_provenance(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS rule_provenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL,
            correction_event_id TEXT,
            session INTEGER,
            timestamp TEXT NOT NULL,
            user_context TEXT
        )"""
    )
    conn.commit()
    conn.close()


def _make_rule_relationships(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS rule_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_a_id TEXT NOT NULL,
            rule_b_id TEXT NOT NULL,
            relationship TEXT NOT NULL,
            confidence REAL,
            detected_at TEXT
        )"""
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# audit.py — rule_provenance
# ---------------------------------------------------------------------------


def test_write_provenance_sets_tenant_id(brain_dir: Path, db_path: Path) -> None:
    _make_rule_provenance(db_path)
    from gradata.audit import write_provenance

    write_provenance(
        db_path,
        rule_id="r_test",
        correction_event_id="evt_001",
        session=1,
        timestamp="2026-04-17T00:00:00Z",
        user_context="pytest",
    )

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT tenant_id FROM rule_provenance WHERE rule_id = 'r_test'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == TEST_TENANT


# ---------------------------------------------------------------------------
# meta_rules_storage.py — meta_rules
# ---------------------------------------------------------------------------


def test_save_meta_rules_sets_tenant_id(brain_dir: Path, db_path: Path) -> None:
    from gradata._types import RuleTransferScope
    from gradata.enhancements.meta_rules import MetaRule
    from gradata.enhancements.meta_rules_storage import save_meta_rules

    meta = MetaRule(
        id="m1",
        principle="Test principle",
        source_categories=["CAT"],
        source_lesson_ids=["l1"],
        confidence=0.8,
        created_session=1,
        last_validated_session=1,
        scope={},
        examples=[],
        context_weights={"default": 1.0},
        applies_when=[],
        never_when=[],
        transfer_scope=RuleTransferScope.PERSONAL,
        source="deterministic",
    )
    save_meta_rules(db_path, [meta])

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT tenant_id FROM meta_rules WHERE id = 'm1'").fetchone()
    conn.close()
    assert row is not None
    assert row[0] == TEST_TENANT


# ---------------------------------------------------------------------------
# meta_rules_storage.py — correction_patterns (single)
# ---------------------------------------------------------------------------


def test_upsert_correction_pattern_sets_tenant_id(brain_dir: Path, db_path: Path) -> None:
    from gradata.enhancements.meta_rules_storage import upsert_correction_pattern

    upsert_correction_pattern(
        db_path,
        pattern_hash="hash_abc",
        category="DRAFTING",
        representative_text="test pattern",
        session_id=1,
        severity="minor",
    )

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT tenant_id FROM correction_patterns WHERE pattern_hash = 'hash_abc'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == TEST_TENANT


# ---------------------------------------------------------------------------
# meta_rules_storage.py — correction_patterns (batch)
# ---------------------------------------------------------------------------


def test_upsert_correction_patterns_batch_sets_tenant_id(
    brain_dir: Path, db_path: Path
) -> None:
    from gradata.enhancements.meta_rules_storage import upsert_correction_patterns_batch

    upsert_correction_patterns_batch(
        db_path,
        [("hash_batch1", "PROCESS", "batch pattern", 2, "major")],
    )

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT tenant_id FROM correction_patterns WHERE pattern_hash = 'hash_batch1'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == TEST_TENANT


# ---------------------------------------------------------------------------
# loop_intelligence.py — activity_log
# ---------------------------------------------------------------------------


def test_log_activity_sets_tenant_id(brain_dir: Path, db_path: Path) -> None:
    from gradata.enhancements.scoring.loop_intelligence import log_activity

    log_activity(
        db_path,
        activity_type="email_sent",
        prospect="Test Prospect",
        emit_event=False,
    )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT tenant_id FROM activity_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["tenant_id"] == TEST_TENANT


# ---------------------------------------------------------------------------
# loop_intelligence.py — prep_outcomes (log_prep)
# ---------------------------------------------------------------------------


def test_log_prep_sets_tenant_id(brain_dir: Path, db_path: Path) -> None:
    from gradata.enhancements.scoring.loop_intelligence import log_prep

    log_prep(db_path, prospect="Alice", prep_type="research", prep_level=2)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT tenant_id FROM prep_outcomes ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["tenant_id"] == TEST_TENANT


# ---------------------------------------------------------------------------
# loop_intelligence.py — prep_outcomes (log_outcome fallback INSERT)
# ---------------------------------------------------------------------------


def test_log_outcome_fallback_sets_tenant_id(brain_dir: Path, db_path: Path) -> None:
    from gradata.enhancements.scoring.loop_intelligence import log_outcome

    # No existing prep row -> triggers the fallback INSERT path
    result = log_outcome(db_path, prospect="Bob", prep_type="personalization",
                         outcome="reply", days=3)
    assert result["linked_to_prep"] is False

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT tenant_id FROM prep_outcomes WHERE prospect = 'Bob'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["tenant_id"] == TEST_TENANT


# ---------------------------------------------------------------------------
# rule_graph.py — rule_relationships
# ---------------------------------------------------------------------------


def test_store_relationship_sets_tenant_id(brain_dir: Path, db_path: Path) -> None:
    _make_rule_relationships(db_path)
    from gradata.rules.rule_graph import RuleRelationType, store_relationship

    store_relationship(db_path, "rA", "rB", RuleRelationType.REINFORCES, confidence=0.75)

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT tenant_id FROM rule_relationships WHERE rule_a_id = 'rA'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == TEST_TENANT


# ---------------------------------------------------------------------------
# _query.py — brain_fts_content (fts_index)
# ---------------------------------------------------------------------------


def test_fts_index_sets_tenant_id(brain_dir: Path, db_path: Path) -> None:
    from gradata._paths import BrainContext
    from gradata._query import fts_index

    ctx = BrainContext.from_brain_dir(brain_dir)
    fts_index("test/source.md", "general", "hello world", embed_date="2026-04-17", ctx=ctx)

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT tenant_id FROM brain_fts_content WHERE source = 'test/source.md'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == TEST_TENANT


# ---------------------------------------------------------------------------
# _query.py — brain_fts_content (fts_index_batch)
# ---------------------------------------------------------------------------


def test_fts_index_batch_sets_tenant_id(brain_dir: Path, db_path: Path) -> None:
    from gradata._paths import BrainContext
    from gradata._query import fts_index_batch

    ctx = BrainContext.from_brain_dir(brain_dir)
    fts_index_batch(
        [{"source": "batch/file.md", "file_type": "general", "text": "batch text", "embed_date": "2026-04-17"}],
        ctx=ctx,
    )

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT tenant_id FROM brain_fts_content WHERE source = 'batch/file.md'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == TEST_TENANT
