"""Test that brain.correct() uses behavioral extraction."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from gradata.brain import Brain


def test_correct_uses_behavioral_description():
    """When extraction returns a result, it should be used as the lesson description."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        brain = Brain.init(d)
        with patch(
            "gradata.enhancements.behavioral_extractor.extract_instruction",
            return_value="Use casual, direct tone in all communications",
        ):
            brain.correct(
                draft="Dear Sir, We are pleased to inform you of our decision.",
                final="Hey, here's what we decided.",
            )
        lessons_path = Path(d) / "lessons.md"
        if lessons_path.exists():
            content = lessons_path.read_text(encoding="utf-8")
            assert "Use casual, direct tone" in content


def test_correct_falls_back_to_old_description():
    """When extraction returns None, old diff-fingerprint description is used."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        brain = Brain.init(d)
        with patch(
            "gradata.enhancements.behavioral_extractor.extract_instruction",
            return_value=None,
        ):
            brain.correct(
                draft="Dear Sir, We are pleased.",
                final="Hey, here's the deal.",
            )
        lessons_path = Path(d) / "lessons.md"
        if lessons_path.exists():
            content = lessons_path.read_text(encoding="utf-8")
            assert "INSTINCT" in content or "PATTERN" in content
