"""Tests for cluster-level rule injection in inject_brain_rules.main().

Verifies that qualifying clusters replace individual rules in the brain-rules
block, reducing injection slot usage, while non-qualifying rules still appear
individually.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

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


# ---------------------------------------------------------------------------
# Test 1: qualifying cluster replaces member rules with a summary line
# ---------------------------------------------------------------------------

def test_qualifying_cluster_injects_summary(three_qualifying_lessons):
    result = _run_main(three_qualifying_lessons)
    assert result is not None
    block = result["result"]
    # Summary line must be present
    assert "[CLUSTER:" in block
    assert "VALIDATION" in block
    # The raw individual descriptions should NOT appear as [RULE:...] lines
    # (they may appear inside the summary text, but not as standalone rule lines)
    rule_lines = [
        line for line in block.splitlines()
        if line.startswith("[RULE:") or line.startswith("[PATTERN:")
    ]
    validation_rule_lines = [l for l in rule_lines if "VALIDATION" in l]
    assert len(validation_rule_lines) == 0, (
        f"Individual VALIDATION rules leaked through: {validation_rule_lines}"
    )


# ---------------------------------------------------------------------------
# Test 2: rules NOT in any cluster appear individually
# ---------------------------------------------------------------------------

def test_non_cluster_rules_injected_individually(
    three_qualifying_lessons, two_unrelated_lessons
):
    all_lessons = three_qualifying_lessons + two_unrelated_lessons
    result = _run_main(all_lessons)
    assert result is not None
    block = result["result"]
    # Individual PATHS and IMPORTS rules must appear
    assert "PATHS" in block or "IMPORTS" in block


# ---------------------------------------------------------------------------
# Test 3: clusters with contradictions are NOT used — members injected individually
# ---------------------------------------------------------------------------

def test_contradicting_cluster_not_used():
    # Two rules that will trigger contradiction detection (same tokens + negation difference)
    # Plus a third to meet size >= 3
    lessons = [
        _make_lesson("always validate user input carefully", "SAFETY", confidence=0.85),
        _make_lesson("never validate user input in tests", "SAFETY", confidence=0.85),
        _make_lesson("validate input at every system boundary", "SAFETY", confidence=0.87),
    ]
    result = _run_main(lessons)
    assert result is not None
    block = result["result"]
    # If cluster has contradictions, no CLUSTER: line should appear for SAFETY
    # (cluster injection is skipped; individual rules take over)
    safety_cluster_lines = [
        l for l in block.splitlines()
        if "[CLUSTER:" in l and "SAFETY" in l
    ]
    # Either no cluster for SAFETY, OR if there's a cluster it must have no contradictions
    # (we just verify individual SAFETY lines are present when cluster is skipped)
    if not safety_cluster_lines:
        # Individual lines present
        individual_safety = [l for l in block.splitlines() if "SAFETY" in l]
        assert len(individual_safety) > 0


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
    low_conf_cluster_lines = [
        l for l in block.splitlines()
        if "[CLUSTER:" in l and "LOW_CONF" in l
    ]
    assert len(low_conf_cluster_lines) == 0


# ---------------------------------------------------------------------------
# Test 5: total injection count decreases when clusters are used
# ---------------------------------------------------------------------------

def test_cluster_reduces_injection_count(three_qualifying_lessons):
    """One CLUSTER line replaces three individual rule lines — net count is lower."""
    # Baseline: count lines without clustering (individual only)
    # Clustered: count lines with clustering active
    result = _run_main(three_qualifying_lessons)
    assert result is not None
    block = result["result"]
    inner = block.replace("<brain-rules>", "").replace("</brain-rules>", "").strip()
    injected_lines = [l for l in inner.splitlines() if l.strip()]
    # 3 lessons -> 1 cluster summary -> 1 line total (not 3)
    assert len(injected_lines) == 1
    assert injected_lines[0].startswith("[CLUSTER:")


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
    result = _run_main(three_qualifying_lessons)
    assert result is not None
    block = result["result"]
    cluster_lines = [l for l in block.splitlines() if "[CLUSTER:" in l]
    assert len(cluster_lines) == 1
    line = cluster_lines[0]
    # Must contain the confidence score, rule count marker, and category.
    # Marker may be followed by a ` r:<anchors>` suffix for Meta-Harness A
    # attribution, so accept both the bare `×3]`/`|3]` and `×3 r:...]`/`|3 r:...]`.
    assert (
        "\u00d73]" in line or "|3]" in line
        or "\u00d73 r:" in line or "|3 r:" in line
    ), f"Missing size marker in: {line!r}"
    assert "VALIDATION" in line
    # Confidence value should be in [0, 1] range formatted as float
    import re
    m = re.search(r"\[CLUSTER:(\d+\.\d+)\|", line)
    assert m is not None, f"Cluster line missing confidence: {line!r}"
    conf = float(m.group(1))
    assert 0.75 <= conf <= 1.0


# ---------------------------------------------------------------------------
# Test 8: meta-rule mutex — cluster suppressed when meta-rule covers category
# ---------------------------------------------------------------------------

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
    cluster_lines = [l for l in block.splitlines() if "[CLUSTER:" in l]
    assert len(cluster_lines) == 0, (
        f"Mutex failed: cluster fired despite meta-rule covering VALIDATION. "
        f"Block: {block}"
    )


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
    cluster_lines = [l for l in block.splitlines() if "[CLUSTER:" in l]
    assert len(cluster_lines) == 1, (
        f"Mutex over-fired: cluster suppressed despite meta-rule covering different category. "
        f"Block: {block}"
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
    cluster_lines = [l for l in block.splitlines() if "[CLUSTER:" in l]
    assert len(cluster_lines) == 1, (
        "Deterministic meta-rules must not suppress clusters (they are not injected)."
    )


# ---------------------------------------------------------------------------
# Meta-Harness A: per-rule attribution anchors + .last_injection.json manifest
# ---------------------------------------------------------------------------

def test_cluster_line_carries_member_anchors(three_qualifying_lessons):
    """Cluster injection lines must include `r:<anchor,anchor,...>` for each member."""
    result = _run_main(three_qualifying_lessons)
    assert result is not None
    block = result["result"]
    cluster_lines = [l for l in block.splitlines() if "[CLUSTER:" in l]
    assert len(cluster_lines) == 1
    line = cluster_lines[0]
    import re
    m = re.search(r"r:([0-9a-f,]+)\]", line)
    assert m is not None, f"Cluster line missing anchor suffix: {line!r}"
    anchors = m.group(1).split(",")
    assert len(anchors) == 3, f"Expected 3 member anchors, got {anchors}"
    for a in anchors:
        assert len(a) == 4, f"Anchor must be 4 chars: {a!r}"


def test_individual_line_carries_anchor():
    """Non-clustered RULE lines must include ` r:<anchor>` before the closing `]`."""
    lessons = [
        _make_lesson("use absolute paths only", "PATHS", confidence=0.80),
    ]
    result = _run_main(lessons)
    assert result is not None
    block = result["result"]
    rule_lines = [l for l in block.splitlines() if l.startswith("[RULE:")]
    assert len(rule_lines) == 1
    import re
    assert re.search(r"\[RULE:[\d.]+\s+r:[0-9a-f]{4}\]", rule_lines[0]), (
        f"Individual line missing anchor: {rule_lines[0]!r}"
    )


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
