"""Tests for core learning loop hooks."""
import json
import os
from pathlib import Path
from unittest.mock import patch

from gradata.enhancements.self_improvement import parse_lessons
from gradata.hooks.inject_brain_rules import main as inject_main, _score
from gradata.hooks.session_close import main as close_main


def test_parse_lessons_extracts_rules():
    text = (
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n"
        "[2026-04-01] [PATTERN:0.65] TONE: Use casual tone in emails\n"
        "[2026-04-01] [INSTINCT:0.35] CODE: Add docstrings\n"
    )
    lessons = parse_lessons(text)
    # parse_lessons returns all lessons; filtering is done in the hook
    rules_and_patterns = [l for l in lessons if l.state.name in ("RULE", "PATTERN")]
    assert len(rules_and_patterns) == 2
    assert rules_and_patterns[0].state.name == "RULE"
    assert rules_and_patterns[0].confidence == 0.92
    assert rules_and_patterns[1].state.name == "PATTERN"


def test_parse_lessons_empty():
    assert parse_lessons("") == []
    assert parse_lessons("random text\nno lessons here\n") == []


def test_score_rule_higher_than_pattern():
    rule = {"state": "RULE", "confidence": 0.90}
    pattern = {"state": "PATTERN", "confidence": 0.90}
    assert _score(rule) > _score(pattern)


def test_score_higher_confidence_wins():
    high = {"state": "RULE", "confidence": 0.95}
    low = {"state": "RULE", "confidence": 0.65}
    assert _score(high) > _score(low)


def test_inject_rules_from_lessons(tmp_path):
    lessons = tmp_path / "lessons.md"
    lessons.write_text(
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n"
        "[2026-04-01] [PATTERN:0.65] TONE: Use casual tone in emails\n"
        "[2026-04-01] [INSTINCT:0.35] CODE: Add docstrings\n",
        encoding="utf-8",
    )
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        result = inject_main({})
    assert result is not None
    assert "brain-rules" in result.get("result", "")
    assert "Always plan" in result["result"]
    assert "casual tone" in result["result"]
    assert "docstrings" not in result["result"]


def test_inject_rules_no_brain_dir(tmp_path):
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": "", "BRAIN_DIR": ""}):
        with patch("gradata.hooks._base.Path.home", return_value=fake_home):
            result = inject_main({})
    assert result is None


def test_inject_rules_no_lessons_file(tmp_path):
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        result = inject_main({})
    assert result is None


def test_inject_also_emits_meta_rules_block_when_db_has_them(tmp_path):
    """When meta-rules exist in system.db, the injection block includes
    <brain-meta-rules> alongside <brain-rules>. Previously meta-rules were
    created and stored but never reached the LLM."""
    # Seed lessons so the hook gets past the "no rules" guard
    (tmp_path / "lessons.md").write_text(
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n",
        encoding="utf-8",
    )

    # Seed a meta-rule into system.db
    from gradata.enhancements.meta_rules import MetaRule
    from gradata.enhancements.meta_rules_storage import save_meta_rules

    db_path = tmp_path / "system.db"
    meta = MetaRule(
        id="m-1",
        principle="Verify before acting — check existing state before creating new artifacts.",
        source_categories=["PROCESS", "CODE"],
        source_lesson_ids=["l-1", "l-2", "l-3"],
        confidence=0.88,
        created_session=1,
        last_validated_session=1,
    )
    save_meta_rules(db_path, [meta])

    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        result = inject_main({})
    assert result is not None
    text = result.get("result", "")
    assert "<brain-rules>" in text
    assert "<brain-meta-rules>" in text
    assert "Verify before acting" in text


def test_inject_tolerates_missing_meta_rules_db(tmp_path):
    """No system.db file → still returns the rules block, no meta-rules block,
    and no exception."""
    (tmp_path / "lessons.md").write_text(
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n",
        encoding="utf-8",
    )
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        result = inject_main({})
    assert result is not None
    text = result.get("result", "")
    assert "<brain-rules>" in text
    assert "<brain-meta-rules>" not in text


def test_session_close_emits_event(tmp_path):
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        with patch("gradata.hooks.session_close._emit_session_end") as mock_emit:
            with patch("gradata.hooks.session_close._run_graduation") as mock_grad:
                close_main({})
    mock_emit.assert_called_once_with(str(tmp_path))
    mock_grad.assert_called_once_with(str(tmp_path))


def test_session_close_no_brain(tmp_path):
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": "", "BRAIN_DIR": ""}):
        with patch("gradata.hooks._base.Path.home", return_value=fake_home):
            result = close_main({})
    assert result is None
