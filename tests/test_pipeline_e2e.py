"""
End-to-end test for the correction -> graduation -> meta-rule -> injection pipeline.

Verifies the COMPOSED pipeline, not individual functions.
The existing unit tests in test_meta_rules.py verify individual functions.
This test verifies they compose correctly.

Run: python -m pytest tests/test_pipeline_e2e.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Try cloud-only override first (real discovery), fall back to SDK stubs
_CLOUD_DISCOVERY = False
try:
    _cloud_path = os.environ.get("GRADATA_CLOUD_PATH", "C:/Users/olive/SpritesWork/brain/cloud-only")
    sys.path.insert(0, _cloud_path)
    from meta_rules import discover_meta_rules, merge_into_meta  # type: ignore[import]
    _CLOUD_DISCOVERY = True
except ImportError:
    from gradata.enhancements.meta_rules import discover_meta_rules

_requires_cloud = pytest.mark.skipif(
    not _CLOUD_DISCOVERY, reason="requires cloud-only meta-rule discovery"
)

from gradata._types import Lesson, LessonState
from gradata.enhancements.meta_rules import (
    MetaRule,
    ensure_table,
    format_meta_rules_for_prompt,
    load_meta_rules,
    refresh_meta_rules,
    save_meta_rules,
)


SALES_CORRECTIONS = [
    {"session": 95, "draft": "Hi Matt, Great connecting today. [2-3 sentences recapping...]",
     "final": "Don't skip sales workflows (post-demo, Fireflies, Pipedrive) even when asked to 'just draft' emails",
     "category": "PROCESS"},
    {"session": 96, "draft": "Here's a quick follow-up email for your demo today...",
     "final": "Always load the sales skill router before drafting any sales deliverable",
     "category": "PROCESS"},
    {"session": 97, "draft": "I'll draft the email now based on the transcript...",
     "final": "Use the post-call skill and follow-up-emails skill, not generic drafting",
     "category": "PROCESS"},
    {"session": 98, "draft": "Let me write a quick recap email...",
     "final": "Sales emails require the full workflow: research, skill load, Fireflies, draft, CRM",
     "category": "PROCESS"},
]


def _simulate_session(brain, correction: dict) -> dict:
    result = brain.correct(
        draft=correction["draft"], final=correction["final"],
        category=correction["category"], session=correction["session"],
    )
    # Propagate real severity from the correction result
    # Try result["severity"] first (if brain.correct returns it directly),
    # fall back to result["outcome"] or nested result["data"]["severity"]
    severity = (
        result.get("severity") or
        result.get("outcome") or
        (result.get("data") or {}).get("severity") or
        "major"  # final fallback
    )
    end_result = brain.end_session(
        session_corrections=[{
            "category": correction["category"],
            "severity": severity,
            "direction": "REINFORCING",
        }],
        session_type="sales",
    )
    return {"correct": result, "end_session": end_result}


class TestPipelineE2E:

    def test_correction_logged_with_severity(self, fresh_brain):
        result = fresh_brain.correct(
            draft=SALES_CORRECTIONS[0]["draft"],
            final=SALES_CORRECTIONS[0]["final"],
            category="PROCESS", session=95,
        )
        assert result is not None
        severity = result.get("outcome") or result.get("data", {}).get("severity")
        assert severity in ("as-is", "minor", "moderate", "major", "discarded")

    def test_graduation_across_sessions(self, fresh_brain):
        for corr in SALES_CORRECTIONS[:3]:
            _simulate_session(fresh_brain, corr)
        lessons = fresh_brain._load_lessons()
        process_lessons = [l for l in lessons if l.category == "PROCESS"]
        assert len(process_lessons) > 0, "Should have PROCESS lessons after 3 corrections"

    @_requires_cloud
    def test_meta_rule_discovery_from_related_corrections(self):
        rule_lessons = [
            Lesson("2026-04-01", LessonState.RULE, 0.92, "PROCESS",
                   "Don't skip sales workflows when drafting emails"),
            Lesson("2026-04-02", LessonState.RULE, 0.90, "PROCESS",
                   "Always load sales skill router before any sales deliverable"),
            Lesson("2026-04-03", LessonState.RULE, 0.88, "PROCESS",
                   "Use post-call skill, not generic drafting for follow-ups"),
            Lesson("2026-04-04", LessonState.RULE, 0.91, "PROCESS",
                   "Sales emails need full workflow: research, skill, Fireflies, draft, CRM"),
        ]
        metas = discover_meta_rules(rule_lessons, min_group_size=3, current_session=98)
        assert len(metas) >= 1, (
            "4 RULE-graduated PROCESS lessons should produce at least 1 meta-rule. "
            "If this fails, discover_meta_rules() is still cloud-gated."
        )
        meta = metas[0]
        assert meta.id.startswith("META-")
        assert meta.confidence > 0.5
        assert "PROCESS" in meta.source_categories

    @_requires_cloud
    def test_meta_rule_has_meaningful_principle(self):
        rule_lessons = [
            Lesson("2026-04-01", LessonState.RULE, 0.92, "PROCESS",
                   "Don't skip sales workflows when drafting emails"),
            Lesson("2026-04-02", LessonState.RULE, 0.90, "PROCESS",
                   "Always load sales skill router before any sales deliverable"),
            Lesson("2026-04-03", LessonState.RULE, 0.88, "PROCESS",
                   "Use post-call skill, not generic drafting for follow-ups"),
        ]
        metas = discover_meta_rules(rule_lessons, min_group_size=3, current_session=98)
        if not metas:
            pytest.skip("discover_meta_rules not yet implemented")
        meta = metas[0]
        assert "cut:" not in meta.principle.lower(), "Principle is word-diff noise"
        assert "(requires Gradata Cloud)" not in meta.principle
        assert len(meta.principle) > 20

    @_requires_cloud
    def test_meta_rule_has_applies_when(self):
        rule_lessons = [
            Lesson("2026-04-01", LessonState.RULE, 0.92, "DRAFTING",
                   "Use colons not dashes in email prose"),
            Lesson("2026-04-02", LessonState.RULE, 0.90, "DRAFTING",
                   "No bold mid-paragraph in emails"),
            Lesson("2026-04-03", LessonState.RULE, 0.88, "DRAFTING",
                   "Tight prose, direct sentences, no decorative punctuation"),
        ]
        metas = discover_meta_rules(rule_lessons, min_group_size=3, current_session=98)
        if not metas:
            pytest.skip("discover_meta_rules not yet implemented")
        assert len(metas[0].applies_when) > 0

    @_requires_cloud
    def test_meta_rule_has_context_weights(self):
        rule_lessons = [
            Lesson("2026-04-01", LessonState.RULE, 0.92, "DRAFTING",
                   "Use colons not dashes in email prose"),
            Lesson("2026-04-02", LessonState.RULE, 0.90, "DRAFTING",
                   "No bold mid-paragraph in emails"),
            Lesson("2026-04-03", LessonState.RULE, 0.88, "DRAFTING",
                   "Tight prose, direct sentences, no decorative punctuation"),
        ]
        metas = discover_meta_rules(rule_lessons, min_group_size=3, current_session=98)
        if not metas:
            pytest.skip("discover_meta_rules not yet implemented")
        weights = metas[0].context_weights
        # The task_type for DRAFTING is "drafting" — check it has elevated weight
        task_type_weight = max(v for k, v in weights.items() if k != "default")
        assert task_type_weight >= 1.5, f"Expected elevated task_type weight, got {weights}"

    def test_format_for_injection(self):
        meta = MetaRule(
            id="META-test-e2e",
            principle="When drafting sales emails, always load the sales skill router first",
            source_categories=["PROCESS"],
            source_lesson_ids=["a", "b", "c"],
            confidence=0.90, created_session=95, last_validated_session=98,
            applies_when=["task_type=sales"],
            context_weights={"sales": 1.5, "drafting": 1.3, "default": 0.5},
        )
        output = format_meta_rules_for_prompt([meta], context="sales")
        assert "## Brain Meta-Rules" in output
        assert "META:0.90" in output

    def test_sqlite_roundtrip_preserves_conditions(self, tmp_path):
        db_path = str(tmp_path / "test_e2e.db")
        meta = MetaRule(
            id="META-roundtrip",
            principle="Test principle with conditions",
            source_categories=["PROCESS"],
            source_lesson_ids=["a", "b", "c"],
            confidence=0.85, created_session=95, last_validated_session=98,
            applies_when=["task_type=sales", "session_type=sales"],
            never_when=["task_type=system"],
            context_weights={"sales": 1.5, "drafting": 1.3, "default": 0.5},
        )
        ensure_table(db_path)
        save_meta_rules(db_path, [meta])
        loaded = load_meta_rules(db_path)
        assert len(loaded) == 1
        m = loaded[0]
        assert m.applies_when == ["task_type=sales", "session_type=sales"]
        assert m.never_when == ["task_type=system"]
        assert m.context_weights["sales"] == 1.5

    @_requires_cloud
    def test_full_pipeline_correction_to_injection(self, fresh_brain):
        """Full e2e: corrections → lessons → promote to RULE → discover → inject.

        In a real brain, graduation happens across many sessions. In this test,
        we simulate 4 corrections, then manually promote the resulting lessons
        to RULE state (as graduation would after sufficient reinforcement),
        then verify discovery + injection works.
        """
        for corr in SALES_CORRECTIONS:
            _simulate_session(fresh_brain, corr)
        lessons = fresh_brain._load_lessons()
        assert len(lessons) > 0, "No lessons created from 4 corrections"

        # Promote lessons to RULE (simulating what graduation does over many sessions)
        promoted = []
        for l in lessons:
            if l.category == "PROCESS":
                promoted.append(Lesson(
                    date=l.date, state=LessonState.RULE, confidence=0.90,
                    category=l.category, description=l.description,
                ))
            else:
                promoted.append(l)

        metas = discover_meta_rules(promoted, min_group_size=3, current_session=99)
        assert len(metas) >= 1, (
            "After 4 RULE-promoted PROCESS corrections, at least 1 meta-rule "
            "should emerge. The learning pipeline is broken."
        )
        output = format_meta_rules_for_prompt(metas)
        assert "## Brain Meta-Rules" in output
        for meta in metas:
            assert "(requires Gradata Cloud)" not in meta.principle


class TestDeduplication:

    def test_same_correction_twice_same_session(self, fresh_brain):
        corr = SALES_CORRECTIONS[0]
        r1 = fresh_brain.correct(draft=corr["draft"], final=corr["final"],
                                  category=corr["category"], session=95)
        r2 = fresh_brain.correct(draft=corr["draft"], final=corr["final"],
                                  category=corr["category"], session=95)
        assert r1 is not None
        assert r2 is not None


class TestCrossCategoryIsolation:

    @_requires_cloud
    def test_different_categories_separate_meta_rules(self):
        lessons = [
            Lesson("2026-04-01", LessonState.RULE, 0.92, "DRAFTING", "Use colons not dashes"),
            Lesson("2026-04-02", LessonState.RULE, 0.90, "DRAFTING", "No bold mid-paragraph"),
            Lesson("2026-04-03", LessonState.RULE, 0.88, "DRAFTING", "Tight prose, direct sentences"),
            Lesson("2026-04-01", LessonState.RULE, 0.92, "ARCHITECTURE", "Keep files under 500 lines"),
            Lesson("2026-04-02", LessonState.RULE, 0.90, "ARCHITECTURE", "Validate input at boundaries"),
            Lesson("2026-04-03", LessonState.RULE, 0.88, "ARCHITECTURE", "Prefer editing over creating"),
        ]
        metas = discover_meta_rules(lessons, min_group_size=3, current_session=98)
        if not metas:
            pytest.skip("discover_meta_rules not yet implemented")
        for meta in metas:
            cat_set = set(meta.source_categories)
            assert not ({"DRAFTING", "ARCHITECTURE"} <= cat_set), \
                "DRAFTING and ARCHITECTURE should not merge"


def test_correction_pattern_tracking(tmp_path):
    from gradata.enhancements.meta_rules_storage import (
        ensure_pattern_table, upsert_correction_pattern, query_graduation_candidates,
    )
    db = str(tmp_path / "test_patterns.db")
    ensure_pattern_table(db)
    upsert_correction_pattern(db, pattern_hash="abc123", category="PROCESS",
                              representative_text="Don't skip sales workflows",
                              session_id=95, severity="major")
    upsert_correction_pattern(db, pattern_hash="abc123", category="PROCESS",
                              representative_text="Don't skip sales workflows",
                              session_id=96, severity="major")
    upsert_correction_pattern(db, pattern_hash="abc123", category="PROCESS",
                              representative_text="Don't skip sales workflows",
                              session_id=97, severity="major")
    upsert_correction_pattern(db, pattern_hash="def456", category="DRAFTING",
                              representative_text="Use colons not dashes",
                              session_id=95, severity="minor")
    candidates = query_graduation_candidates(db, min_sessions=2, min_score=3.0)
    assert len(candidates) == 1
    assert candidates[0]["pattern_hash"] == "abc123"
    assert candidates[0]["distinct_sessions"] >= 3
    assert candidates[0]["weighted_score"] >= 3.0
