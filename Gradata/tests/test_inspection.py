"""Tests for the Rule Inspection API (inspection.py + Brain wrappers)."""

from __future__ import annotations

import json
import sqlite3
import textwrap
from pathlib import Path

import pytest

from gradata.inspection import (
    _dict_to_yaml,
    _make_rule_id,
    explain_rule,
    export_rules,
    list_rules,
)

# ---------------------------------------------------------------------------
# Sample lessons.md content — 3 lessons: 1 RULE, 1 PATTERN, 1 INSTINCT
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

    # Write lessons.md
    (d / "lessons.md").write_text(SAMPLE_LESSONS, encoding="utf-8")

    # Create system.db with required tables
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
    # Insert a transition for the RULE lesson
    conn.execute(
        """INSERT INTO lesson_transitions
           (lesson_desc, category, old_state, new_state, confidence, fire_count, session, transitioned_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "Never use em dashes in email prose",
            "DRAFTING",
            "PATTERN",
            "RULE",
            0.95,
            12,
            50,
            "2026-01-15T10:00:00",
        ),
    )
    conn.commit()
    conn.close()

    # Create events.jsonl (empty is fine)
    (d / "events.jsonl").write_text("", encoding="utf-8")

    return d


# ---------------------------------------------------------------------------
# list_rules tests
# ---------------------------------------------------------------------------


class TestListRules:
    def test_default_filters_to_pattern_and_rule(self, brain_dir: Path):
        """Default call returns only PATTERN + RULE lessons."""
        result = list_rules(db_path=brain_dir / "system.db", lessons_path=brain_dir / "lessons.md")
        assert len(result) == 2
        states = {r["state"] for r in result}
        assert states == {"RULE", "PATTERN"}

    def test_include_all_returns_everything(self, brain_dir: Path):
        """include_all=True returns all 3 lessons."""
        result = list_rules(
            db_path=brain_dir / "system.db", lessons_path=brain_dir / "lessons.md", include_all=True
        )
        assert len(result) == 3

    def test_category_filter(self, brain_dir: Path):
        """Category filter narrows results."""
        result = list_rules(
            db_path=brain_dir / "system.db",
            lessons_path=brain_dir / "lessons.md",
            include_all=True,
            category="DRAFTING",
        )
        assert len(result) == 1
        assert result[0]["category"] == "DRAFTING"

    def test_empty_lessons_returns_empty_list(self, tmp_path: Path):
        """No lessons.md returns empty list."""
        d = tmp_path / "empty-brain"
        d.mkdir()
        (d / "lessons.md").write_text("", encoding="utf-8")
        result = list_rules(db_path=d / "system.db", lessons_path=d / "lessons.md")
        assert result == []

    def test_rule_dict_has_expected_keys(self, brain_dir: Path):
        """Each rule dict has id, state, confidence, category, description."""
        result = list_rules(db_path=brain_dir / "system.db", lessons_path=brain_dir / "lessons.md")
        for r in result:
            assert "id" in r
            assert "state" in r
            assert "confidence" in r
            assert "category" in r
            assert "description" in r


# ---------------------------------------------------------------------------
# explain_rule tests
# ---------------------------------------------------------------------------


class TestExplainRule:
    def test_explain_existing_rule(self, brain_dir: Path):
        """explain_rule returns metadata + transitions for an existing rule."""
        rules = list_rules(db_path=brain_dir / "system.db", lessons_path=brain_dir / "lessons.md")
        rule_id = rules[0]["id"]  # first RULE/PATTERN
        result = explain_rule(
            db_path=brain_dir / "system.db",
            events_path=brain_dir / "events.jsonl",
            rule_id=rule_id,
            lessons_path=brain_dir / "lessons.md",
        )
        assert "description" in result
        assert "category" in result
        assert "transitions" in result

    def test_explain_nonexistent_rule(self, brain_dir: Path):
        """explain_rule returns error dict for unknown rule_id."""
        result = explain_rule(
            db_path=brain_dir / "system.db",
            events_path=brain_dir / "events.jsonl",
            rule_id="nonexistent-id",
            lessons_path=brain_dir / "lessons.md",
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# export_rules tests
# ---------------------------------------------------------------------------


class TestExportRules:
    def test_json_format(self, brain_dir: Path):
        """JSON export is valid JSON with expected keys."""
        output = export_rules(
            db_path=brain_dir / "system.db",
            lessons_path=brain_dir / "lessons.md",
            output_format="json",
        )
        parsed = json.loads(output)
        assert "rules" in parsed
        assert "metadata" in parsed
        assert len(parsed["rules"]) == 2  # default: PATTERN + RULE only

    def test_yaml_format(self, brain_dir: Path):
        """YAML export contains expected markers."""
        output = export_rules(
            db_path=brain_dir / "system.db",
            lessons_path=brain_dir / "lessons.md",
            output_format="yaml",
        )
        assert "rules:" in output
        assert "category:" in output

    def test_invalid_format_raises(self, brain_dir: Path):
        """Unsupported format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported"):
            export_rules(
                db_path=brain_dir / "system.db",
                lessons_path=brain_dir / "lessons.md",
                output_format="xml",
            )


# ---------------------------------------------------------------------------
# _dict_to_yaml tests
# ---------------------------------------------------------------------------


class TestDictToYaml:
    def test_simple_dict(self):
        result = _dict_to_yaml({"name": "test", "count": 42})
        assert "name: test" in result
        assert "count: 42" in result

    def test_nested_dict(self):
        result = _dict_to_yaml({"outer": {"inner": "value"}})
        assert "outer:" in result
        assert "  inner: value" in result

    def test_list_values(self):
        result = _dict_to_yaml({"items": ["a", "b"]})
        assert "- a" in result
        assert "- b" in result


# ---------------------------------------------------------------------------
# _make_rule_id tests
# ---------------------------------------------------------------------------


class TestMakeRuleId:
    def test_stable_id(self):
        """Same input produces same ID."""
        from gradata._types import Lesson, LessonState

        lesson = Lesson(
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.95,
            category="DRAFTING",
            description="Never use em dashes",
        )
        id1 = _make_rule_id(lesson)
        id2 = _make_rule_id(lesson)
        assert id1 == id2
        assert len(id1) > 0

    def test_different_lessons_different_ids(self):
        from gradata._types import Lesson, LessonState

        l1 = Lesson(
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.95,
            category="DRAFTING",
            description="Never use em dashes",
        )
        l2 = Lesson(
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.95,
            category="ACCURACY",
            description="Verify data first",
        )
        assert _make_rule_id(l1) != _make_rule_id(l2)


# ---------------------------------------------------------------------------
# Brain wrapper tests
# ---------------------------------------------------------------------------


class TestBrainWrappers:
    @pytest.fixture()
    def brain(self, brain_dir: Path):
        from gradata.brain import Brain

        return Brain.init(
            brain_dir, name="Test", domain="Testing", embedding="local", interactive=False
        )

    def test_brain_rules_returns_list(self, brain):
        result = brain.rules()
        assert isinstance(result, list)

    def test_brain_explain_returns_dict(self, brain):
        rules = brain.rules()
        assert len(rules) > 0, "Fixture must seed PATTERN/RULE lessons"
        result = brain.explain(rules[0]["id"])
        assert isinstance(result, dict)
        assert "description" in result

    def test_brain_export_data_json(self, brain):
        output = brain.export_data(output_format="json")
        parsed = json.loads(output)
        assert "rules" in parsed

    def test_brain_export_data_yaml(self, brain):
        output = brain.export_data(output_format="yaml")
        assert isinstance(output, str)

    def test_brain_rules_empty(self, tmp_path: Path):
        """Brain with no lessons returns empty list."""
        from gradata.brain import Brain

        d = tmp_path / "empty-brain"
        b = Brain.init(d, name="Empty", domain="Test", embedding="local", interactive=False)
        result = b.rules()
        assert result == []
