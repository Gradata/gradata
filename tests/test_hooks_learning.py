"""Tests for core learning loop hooks."""
import json
import os
from pathlib import Path
from unittest.mock import patch

from gradata.hooks.inject_brain_rules import main as inject_main, _parse_lessons, _score
from gradata.hooks.session_close import main as close_main


def test_parse_lessons_extracts_rules():
    text = (
        "2026-04-01 [RULE:0.92] PROCESS: Always plan before implementing\n"
        "2026-04-01 [PATTERN:0.65] TONE: Use casual tone in emails\n"
        "2026-04-01 [INSTINCT:0.35] CODE: Add docstrings\n"
    )
    lessons = _parse_lessons(text)
    assert len(lessons) == 2  # INSTINCT below threshold
    assert lessons[0]["state"] == "RULE"
    assert lessons[0]["confidence"] == 0.92
    assert lessons[1]["state"] == "PATTERN"


def test_parse_lessons_empty():
    assert _parse_lessons("") == []
    assert _parse_lessons("random text\nno lessons here\n") == []


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
        "2026-04-01 [RULE:0.92] PROCESS: Always plan before implementing\n"
        "2026-04-01 [PATTERN:0.65] TONE: Use casual tone in emails\n"
        "2026-04-01 [INSTINCT:0.35] CODE: Add docstrings\n",
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
        with patch("gradata.hooks.inject_brain_rules.Path.home", return_value=fake_home):
            result = inject_main({})
    assert result is None


def test_inject_rules_no_lessons_file(tmp_path):
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        result = inject_main({})
    assert result is None


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
        with patch("gradata.hooks.session_close.Path.home", return_value=fake_home):
            result = close_main({})
    assert result is None
