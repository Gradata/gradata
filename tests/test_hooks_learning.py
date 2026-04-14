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


def test_inject_emits_meta_rules_block_for_llm_synth_source(tmp_path):
    """Meta-rules with source='llm_synth' or 'human_curated' get injected."""
    (tmp_path / "lessons.md").write_text(
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n",
        encoding="utf-8",
    )

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
        source="llm_synth",
    )
    save_meta_rules(db_path, [meta])

    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        result = inject_main({})
    assert result is not None
    text = result.get("result", "")
    assert "<brain-rules>" in text
    assert "<brain-meta-rules>" in text
    assert "Verify before acting" in text


def test_inject_skips_meta_rules_with_deterministic_source(tmp_path):
    """Meta-rules with source='deterministic' (the default for auto-generated
    cluster output) are EXCLUDED from injection. Empirical: 2026-04-14 ablation
    showed deterministic principles regress correctness."""
    (tmp_path / "lessons.md").write_text(
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n",
        encoding="utf-8",
    )

    from gradata.enhancements.meta_rules import MetaRule
    from gradata.enhancements.meta_rules_storage import save_meta_rules

    db_path = tmp_path / "system.db"
    # Default source is 'deterministic' — should NOT be injected
    meta = MetaRule(
        id="m-2",
        principle="Code: Avoid: foo. Prefer: bar.",  # the ablation-confirmed garbage shape
        source_categories=["CODE"],
        source_lesson_ids=["l-9"],
        confidence=1.00,  # confidence is high BUT source disqualifies it
        created_session=1,
        last_validated_session=1,
    )
    save_meta_rules(db_path, [meta])

    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        result = inject_main({})
    assert result is not None
    text = result.get("result", "")
    assert "<brain-rules>" in text
    # Critical: the deterministic meta-rule must NOT appear in the prompt
    assert "<brain-meta-rules>" not in text
    assert "Avoid: foo" not in text


def test_inject_caps_meta_rules_and_context_promotes_lower_confidence(tmp_path):
    """Boundary test: with more than MAX_META_RULES injectable metas, the cap
    must be applied AFTER context-aware ranking, so a lower-confidence rule
    with a strong context weight can still make the cut.

    Regression guard for the CR finding: pre-slicing by raw confidence would
    silently exclude the context-promoted rule, giving the LLM the wrong
    principles for the current task.
    """
    from gradata.enhancements.meta_rules import MetaRule
    from gradata.enhancements.meta_rules_storage import save_meta_rules
    from gradata.hooks.inject_brain_rules import MAX_META_RULES

    (tmp_path / "lessons.md").write_text(
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "system.db"
    # Seed MAX_META_RULES + 2 high-confidence metas that are *neutral* in the
    # target context, plus one lower-confidence meta that should be *boosted*
    # by context weight so it makes it into the top-N despite its lower base.
    metas = []
    for i in range(MAX_META_RULES + 2):
        metas.append(
            MetaRule(
                id=f"m-hi-{i}",
                principle=f"Neutral principle number {i} for baseline comparison.",
                source_categories=["PROCESS"],
                source_lesson_ids=[f"l-{i}a", f"l-{i}b", f"l-{i}c"],
                confidence=0.95,
                created_session=1,
                last_validated_session=1,
                source="llm_synth",
            ),
        )
    # Lower base confidence (0.60) but a very strong context weight (3.0) in
    # the "drafting" context — should beat the neutral 0.95-confidence metas
    # after weighting (0.60 * 3.0 = 1.80 > 0.95 * 1.0 = 0.95).
    promoted = MetaRule(
        id="m-promoted",
        principle="Promoted drafting principle — context weight lifts this in.",
        source_categories=["TONE"],
        source_lesson_ids=["l-p1", "l-p2", "l-p3"],
        confidence=0.60,
        created_session=1,
        last_validated_session=1,
        source="llm_synth",
        context_weights={"drafting": 3.0, "default": 1.0},
    )
    metas.append(promoted)
    save_meta_rules(db_path, metas)

    # Run the hook with a context that promotes the low-confidence meta.
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        result = inject_main({"session_type": "drafting"})

    assert result is not None
    text = result["result"]
    assert "<brain-meta-rules>" in text

    # Cap: only MAX_META_RULES meta-rule lines (numbered "1.", "2." ...) appear
    # between the meta-rules tags.
    meta_section = text.split("<brain-meta-rules>")[1].split("</brain-meta-rules>")[0]
    numbered_lines = [
        line for line in meta_section.splitlines()
        if line.strip() and line.lstrip()[0].isdigit() and ". [META:" in line
    ]
    assert len(numbered_lines) == MAX_META_RULES, (
        f"expected exactly {MAX_META_RULES} meta-rule lines, got {len(numbered_lines)}"
    )

    # Context-aware promotion: the lower-confidence but context-boosted rule
    # must appear in the final output even though MAX_META_RULES other metas
    # have higher raw confidence.
    assert "Promoted drafting principle" in text, (
        "context-weighted rule was excluded — cap is being applied before "
        "context ranking (CR finding regression)"
    )


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
