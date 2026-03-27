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
        Lesson("2026-03-20", LessonState.PATTERN, 0.80, "DRAFTING",
               "Use colons not dashes in email prose"),
        Lesson("2026-03-20", LessonState.PATTERN, 0.75, "DRAFTING",
               "No bold mid-paragraph in emails"),
        Lesson("2026-03-20", LessonState.RULE, 0.95, "TONE",
               "Tight prose, direct sentences, no decorative punctuation"),
    ]
    meta = merge_into_meta(lessons, theme_override="formatting", session=42)
    assert meta.id.startswith("META-")
    assert meta.confidence == round((0.80 + 0.75 + 0.95) / 3, 2)
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
    assert validate_meta_rule(meta, [{"description": "Use Apollo for enrichment"}]) is True

    # Contradicting correction -> invalid (needs 4+ token overlap + reversal words)
    assert validate_meta_rule(meta, [{
        "description": "Actually the minimal clean formatting rule was wrong and incorrect, decorative punctuation inline emphasis is fine"
    }]) is False
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
    """Test the refresh pipeline."""
    lessons = [
        Lesson("2026-03-20", LessonState.PATTERN, 0.80, "PROCESS", "Never skip wrap-up steps"),
        Lesson("2026-03-20", LessonState.PATTERN, 0.75, "PROCESS", "Always run gate checks before done"),
        Lesson("2026-03-20", LessonState.PATTERN, 0.85, "PROCESS", "Mandatory audit at every session end"),
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

    result = refresh_meta_rules(
        lessons, existing, recent_corrections=[], current_session=42
    )
    # Should have the old one (still valid) + any new discovered ones
    ids = [m.id for m in result]
    assert "META-old" in ids, "Valid existing meta-rule should survive refresh"
    print(f"[PASS] refresh_meta_rules -> {len(result)} meta-rules")


@pytest.mark.skipif(
    not Path(os.environ.get("GRADATA_LESSONS_PATH", "/nonexistent")).exists(),
    reason="requires GRADATA_LESSONS_PATH env var pointing to real lessons.md"
)
def test_with_real_data():
    """Load real lessons from the project and discover meta-rules."""
    lessons_path = Path(os.environ.get("GRADATA_LESSONS_PATH", "lessons.md"))
    archive_path = Path(os.environ.get("GRADATA_ARCHIVE_PATH", "lessons-archive.md"))

    all_text = ""
    for p in [lessons_path, archive_path]:
        if p.exists():
            all_text += "\n" + p.read_text(encoding="utf-8")

    lessons = parse_lessons_from_markdown(all_text)
    print(f"\n{'='*60}")
    print(f"REAL DATA: Parsed {len(lessons)} lessons")
    print(f"  INSTINCT: {sum(1 for l in lessons if l.state == LessonState.INSTINCT)}")
    print(f"  PATTERN:  {sum(1 for l in lessons if l.state == LessonState.PATTERN)}")
    print(f"  RULE:     {sum(1 for l in lessons if l.state == LessonState.RULE)}")
    print(f"  UNTESTABLE: {sum(1 for l in lessons if l.state == LessonState.UNTESTABLE)}")

    # Categories
    from collections import Counter
    cat_counts = Counter(l.category for l in lessons)
    print(f"\n  Categories: {dict(cat_counts)}")

    # Discover meta-rules including INSTINCT (lower threshold for real data test)
    # First with only PATTERN+RULE (default)
    metas_strict = discover_meta_rules(lessons, min_group_size=3, current_session=70)
    print(f"\n  Meta-rules discovered (PATTERN+RULE only, min 3): {len(metas_strict)}")
    for meta in metas_strict:
        print(f"\n  [{meta.id}] confidence={meta.confidence:.2f}")
        print(f"    Categories: {meta.source_categories}")
        print(f"    Sources: {len(meta.source_lesson_ids)} lessons")
        print(f"    Principle: {meta.principle}")
        if meta.examples:
            for ex in meta.examples:
                print(f"    Example: {ex}")

    # Also test with all eligible lessons relaxed to include INSTINCT
    # (to show what would emerge as lessons graduate)
    all_for_preview = []
    for l in lessons:
        # Temporarily promote INSTINCT to PATTERN for preview
        preview = Lesson(
            date=l.date, state=LessonState.PATTERN if l.state == LessonState.INSTINCT else l.state,
            confidence=max(l.confidence, 0.60), category=l.category,
            description=l.description, root_cause=l.root_cause,
        )
        all_for_preview.append(preview)

    metas_preview = discover_meta_rules(all_for_preview, min_group_size=3, current_session=70)
    print(f"\n  PREVIEW (if all INSTINCT graduated): {len(metas_preview)} meta-rules")
    for meta in metas_preview:
        print(f"\n  [{meta.id}] confidence={meta.confidence:.2f}")
        print(f"    Categories: {meta.source_categories}")
        print(f"    Sources: {len(meta.source_lesson_ids)} lessons")
        print(f"    Principle: {meta.principle}")

    # Format for prompt
    if metas_preview:
        print(f"\n{'='*60}")
        print("FORMATTED FOR PROMPT INJECTION:")
        print(format_meta_rules_for_prompt(metas_preview))

    # Save to real system.db
    db_path = Path(os.environ.get("GRADATA_DB_PATH", "system.db"))
    if db_path.exists() and metas_strict:
        saved = save_meta_rules(db_path, metas_strict)
        print(f"\nSaved {saved} meta-rules to {db_path}")
        loaded = load_meta_rules(db_path)
        print(f"Verified: loaded {len(loaded)} meta-rules back from DB")


if __name__ == "__main__":
    print("Running meta_rules unit tests...\n")
    test_parse_lessons()
    test_merge_into_meta()
    test_discover_meta_rules_minimum()
    test_validate_meta_rule()
    test_format_meta_rules()
    test_sqlite_roundtrip()
    test_refresh_meta_rules()

    print("\n" + "="*60)
    print("Running against REAL lesson data...\n")
    test_with_real_data()

    print("\n" + "="*60)
    print("ALL TESTS PASSED")
