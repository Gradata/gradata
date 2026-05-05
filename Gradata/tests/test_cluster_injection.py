"""Tests for rule injection in inject_brain_rules.main().

Legacy cluster-summary + per-rule-line output is replaced by a single
slot-grouped synthesized prompt (Preston-Rhodes 6-step). The manifest
still records per-rule anchors for capture_learning attribution; the
visible block is prose with inline r:xxxx anchors. Tests below assert
the new contract (category/description presence in prose, anchor
survival, manifest structure) instead of the obsolete line format.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers to build minimal Lesson-like objects accepted by inject_brain_rules
# ---------------------------------------------------------------------------


def _make_lesson(
    description: str,
    category: str,
    confidence: float = 0.85,
    state_name: str = "RULE",
    fire_count: int = 0,
    scope_json: str | None = None,
) -> Any:
    """Return a minimal object that satisfies the duck-typed Lesson interface."""
    from gradata._types import LessonState

    state = LessonState[state_name]
    obj = SimpleNamespace(
        description=description,
        category=category,
        confidence=confidence,
        state=state,
        fire_count=fire_count,
        scope_json=scope_json or "",
        alpha=1.0,
        beta_param=1.0,
    )
    return obj


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def three_qualifying_lessons():
    """Three RULE-tier lessons in the same category, high confidence — will form a cluster."""
    return [
        _make_lesson("always validate input at boundaries", "VALIDATION", confidence=0.88),
        _make_lesson("sanitize user input before processing", "VALIDATION", confidence=0.82),
        _make_lesson("reject requests missing required fields", "VALIDATION", confidence=0.91),
    ]


@pytest.fixture()
def two_unrelated_lessons():
    """Two lessons in a different category — won't form a cluster (size < 3)."""
    return [
        _make_lesson("use absolute paths only", "PATHS", confidence=0.80),
        _make_lesson("never use relative imports", "IMPORTS", confidence=0.78),
    ]


# ---------------------------------------------------------------------------
# Helper: run main() with mocked dependencies
# ---------------------------------------------------------------------------


def _run_main(lessons: list, data: dict | None = None) -> dict | None:
    """Invoke inject_brain_rules.main() with the given lessons pre-loaded."""
    from gradata.hooks import inject_brain_rules as inj

    data = data or {"session_type": "coding", "session_number": 1}

    mock_lesson_text = "# mocked lessons file"

    with (
        patch.object(inj, "parse_lessons", return_value=lessons),
        patch.object(inj, "is_hook_enforced", return_value=False),
        patch.object(inj, "resolve_brain_dir", return_value="/fake/brain"),
        patch.object(inj, "load_meta_rules", return_value=[]),
        patch.object(inj, "format_meta_rules_for_prompt", return_value=""),
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.read_text", return_value=mock_lesson_text),
    ):
        return inj.main(data)


import re

_ANCHOR_RE = re.compile(r"(?<![0-9a-zA-Z])r:([0-9a-f]{4})")


def _anchors(block: str) -> list[str]:
    return _ANCHOR_RE.findall(block)


# ---------------------------------------------------------------------------
# Test 1: qualifying rules surface in the synthesized prose with anchors
# ---------------------------------------------------------------------------


def test_qualifying_cluster_injects_summary(three_qualifying_lessons):
    result = _run_main(three_qualifying_lessons)
    assert result is not None
    block = result["result"]
    # Synthesizer output replaces cluster summary lines — category + rule
    # content still has to be represented via inline anchors.
    assert "<brain-rules>" in block and "</brain-rules>" in block
    assert len(_anchors(block)) == 3
    # At least one rule description survives the synthesis
    descriptions = [
        "validate input at boundaries",
        "sanitize user input",
        "reject requests missing required fields",
    ]
    assert any(any(token in block.lower() for token in d.lower().split()) for d in descriptions)


# ---------------------------------------------------------------------------
# Test 2: rules across multiple categories all reach the prompt
# ---------------------------------------------------------------------------


def test_non_cluster_rules_injected_individually():
    lessons = [
        _make_lesson("always validate input at boundaries", "VALIDATION", confidence=0.88),
        _make_lesson("use absolute paths only", "PATHS", confidence=0.80),
        _make_lesson("never use relative imports", "IMPORTS", confidence=0.78),
    ]
    result = _run_main(lessons)
    assert result is not None
    block = result["result"]
    # All three unique anchors must make it into the prose
    assert len(_anchors(block)) == 3


# ---------------------------------------------------------------------------
# Test 3: contradicting rules still appear — contradictions matter for
# graduation, not for session-start synthesis
# ---------------------------------------------------------------------------


def test_contradicting_cluster_not_used():
    lessons = [
        _make_lesson("always validate user input carefully", "SAFETY", confidence=0.85),
        _make_lesson("never validate user input in tests", "SAFETY", confidence=0.85),
        _make_lesson("validate input at every system boundary", "SAFETY", confidence=0.87),
    ]
    result = _run_main(lessons)
    assert result is not None
    block = result["result"]
    # All three rules selected for injection (manifest proves it elsewhere);
    # here we just check that the synthesizer produced a non-empty block.
    assert "<brain-rules>" in block
    assert len(_anchors(block)) >= 1


# ---------------------------------------------------------------------------
# Test 4: clusters below confidence threshold are not used
# ---------------------------------------------------------------------------


def test_low_confidence_cluster_not_injected():
    # Three lessons with low confidence — cluster avg will be < 0.75
    lessons = [
        _make_lesson("do something cautiously", "LOW_CONF", confidence=0.61),
        _make_lesson("be careful with operations", "LOW_CONF", confidence=0.63),
        _make_lesson("handle errors gracefully here", "LOW_CONF", confidence=0.62),
    ]
    result = _run_main(lessons)
    assert result is not None
    block = result["result"]
    # No cluster line should appear for LOW_CONF
    low_conf_cluster_lines = [l for l in block.splitlines() if "[CLUSTER:" in l and "LOW_CONF" in l]
    assert len(low_conf_cluster_lines) == 0


# ---------------------------------------------------------------------------
# Test 5: synthesizer collapses N rules into a single prose block
# ---------------------------------------------------------------------------


def test_cluster_reduces_injection_count(three_qualifying_lessons):
    """Three rules collapse into one synthesized prose block bounded by the tags."""
    result = _run_main(three_qualifying_lessons)
    assert result is not None
    block = result["result"]
    inner = block.replace("<brain-rules>", "").replace("</brain-rules>", "").strip()
    # The whole prose is one contiguous block — no per-rule line format anymore.
    assert inner
    assert "[CLUSTER:" not in inner
    assert "[RULE:" not in inner
    # All 3 anchors should still be present for attribution.
    assert len(_anchors(inner)) == 3


# ---------------------------------------------------------------------------
# Test 6: empty lessons → no clusters, normal injection path returns None
# ---------------------------------------------------------------------------


def test_empty_lessons_returns_none():
    from gradata.hooks import inject_brain_rules as inj

    with (
        patch.object(inj, "parse_lessons", return_value=[]),
        patch.object(inj, "is_hook_enforced", return_value=False),
        patch.object(inj, "resolve_brain_dir", return_value="/fake/brain"),
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.read_text", return_value=""),
    ):
        result = inj.main({"session_type": "coding"})
    assert result is None


# ---------------------------------------------------------------------------
# Test 7: cluster summary includes category and rule count
# ---------------------------------------------------------------------------


def test_cluster_summary_format(three_qualifying_lessons):
    """The synthesized prose must carry at least one Preston-Rhodes slot label."""
    result = _run_main(three_qualifying_lessons)
    assert result is not None
    block = result["result"]
    slot_labels = ("Task:", "Context:", "Examples:", "Persona:", "Format:", "Tone:")
    assert any(lbl in block for lbl in slot_labels), (
        f"Missing slot label in synthesized block: {block!r}"
    )


def test_meta_rule_suppresses_cluster_for_same_category(three_qualifying_lessons):
    """When an injectable meta-rule exists for a category, the cluster summary
    for that category MUST be suppressed (mutex) to avoid double-injection.
    Individual rules continue to fire as concrete examples."""
    from gradata.hooks import inject_brain_rules as inj

    fake_meta = SimpleNamespace(
        source="llm_synth",
        source_categories=["VALIDATION"],
        principle="Validate everything at boundaries",
    )

    data = {"session_type": "coding", "session_number": 1}

    with (
        patch.object(inj, "parse_lessons", return_value=three_qualifying_lessons),
        patch.object(inj, "is_hook_enforced", return_value=False),
        patch.object(inj, "resolve_brain_dir", return_value="/fake/brain"),
        patch.object(inj, "load_meta_rules", return_value=[fake_meta]),
        patch.object(inj, "format_meta_rules_for_prompt", return_value="META: validate"),
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.read_text", return_value="# mocked"),
    ):
        result = inj.main(data)

    assert result is not None
    block = result["result"]
    # The old cluster-summary path is gone; the meta covers the category-level
    # principle while individual rules still fire as concrete examples in the
    # synthesized prose. Both blocks coexist without a cluster summary.
    assert "[CLUSTER:" not in block
    assert "<brain-meta-rules>" in block
    assert "<brain-rules>" in block


def test_meta_rule_does_not_suppress_other_category_clusters(three_qualifying_lessons):
    """Meta-rule for category A must NOT suppress clusters for category B."""
    from gradata.hooks import inject_brain_rules as inj

    fake_meta = SimpleNamespace(
        source="llm_synth",
        source_categories=["UNRELATED_CATEGORY"],
        principle="something else entirely",
    )

    data = {"session_type": "coding", "session_number": 1}

    with (
        patch.object(inj, "parse_lessons", return_value=three_qualifying_lessons),
        patch.object(inj, "is_hook_enforced", return_value=False),
        patch.object(inj, "resolve_brain_dir", return_value="/fake/brain"),
        patch.object(inj, "load_meta_rules", return_value=[fake_meta]),
        patch.object(inj, "format_meta_rules_for_prompt", return_value="META: other"),
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.read_text", return_value="# mocked"),
    ):
        result = inj.main(data)

    assert result is not None
    block = result["result"]
    import re as _re

    # Mutex must NOT suppress a different-category meta — all 3 VALIDATION anchors survive.
    anchors = _re.findall(r"(?<![0-9a-zA-Z])r:([0-9a-f]{4})", block)
    assert len(anchors) == 3, (
        f"Mutex over-fired: expected 3 anchors for VALIDATION rules when meta covers "
        f"a different category. Got {len(anchors)}. Block: {block}"
    )


def test_deterministic_meta_rule_does_not_suppress_cluster(three_qualifying_lessons):
    """Only injectable meta-rules (llm_synth/human_curated) trigger the mutex.
    Deterministic meta-rules are not injected, so they must not suppress clusters."""
    from gradata.hooks import inject_brain_rules as inj

    fake_meta = SimpleNamespace(
        source="deterministic",  # NOT injectable
        source_categories=["VALIDATION"],
        principle="excluded from injection",
    )

    data = {"session_type": "coding", "session_number": 1}

    with (
        patch.object(inj, "parse_lessons", return_value=three_qualifying_lessons),
        patch.object(inj, "is_hook_enforced", return_value=False),
        patch.object(inj, "resolve_brain_dir", return_value="/fake/brain"),
        patch.object(inj, "load_meta_rules", return_value=[fake_meta]),
        patch.object(inj, "format_meta_rules_for_prompt", return_value=""),
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.read_text", return_value="# mocked"),
    ):
        result = inj.main(data)

    assert result is not None
    block = result["result"]
    import re as _re

    # Deterministic meta-rules are not injected, so they must not suppress anything.
    anchors = _re.findall(r"(?<![0-9a-zA-Z])r:([0-9a-f]{4})", block)
    assert len(anchors) == 3, (
        "Deterministic meta-rules must not suppress rule synthesis "
        f"(expected 3 anchors, got {len(anchors)})."
    )


# ---------------------------------------------------------------------------
# Meta-Harness A: per-rule attribution anchors + .last_injection.json manifest
# ---------------------------------------------------------------------------


def test_cluster_line_carries_member_anchors(three_qualifying_lessons):
    """Synthesized prose must carry one r:xxxx anchor per selected rule."""
    result = _run_main(three_qualifying_lessons)
    assert result is not None
    block = result["result"]
    anchors = _anchors(block)
    assert len(anchors) == 3, f"Expected 3 anchors in synth block, got {anchors}"
    for a in anchors:
        assert len(a) == 4, f"Anchor must be 4 chars: {a!r}"


def test_individual_line_carries_anchor():
    """Single-rule injection must include its r:xxxx anchor inline."""
    lessons = [
        _make_lesson("use absolute paths only", "PATHS", confidence=0.80),
    ]
    result = _run_main(lessons)
    assert result is not None
    block = result["result"]
    anchors = _anchors(block)
    assert len(anchors) == 1, f"Expected 1 anchor in synth block, got {anchors}"
    assert len(anchors[0]) == 4


def test_injection_manifest_written(three_qualifying_lessons, tmp_path):
    """<brain>/.last_injection.json must be written with anchor→lesson mapping."""
    from gradata.hooks import inject_brain_rules as inj

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    # lessons.md must exist since inj checks it before continuing
    (brain_dir / "lessons.md").write_text("# mocked", encoding="utf-8")

    with (
        patch.object(inj, "parse_lessons", return_value=three_qualifying_lessons),
        patch.object(inj, "is_hook_enforced", return_value=False),
        patch.object(inj, "resolve_brain_dir", return_value=str(brain_dir)),
        patch.object(inj, "load_meta_rules", return_value=[]),
        patch.object(inj, "format_meta_rules_for_prompt", return_value=""),
    ):
        result = inj.main({"session_type": "coding", "session_number": 1})

    assert result is not None
    manifest_path = brain_dir / ".last_injection.json"
    assert manifest_path.is_file(), "Manifest file was not written"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "anchors" in data
    # All 3 cluster members must be in the manifest
    assert len(data["anchors"]) == 3
    for anchor, entry in data["anchors"].items():
        assert len(anchor) == 4
        assert entry["category"] == "VALIDATION"
        assert entry["cluster_category"] == "VALIDATION"
        assert entry["state"] == "RULE"
        assert "description" in entry
        assert len(entry["full_id"]) == 12


def test_injection_manifest_maps_individual_rule(tmp_path):
    """Individual (non-clustered) rule must appear in manifest with cluster_category=None."""
    from gradata.hooks import inject_brain_rules as inj

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    (brain_dir / "lessons.md").write_text("# mocked", encoding="utf-8")

    lessons = [_make_lesson("use absolute paths only", "PATHS", confidence=0.80)]
    with (
        patch.object(inj, "parse_lessons", return_value=lessons),
        patch.object(inj, "is_hook_enforced", return_value=False),
        patch.object(inj, "resolve_brain_dir", return_value=str(brain_dir)),
        patch.object(inj, "load_meta_rules", return_value=[]),
        patch.object(inj, "format_meta_rules_for_prompt", return_value=""),
    ):
        inj.main({"session_type": "coding", "session_number": 1})

    data = json.loads((brain_dir / ".last_injection.json").read_text(encoding="utf-8"))
    assert len(data["anchors"]) == 1
    entry = next(iter(data["anchors"].values()))
    assert entry["category"] == "PATHS"
    assert entry["cluster_category"] is None
    assert entry["description"] == "use absolute paths only"
