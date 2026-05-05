"""Tests for behavioral instruction extraction."""

from __future__ import annotations

import tempfile
from pathlib import Path

from gradata.enhancements.diff_engine import ChangedSection, DiffResult
from gradata.enhancements.edit_classifier import (
    EditClassification,
    extract_behavioral_instruction,
)
from gradata.enhancements.instruction_cache import InstructionCache


def _make_diff(old: str, new: str) -> DiffResult:
    return DiffResult(
        edit_distance=0.3,
        compression_distance=0.25,
        changed_sections=[ChangedSection(start_line=0, end_line=1, old_text=old, new_text=new)],
        severity="moderate",
        summary_stats={"lines_added": 1, "lines_removed": 1, "lines_changed": 1},
    )


def test_template_fallback_getattr():
    diff = _make_diff("data[0]", "getattr(data, 'field', None)")
    classification = EditClassification(
        category="CODE",
        confidence=0.6,
        severity="moderate",
        description="Content change (added: getattr)",
    )
    with tempfile.TemporaryDirectory() as d:
        cache = InstructionCache(Path(d) / "cache.json")
        result = extract_behavioral_instruction(diff, classification, cache=cache)
        assert result is not None
        assert "getattr" in result.lower()


def test_cache_hit_skips_llm():
    diff = _make_diff("old code", "new code")
    classification = EditClassification(
        category="CODE",
        confidence=0.6,
        severity="moderate",
        description="Content change (added: getattr)",
    )
    with tempfile.TemporaryDirectory() as d:
        cache = InstructionCache(Path(d) / "cache.json")
        key = InstructionCache.make_key("CODE", ["getattr"], [])
        cache.put(key, "Use getattr() for safe attribute access on optional objects")
        result = extract_behavioral_instruction(diff, classification, cache=cache)
        assert result == "Use getattr() for safe attribute access on optional objects"


def test_returns_none_without_cache_or_llm():
    diff = _make_diff("something obscure", "something else obscure")
    classification = EditClassification(
        category="CONTENT",
        confidence=0.5,
        severity="minor",
        description="Content change (added: xyzzy123)",
    )
    with tempfile.TemporaryDirectory() as d:
        cache = InstructionCache(Path(d) / "cache.json")
        result = extract_behavioral_instruction(
            diff,
            classification,
            cache=cache,
            llm_enabled=False,
        )
        assert result is None


def test_formality_template():
    diff = _make_diff("Dear Sir, We are pleased to inform you", "Hey, check this out")
    classification = EditClassification(
        category="TONE",
        confidence=0.8,
        severity="moderate",
        description="Tone casualized (formality shift: +4)",
    )
    with tempfile.TemporaryDirectory() as d:
        cache = InstructionCache(Path(d) / "cache.json")
        result = extract_behavioral_instruction(diff, classification, cache=cache)
        assert result is not None
        assert "casual" in result.lower() or "informal" in result.lower()


def test_process_template():
    diff = _make_diff("Let me implement this", "Let me plan first, then implement")
    classification = EditClassification(
        category="PROCESS",
        confidence=0.75,
        severity="moderate",
        description="Behavioral/process correction (added: plan, first)",
    )
    with tempfile.TemporaryDirectory() as d:
        cache = InstructionCache(Path(d) / "cache.json")
        result = extract_behavioral_instruction(diff, classification, cache=cache)
        assert result is not None
        assert "plan" in result.lower()
