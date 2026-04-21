"""
Test meta_rules module against real lesson data.

Reads lessons.md and lessons-archive.md, runs discovery, and prints
what meta-rules emerge. Also runs unit tests for core functions.
"""

from __future__ import annotations

import os
import sys
import tempfile

import pytest
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add SDK src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gradata._types import Lesson, LessonState
from gradata.enhancements.meta_rules import (
    MetaRule,
    discover_meta_rules,
    ensure_table,
    format_meta_rules_for_prompt,
    load_meta_rules,
    merge_into_meta,
    parse_lessons_from_markdown,
    refresh_meta_rules,
    save_meta_rules,
    validate_meta_rule,
)


def test_parse_lessons():
    """Test markdown parsing against known format."""
    sample = """
[2026-03-20] [PATTERN:0.80] DRAFTING: Bullet lists need a lead-in line for context.
[2026-03-22] [INSTINCT:0.59] CONSTRAINT: Before proposing any tool, check if it costs money.
[2026-03-21] [PATTERN:0.80] POSITIONING: Never use "agency pricing". Root cause: implies expensive retainers.
"""
    lessons = parse_lessons_from_markdown(sample)
    assert len(lessons) == 3, f"Expected 3 lessons, got {len(lessons)}"
    assert lessons[0].category == "DRAFTING"
    assert lessons[0].state == LessonState.PATTERN
    assert lessons[0].confidence == 0.80
    assert lessons[1].category == "CONSTRAINT"
    assert lessons[1].state == LessonState.INSTINCT
    assert lessons[2].root_cause == "implies expensive retainers."
    print("[PASS] parse_lessons")


def test_merge_into_meta():
    """Test merging a group of lessons into a meta-rule."""
    lessons = [
        Lesson(
            "2026-03-20",
            LessonState.PATTERN,
            0.80,
            "DRAFTING",
            "Use colons not dashes in email prose",
        ),
        Lesson(
            "2026-03-20", LessonState.PATTERN, 0.75, "DRAFTING", "No bold mid-paragraph in emails"
        ),
        Lesson(
            "2026-03-20",
            LessonState.RULE,
            0.95,
            "TONE",
            "Tight prose, direct sentences, no decorative punctuation",
        ),
    ]
    meta = merge_into_meta(lessons, theme_override="formatting", session=42)
    assert meta.id.startswith("META-")
    # Confidence uses count / (count + 3) smoothing (3 lessons → 0.50).
    assert meta.confidence == round(len(lessons) / (len(lessons) + 3.0), 2)
    assert "DRAFTING" in meta.source_categories
    assert len(meta.source_lesson_ids) == 3
    print(f"[PASS] merge_into_meta -> {meta.principle}")


def test_discover_meta_rules_minimum():
    """Test that groups below min_group_size are excluded."""
    lessons = [
        Lesson("2026-03-20", LessonState.PATTERN, 0.80, "DRAFTING", "Rule A about formatting"),
        Lesson("2026-03-20", LessonState.PATTERN, 0.80, "DRAFTING", "Rule B about formatting"),
    ]
    metas = discover_meta_rules(lessons, min_group_size=3)
    assert len(metas) == 0, "Should not form meta-rule with only 2 lessons"
    print("[PASS] min_group_size threshold works")


def test_validate_meta_rule():
    """Test contradiction detection."""
    meta = MetaRule(
        id="META-test",
        principle="Clean, minimal formatting: no decorative punctuation, no inline emphasis",
        source_categories=["DRAFTING"],
        source_lesson_ids=["a", "b", "c"],
        confidence=0.85,
        created_session=40,
        last_validated_session=40,
    )
    # No corrections -> valid
    assert validate_meta_rule(meta, []) is True

    # Unrelated correction -> valid
    assert (
        validate_meta_rule(meta, [{"description": "Use enrichment service for data enhancement"}])
        is True
    )

    # Contradicting correction -> invalid (needs 4+ token overlap + reversal words)
    assert (
        validate_meta_rule(
            meta,
            [
                {
                    "description": "Actually the minimal clean formatting rule was wrong and incorrect, decorative punctuation inline emphasis is fine"
                }
            ],
        )
        is False
    )
    print("[PASS] validate_meta_rule")


def test_format_meta_rules():
    """Test prompt formatting."""
    metas = [
        MetaRule(
            id="META-001",
            principle="Clean formatting: no dashes, use colons",
            source_categories=["DRAFTING", "TONE"],
            source_lesson_ids=["a", "b", "c"],
            confidence=0.85,
            created_session=40,
            last_validated_session=42,
            examples=["[DRAFTING] Use colons not dashes"],
        ),
    ]
    output = format_meta_rules_for_prompt(metas)
    assert "## Brain Meta-Rules" in output
    assert "META:0.85" in output
    assert "3 rules" in output
    print("[PASS] format_meta_rules_for_prompt")
    print(f"  Output:\n{output}\n")


def test_sqlite_roundtrip():
    """Test save/load cycle with a temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    metas = [
        MetaRule(
            id="META-test1",
            principle="Test principle one",
            source_categories=["DRAFTING"],
            source_lesson_ids=["a", "b", "c"],
            confidence=0.85,
            created_session=40,
            last_validated_session=42,
            scope={"task_type": "email_draft"},
            examples=["Example 1"],
        ),
        MetaRule(
            id="META-test2",
            principle="Test principle two",
            source_categories=["ACCURACY"],
            source_lesson_ids=["d", "e", "f"],
            confidence=0.75,
            created_session=38,
            last_validated_session=42,
        ),
    ]

    saved = save_meta_rules(db_path, metas)
    assert saved == 2

    loaded = load_meta_rules(db_path)
    assert len(loaded) == 2
    assert loaded[0].confidence >= loaded[1].confidence  # sorted desc
    assert loaded[0].scope == {"task_type": "email_draft"}
    assert loaded[0].examples == ["Example 1"]

    Path(db_path).unlink(missing_ok=True)
    print("[PASS] SQLite roundtrip")


def test_refresh_meta_rules():
    """Test the refresh pipeline preserves valid existing meta-rules."""
    lessons = [
        Lesson("2026-03-20", LessonState.PATTERN, 0.80, "PROCESS", "Never skip wrap-up steps"),
        Lesson(
            "2026-03-20", LessonState.PATTERN, 0.75, "PROCESS", "Always run gate checks before done"
        ),
        Lesson(
            "2026-03-20",
            LessonState.PATTERN,
            0.85,
            "PROCESS",
            "Mandatory audit at every session end",
        ),
    ]
    existing = [
        MetaRule(
            id="META-old",
            principle="Old principle that is still valid",
            source_categories=["MISC"],
            source_lesson_ids=["x", "y", "z"],
            confidence=0.70,
            created_session=30,
            last_validated_session=38,
        ),
    ]

    result = refresh_meta_rules(lessons, existing, recent_corrections=[], current_session=42)
    # Valid existing meta-rules should survive refresh
    ids = [m.id for m in result]
    assert "META-old" in ids, "Valid existing meta-rule should survive refresh"
    # Validated session should be updated
    meta_old = [m for m in result if m.id == "META-old"][0]
    assert meta_old.last_validated_session == 42
    print(f"[PASS] refresh_meta_rules -> {len(result)} meta-rules")


# ---------------------------------------------------------------------------
# Differential-privacy export scaffold tests
# ---------------------------------------------------------------------------

import random as _random

from gradata.enhancements.meta_rules_storage import (
    DPConfig,
    apply_dp_to_export_row,
)


def test_dp_config_defaults_are_off():
    """DP must ship off-by-default; the dataclass is the source of truth."""
    cfg = DPConfig()
    assert cfg.enabled is False
    assert cfg.epsilon == 1.0
    assert cfg.mechanism == "laplace"
    assert cfg.clip_norm == 1.0
    print("[PASS] DPConfig defaults")


def test_apply_dp_noop_when_disabled():
    """With enabled=False the row must pass through untouched."""
    row = {
        "id": "m1",
        "confidence": 0.87,
        "fire_count": 12,
        "principle": "raw operator fingerprint",
        "source_lesson_ids": ["l1", "l2", "l3"],
    }
    original = dict(row)
    result = apply_dp_to_export_row(row, DPConfig(enabled=False))
    assert result == original
    print("[PASS] DP off = identity")


def test_apply_dp_enabled_suppresses_text_and_perturbs_numbers():
    """With enabled=True text must be suppressed and numbers noised/clipped."""
    rng = _random.Random(42)  # seeded for reproducibility
    row = {
        "id": "m1",
        "confidence": 0.87,
        "fire_count": 12,
        "principle": "raw operator fingerprint",
        "description": "also sensitive",
        "representative_text": "verbatim correction",
        "examples": ["ex1", "ex2"],
        "source_lesson_ids": ["l1", "l2", "l3", "l4", "l5"],
    }
    cfg = DPConfig(enabled=True, epsilon=1.0, clip_norm=1.0)
    result = apply_dp_to_export_row(row, cfg, rng=rng)

    # Text fields: suppressed.
    assert result["principle"] == "[DP-SUPPRESSED]"
    assert result["description"] == "[DP-SUPPRESSED]"
    assert result["representative_text"] == "[DP-SUPPRESSED]"
    assert result["examples"] == []

    # Source IDs: dropped; cardinality exposed as noised integer.
    assert result["source_lesson_ids"] == []
    assert isinstance(result["source_lesson_count"], int)
    assert result["source_lesson_count"] >= 0

    # Confidence: clamped to [0, 1] after noise.
    assert 0.0 <= result["confidence"] <= 1.0

    # fire_count: non-negative integer.
    assert isinstance(result["fire_count"], int)
    assert result["fire_count"] >= 0
    print("[PASS] DP on = suppressed + noised")


def test_apply_dp_noise_actually_perturbs_confidence():
    """Flipping the flag must produce *different* outputs across draws.

    Guards against a regression where someone stubs out the Laplace draw
    but leaves the plumbing intact.
    """
    cfg = DPConfig(enabled=True, epsilon=0.5, clip_norm=1.0)
    outputs = set()
    for seed in range(20):
        rng = _random.Random(seed)
        row = {
            "id": "m",
            "confidence": 0.5,
            "fire_count": 10,
            "principle": "x",
            "source_lesson_ids": ["a", "b"],
        }
        out = apply_dp_to_export_row(row, cfg, rng=rng)
        outputs.add(round(out["confidence"], 6))
    # With ε=0.5 and 20 independent seeds, we expect many distinct values.
    assert len(outputs) > 5, f"Expected noise variation, got {len(outputs)} distinct outputs"
    print(f"[PASS] DP noise variation: {len(outputs)} distinct outputs across 20 seeds")


def test_apply_dp_rejects_bad_config():
    """ε must be > 0 and mechanism must be supported."""
    row = {"id": "m", "confidence": 0.5}
    with pytest.raises(ValueError):
        apply_dp_to_export_row(row, DPConfig(enabled=True, epsilon=0.0))
    with pytest.raises(ValueError):
        apply_dp_to_export_row(row, DPConfig(enabled=True, mechanism="gaussian"))
    with pytest.raises(ValueError):
        apply_dp_to_export_row(row, DPConfig(enabled=True, clip_norm=-1.0))
    print("[PASS] DP rejects bad config")


if __name__ == "__main__":
    print("Running meta_rules unit tests...\n")
    test_parse_lessons()
    test_merge_into_meta()
    test_discover_meta_rules_minimum()
    test_validate_meta_rule()
    test_format_meta_rules()
    test_sqlite_roundtrip()
    test_refresh_meta_rules()
    test_dp_config_defaults_are_off()
    test_apply_dp_noop_when_disabled()
    test_apply_dp_enabled_suppresses_text_and_perturbs_numbers()
    test_apply_dp_noise_actually_perturbs_confidence()
    test_apply_dp_rejects_bad_config()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
