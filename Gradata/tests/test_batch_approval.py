"""Tests for batch approval at session end (Task 4).

Tests:
- pending_promotions() returns list with rule_id/category/state
- approve_promotion() returns {approved: True}
- reject_promotion() demotes and returns {rejected: True}
- end_session returns graduated_rules key
- Not reviewing = rules persist (they already passed threshold)
"""

from __future__ import annotations

import importlib
import os
import sqlite3
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Sample lessons: 1 RULE, 1 PATTERN, 1 INSTINCT
# ---------------------------------------------------------------------------

SAMPLE_LESSONS = textwrap.dedent("""\
    # Lessons

    [2026-01-15] [RULE:0.95] DRAFTING: Never use em dashes in email prose
      Root cause: User corrected em dashes 8 times across sessions
      Fire count: 12 | Sessions since fire: 1 | Misfires: 0

    [2026-02-10] [PATTERN:0.72] ACCURACY: Always verify data before sending
      Root cause: Sent unverified stats in demo prep
      Fire count: 5 | Sessions since fire: 3 | Misfires: 1

    [2026-03-01] [INSTINCT:0.42] PROCESS: Check calendar before scheduling
      Root cause: Double-booked a meeting
      Fire count: 2 | Sessions since fire: 7 | Misfires: 0
""")


@pytest.fixture()
def brain_dir(tmp_path: Path) -> Path:
    """Create a minimal brain directory with lessons.md and system.db."""
    d = tmp_path / "test-brain"
    d.mkdir()
    (d / "lessons.md").write_text(SAMPLE_LESSONS, encoding="utf-8")

    db = d / "system.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS lesson_transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_desc TEXT NOT NULL,
            category TEXT NOT NULL,
            old_state TEXT NOT NULL,
            new_state TEXT NOT NULL,
            confidence REAL,
            fire_count INTEGER DEFAULT 0,
            session INTEGER,
            transitioned_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            session INTEGER,
            type TEXT NOT NULL,
            source TEXT,
            data_json TEXT,
            tags_json TEXT
        )"""
    )
    conn.commit()
    conn.close()
    (d / "events.jsonl").write_text("", encoding="utf-8")
    return d


@pytest.fixture()
def brain(brain_dir: Path):
    import gradata._paths as _p
    from gradata.brain import Brain

    os.environ["BRAIN_DIR"] = str(brain_dir)
    importlib.reload(_p)
    return Brain.init(
        brain_dir, name="Test", domain="Testing", embedding="local", interactive=False
    )


# ---------------------------------------------------------------------------
# pending_promotions tests
# ---------------------------------------------------------------------------


class TestPendingPromotions:
    def test_returns_list(self, brain):
        result = brain.pending_promotions()
        assert isinstance(result, list)

    def test_contains_pattern_and_rule(self, brain):
        """Should return lessons in PATTERN or RULE state."""
        result = brain.pending_promotions()
        assert len(result) == 2
        states = {r["state"] for r in result}
        assert states == {"RULE", "PATTERN"}

    def test_each_item_has_rule_id(self, brain):
        result = brain.pending_promotions()
        for item in result:
            assert "id" in item
            assert len(item["id"]) > 0

    def test_each_item_has_category(self, brain):
        result = brain.pending_promotions()
        for item in result:
            assert "category" in item
            assert item["category"] in ("DRAFTING", "ACCURACY")

    def test_each_item_has_state(self, brain):
        result = brain.pending_promotions()
        for item in result:
            assert "state" in item
            assert item["state"] in ("PATTERN", "RULE")

    def test_instinct_excluded(self, brain):
        """INSTINCT lessons should not appear in pending promotions."""
        result = brain.pending_promotions()
        for item in result:
            assert item["state"] != "INSTINCT"

    def test_empty_brain(self, tmp_path: Path):
        """Brain with no lessons returns empty list."""
        import gradata._paths as _p
        from gradata.brain import Brain

        d = tmp_path / "empty-brain"
        os.environ["BRAIN_DIR"] = str(d)
        importlib.reload(_p)
        b = Brain.init(d, name="Empty", domain="Test", embedding="local", interactive=False)
        result = b.pending_promotions()
        assert result == []


# ---------------------------------------------------------------------------
# approve_promotion tests
# ---------------------------------------------------------------------------


class TestApprovePromotion:
    def test_approve_returns_approved_true(self, brain):
        promotions = brain.pending_promotions()
        assert len(promotions) > 0
        rule_id = promotions[0]["id"]
        result = brain.approve_promotion(rule_id)
        assert result["approved"] is True

    def test_approve_nonexistent_returns_error(self, brain):
        result = brain.approve_promotion("nonexistent-id")
        assert "error" in result

    def test_approve_preserves_lesson_state(self, brain):
        """Approving a promotion should not alter the lesson's state or confidence."""
        promotions = brain.pending_promotions()
        rule_id = promotions[0]["id"]
        old_state = promotions[0]["state"]
        old_conf = promotions[0]["confidence"]

        brain.approve_promotion(rule_id)

        after = brain.pending_promotions()
        matched = [r for r in after if r["id"] == rule_id]
        assert len(matched) == 1
        assert matched[0]["state"] == old_state
        assert matched[0]["confidence"] == old_conf


# ---------------------------------------------------------------------------
# reject_promotion tests
# ---------------------------------------------------------------------------


class TestRejectPromotion:
    def test_reject_returns_rejected_true(self, brain):
        promotions = brain.pending_promotions()
        assert len(promotions) > 0
        rule_id = promotions[0]["id"]
        result = brain.reject_promotion(rule_id)
        assert result["rejected"] is True

    def test_reject_returns_demoted_from(self, brain):
        promotions = brain.pending_promotions()
        rule_id = promotions[0]["id"]
        old_state = promotions[0]["state"]
        result = brain.reject_promotion(rule_id)
        assert result["demoted_from"] == old_state

    def test_reject_demotes_to_instinct(self, brain):
        """After rejection, the lesson should be INSTINCT with confidence 0.40."""
        promotions = brain.pending_promotions()
        rule_id = promotions[0]["id"]
        brain.reject_promotion(rule_id)

        # Check that it no longer appears in pending promotions
        after = brain.pending_promotions()
        matching = [r for r in after if r["id"] == rule_id]
        assert len(matching) == 0

        # Check it exists as INSTINCT in all rules
        all_rules = brain.rules(include_all=True)
        matching = [r for r in all_rules if r["id"] == rule_id]
        assert len(matching) == 1
        assert matching[0]["state"] == "INSTINCT"
        assert matching[0]["confidence"] == 0.40

    def test_reject_nonexistent_returns_error(self, brain):
        result = brain.reject_promotion("nonexistent-id")
        assert "error" in result


# ---------------------------------------------------------------------------
# end_session graduated_rules tests
# ---------------------------------------------------------------------------


class TestEndSessionGraduatedRules:
    def test_end_session_has_promotions_key(self, brain):
        result = brain.end_session()
        assert "promotions" in result

    def test_end_session_has_graduated_rules_key(self, brain):
        result = brain.end_session()
        assert "graduated_rules" in result
        assert isinstance(result["graduated_rules"], list)


# ---------------------------------------------------------------------------
# Not reviewing = rules persist
# ---------------------------------------------------------------------------


class TestRulesPersistWithoutReview:
    def test_unreviewed_rules_persist(self, brain):
        """Rules that passed threshold persist without explicit approval."""
        before = brain.pending_promotions()
        assert len(before) > 0

        # Don't call approve or reject — just verify they're still there
        after = brain.pending_promotions()
        assert before == after

    def test_unreviewed_rules_survive_end_session(self, brain):
        """After end_session, graduated rules still exist even without review."""
        before = brain.pending_promotions()
        before_ids = {r["id"] for r in before}
        assert len(before_ids) > 0

        brain.end_session()

        # Same rule IDs should still be present in the full rule set
        all_rules = brain.rules(include_all=True)
        after_ids = {r["id"] for r in all_rules}
        assert before_ids.issubset(after_ids), (
            f"Missing rules after end_session: {before_ids - after_ids}"
        )
