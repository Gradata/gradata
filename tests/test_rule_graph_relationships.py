"""Tests for rule graph typed relationships (Gap 2).

TDD tests for REINFORCES, CONTRADICTS, SPECIALIZES, GENERALIZES
relationship detection and querying.
"""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gradata.rules.rule_graph import (
    RuleGraph,
    RuleRelationType,
    detect_relationship,
    get_related_rules,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path):
    """Create a temp SQLite DB with the rule_relationships table."""
    path = tmp_path / "system.db"
    conn = sqlite3.connect(str(path))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS rule_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_a_id TEXT NOT NULL,
            rule_b_id TEXT NOT NULL,
            relationship TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            detected_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def graph(tmp_path):
    """Create a RuleGraph with no persisted state."""
    return RuleGraph(path=tmp_path / "rule_graph.json")


# ---------------------------------------------------------------------------
# RuleRelationType enum
# ---------------------------------------------------------------------------


class TestRuleRelationType:
    def test_enum_values(self):
        assert RuleRelationType.REINFORCES.value == "reinforces"
        assert RuleRelationType.CONTRADICTS.value == "contradicts"
        assert RuleRelationType.SPECIALIZES.value == "specializes"
        assert RuleRelationType.GENERALIZES.value == "generalizes"

    def test_all_types_present(self):
        assert len(RuleRelationType) == 4


# ---------------------------------------------------------------------------
# detect_relationship
# ---------------------------------------------------------------------------


class TestRelationshipDetection:
    def test_detects_reinforces(self):
        """Two rules with same category and overlapping keywords -> REINFORCES."""
        rule_a = {
            "id": "r1",
            "category": "TONE",
            "description": "Keep professional tone in email drafts",
            "path": "TONE/email",
        }
        rule_b = {
            "id": "r2",
            "category": "TONE",
            "description": "Maintain professional tone in email drafts",
            "path": "TONE/email",
        }
        result = detect_relationship(rule_a, rule_b)
        assert result == RuleRelationType.REINFORCES

    def test_detects_contradicts(self):
        """Opposite polarity on same topic -> CONTRADICTS."""
        rule_a = {
            "id": "r1",
            "category": "TONE",
            "description": "Always use formal language in emails",
            "path": "TONE/email",
        }
        rule_b = {
            "id": "r2",
            "category": "TONE",
            "description": "Never use formal language in emails",
            "path": "TONE/email",
        }
        result = detect_relationship(rule_a, rule_b)
        assert result == RuleRelationType.CONTRADICTS

    def test_detects_contradicts_action_opposites(self):
        """Action opposites (include vs exclude) -> CONTRADICTS."""
        rule_a = {
            "id": "r1",
            "category": "FORMAT",
            "description": "Include pricing details in proposals",
            "path": "FORMAT/proposals",
        }
        rule_b = {
            "id": "r2",
            "category": "FORMAT",
            "description": "Exclude pricing details from proposals",
            "path": "FORMAT/proposals",
        }
        result = detect_relationship(rule_a, rule_b)
        assert result == RuleRelationType.CONTRADICTS

    def test_detects_specializes(self):
        """Rule A's path is a child of rule B's path -> SPECIALIZES."""
        rule_a = {
            "id": "r1",
            "category": "TONE",
            "description": "Use casual tone in sales email drafts",
            "path": "TONE/sales/email_draft",
        }
        rule_b = {
            "id": "r2",
            "category": "TONE",
            "description": "Set appropriate tone in sales contexts",
            "path": "TONE/sales",
        }
        result = detect_relationship(rule_a, rule_b)
        assert result == RuleRelationType.SPECIALIZES

    def test_detects_generalizes(self):
        """Rule A's path is a parent of rule B's path -> GENERALIZES."""
        rule_a = {
            "id": "r1",
            "category": "TONE",
            "description": "Set appropriate tone in sales contexts",
            "path": "TONE/sales",
        }
        rule_b = {
            "id": "r2",
            "category": "TONE",
            "description": "Use casual tone in sales email drafts",
            "path": "TONE/sales/email_draft",
        }
        result = detect_relationship(rule_a, rule_b)
        assert result == RuleRelationType.GENERALIZES

    def test_returns_none_for_unrelated(self):
        """Different categories, no keyword overlap -> None."""
        rule_a = {
            "id": "r1",
            "category": "TONE",
            "description": "Keep email tone professional",
            "path": "TONE/email",
        }
        rule_b = {
            "id": "r2",
            "category": "WORKFLOW",
            "description": "Run tests before committing code",
            "path": "WORKFLOW/testing",
        }
        result = detect_relationship(rule_a, rule_b)
        assert result is None

    def test_specializes_takes_priority_over_reinforces(self):
        """When path is child AND keywords overlap, SPECIALIZES wins."""
        rule_a = {
            "id": "r1",
            "category": "TONE",
            "description": "Keep professional tone in sales email drafts",
            "path": "TONE/sales/email_draft",
        }
        rule_b = {
            "id": "r2",
            "category": "TONE",
            "description": "Keep professional tone in sales",
            "path": "TONE/sales",
        }
        result = detect_relationship(rule_a, rule_b)
        assert result == RuleRelationType.SPECIALIZES

    def test_contradicts_takes_priority_over_reinforces(self):
        """When contradiction detected, it wins over keyword overlap."""
        rule_a = {
            "id": "r1",
            "category": "FORMAT",
            "description": "Always include headers in reports",
            "path": "FORMAT/reports",
        }
        rule_b = {
            "id": "r2",
            "category": "FORMAT",
            "description": "Never include headers in reports",
            "path": "FORMAT/reports",
        }
        result = detect_relationship(rule_a, rule_b)
        assert result == RuleRelationType.CONTRADICTS

    def test_missing_path_no_crash(self):
        """Rules without path field should not crash."""
        rule_a = {
            "id": "r1",
            "category": "TONE",
            "description": "Keep professional tone in email drafts",
        }
        rule_b = {
            "id": "r2",
            "category": "TONE",
            "description": "Maintain professional tone in email drafts",
        }
        # Should still detect REINFORCES based on keywords (no path needed)
        result = detect_relationship(rule_a, rule_b)
        assert result == RuleRelationType.REINFORCES


# ---------------------------------------------------------------------------
# get_related_rules (SQLite storage + querying)
# ---------------------------------------------------------------------------


class TestGetRelatedRules:
    def _insert_relationship(self, db_path, rule_a_id, rule_b_id, relationship, confidence=0.8):
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO rule_relationships (rule_a_id, rule_b_id, relationship, confidence, detected_at) VALUES (?, ?, ?, ?, ?)",
            (
                rule_a_id,
                rule_b_id,
                relationship,
                confidence,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    def test_get_related_filters_by_type(self, db_path):
        """Query only CONTRADICTS relationships."""
        self._insert_relationship(db_path, "r1", "r2", "contradicts")
        self._insert_relationship(db_path, "r1", "r3", "reinforces")
        self._insert_relationship(db_path, "r1", "r4", "contradicts")

        results = get_related_rules(db_path, "r1", rel_type=RuleRelationType.CONTRADICTS)
        assert len(results) == 2
        ids = {r["related_rule_id"] for r in results}
        assert ids == {"r2", "r4"}

    def test_get_related_all_types(self, db_path):
        """Query all relationships for a rule."""
        self._insert_relationship(db_path, "r1", "r2", "contradicts")
        self._insert_relationship(db_path, "r1", "r3", "reinforces")

        results = get_related_rules(db_path, "r1")
        assert len(results) == 2

    def test_get_related_bidirectional(self, db_path):
        """Relationship stored as (r1, r2) should also be found when querying r2."""
        self._insert_relationship(db_path, "r1", "r2", "contradicts")

        results = get_related_rules(db_path, "r2")
        assert len(results) == 1
        assert results[0]["related_rule_id"] == "r1"

    def test_get_related_empty(self, db_path):
        """No relationships returns empty list."""
        results = get_related_rules(db_path, "nonexistent")
        assert results == []

    def test_result_includes_confidence(self, db_path):
        """Results should include confidence score."""
        self._insert_relationship(db_path, "r1", "r2", "reinforces", confidence=0.92)

        results = get_related_rules(db_path, "r1")
        assert len(results) == 1
        assert results[0]["confidence"] == pytest.approx(0.92)
        assert results[0]["relationship"] == "reinforces"


# ---------------------------------------------------------------------------
# RuleGraph.store_relationship (integration with graph class)
# ---------------------------------------------------------------------------


class TestRuleGraphStoreRelationship:
    def test_store_and_retrieve(self, db_path):
        """Store a relationship via RuleGraph and retrieve it."""
        from gradata.rules.rule_graph import store_relationship

        store_relationship(db_path, "r1", "r2", RuleRelationType.REINFORCES, confidence=0.85)

        results = get_related_rules(db_path, "r1")
        assert len(results) == 1
        assert results[0]["related_rule_id"] == "r2"
        assert results[0]["relationship"] == "reinforces"
        assert results[0]["confidence"] == pytest.approx(0.85)

    def test_store_multiple_relationships(self, db_path):
        """Store multiple relationships for one rule."""
        from gradata.rules.rule_graph import store_relationship

        store_relationship(db_path, "r1", "r2", RuleRelationType.REINFORCES)
        store_relationship(db_path, "r1", "r3", RuleRelationType.CONTRADICTS)
        store_relationship(db_path, "r1", "r4", RuleRelationType.SPECIALIZES)

        results = get_related_rules(db_path, "r1")
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class TestMigration:
    def test_rule_relationships_table_in_migrations(self):
        """The rule_relationships CREATE TABLE should be in _MIGRATIONS."""
        from gradata._migrations import _MIGRATIONS

        joined = " ".join(_MIGRATIONS)
        assert "rule_relationships" in joined
