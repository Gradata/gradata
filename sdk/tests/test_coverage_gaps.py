import pytest; pytest.importorskip('gradata.enhancements.self_improvement', reason='requires gradata_cloud')
"""
Targeted tests to close coverage gaps in the five lowest-coverage modules.

Priority targets (by coverage %):
  _stats.py           9%
  _events.py         24%
  _self_improvement  26%
  _query.py          37%
  brain.py           39%

Run: pytest sdk/tests/test_coverage_gaps.py -v
"""

import json
import os
import re
import sqlite3
from pathlib import Path

import pytest

from gradata import Brain


# ---------------------------------------------------------------------------
# Shared helper — reused across all test classes
# ---------------------------------------------------------------------------

def _init_brain(tmp_path: Path, name: str = "GapBrain", domain: str = "Testing") -> Brain:
    """Create a fresh isolated brain and re-wire all cached module-level vars."""
    brain_dir = tmp_path / "brain"
    os.environ["BRAIN_DIR"] = str(brain_dir)
    brain = Brain.init(brain_dir, name=name, domain=domain,
                       embedding="local", interactive=False)

    import gradata._paths as _p
    import gradata._events as _ev
    import gradata._brain_manifest as _bm
    import gradata._export_brain as _ex
    import gradata._query as _q
    import gradata._tag_taxonomy as _tt

    _ev.BRAIN_DIR = _p.BRAIN_DIR
    _ev.EVENTS_JSONL = _p.EVENTS_JSONL
    _ev.DB_PATH = _p.DB_PATH

    _bm.BRAIN_DIR = _p.BRAIN_DIR
    _bm.DB_PATH = _p.DB_PATH
    _bm.EVENTS_JSONL = _p.EVENTS_JSONL
    _bm.WORKING_DIR = _p.WORKING_DIR
    _bm.MANIFEST_PATH = _p.BRAIN_DIR / "brain.manifest.json"

    _ex.BRAIN_DIR = _p.BRAIN_DIR
    _ex.WORKING_DIR = _p.WORKING_DIR
    _ex.PROSPECTS_DIR = _p.PROSPECTS_DIR
    _ex.SESSIONS_DIR = _p.SESSIONS_DIR
    _ex.VERSION_FILE = _p.VERSION_FILE
    _ex.PATTERNS_FILE = _p.PATTERNS_FILE
    _ex.CARL_DIR = _p.CARL_DIR
    _ex.GATES_DIR = _p.GATES_DIR

    _q.DB_PATH = _p.DB_PATH
    _q.BRAIN_DIR = _p.BRAIN_DIR
    # ChromaDB removed S66 — no CHROMA_DIR needed in _query
    _tt.PROSPECTS_DIR = _p.PROSPECTS_DIR
    return brain


# ===========================================================================
# 1. _stats.py  — currently 9% covered
# ===========================================================================

class TestStatsBetaPosterior:
    """Cover beta_posterior, wilson_ci, rolling_comparison, brier_score."""

    def test_beta_posterior_basic(self):
        from gradata._stats import beta_posterior
        result = beta_posterior(successes=5, trials=10)
        assert 0 < result["posterior_mean"] < 1
        assert "ci_95" in result
        assert result["ci_95"][0] < result["posterior_mean"] < result["ci_95"][1]
        assert result["confidence_label"] in ("PROVEN", "EMERGING", "HYPOTHESIS", "UNDERPERFORMING")

    def test_beta_posterior_zero_trials(self):
        from gradata._stats import beta_posterior
        result = beta_posterior(successes=0, trials=0)
        # Prior dominates; posterior_mean should be 0.5 with uniform prior
        assert result["posterior_mean"] == pytest.approx(0.5, abs=0.01)

    def test_beta_posterior_all_successes(self):
        from gradata._stats import beta_posterior
        result = beta_posterior(successes=20, trials=20)
        assert result["posterior_mean"] > 0.9
        assert result["confidence_label"] in ("PROVEN", "EMERGING")

    def test_wilson_ci_zero_total(self):
        from gradata._stats import wilson_ci
        result = wilson_ci(0, 0)
        assert result["point_estimate"] == 0
        assert "no data" in result["display"]

    def test_wilson_ci_perfect_rate(self):
        from gradata._stats import wilson_ci
        result = wilson_ci(10, 10)
        assert result["point_estimate"] == pytest.approx(1.0)
        assert result["ci_low"] > 0.5

    def test_wilson_ci_standard_case(self):
        from gradata._stats import wilson_ci
        result = wilson_ci(3, 10)
        assert result["ci_low"] < result["point_estimate"] < result["ci_high"]
        assert 0 <= result["ci_low"] and result["ci_high"] <= 1

    def test_rolling_comparison_empty(self):
        from gradata._stats import rolling_comparison
        result = rolling_comparison([])
        assert result["trend"] == "NO_DATA"

    def test_rolling_comparison_insufficient_window(self):
        from gradata._stats import rolling_comparison
        result = rolling_comparison([1.0, 2.0, 3.0], window=10)
        assert result["trend"] == "INSUFFICIENT_WINDOW"

    def test_rolling_comparison_stable(self):
        from gradata._stats import rolling_comparison
        values = [1.0] * 20  # perfectly stable
        result = rolling_comparison(values, window=5)
        assert result["trend"] == "STABLE"
        assert result["delta"] == pytest.approx(0.0)

    def test_rolling_comparison_improving(self):
        from gradata._stats import rolling_comparison
        # Lifetime avg is low, recent is much higher
        values = [0.1] * 10 + [0.9] * 10
        result = rolling_comparison(values, window=5)
        # Recent (0.9) > lifetime avg (~0.5) by >5%
        assert result["trend"] == "IMPROVING"
        assert result["pct_change"] > 0

    def test_rolling_comparison_degrading(self):
        from gradata._stats import rolling_comparison
        values = [0.9] * 10 + [0.1] * 10
        result = rolling_comparison(values, window=5)
        assert result["trend"] == "DEGRADING"

    def test_brier_score_empty(self):
        from gradata._stats import brier_score
        result = brier_score([])
        assert result["score"] is None
        assert result["calibration"] == "NO_DATA"
        assert result["n"] == 0

    def test_brier_score_perfect(self):
        from gradata._stats import brier_score
        # Perfect predictions: predicted=1.0 when outcome=1
        result = brier_score([(1.0, 1), (1.0, 1), (0.0, 0)])
        assert result["score"] == pytest.approx(0.0)
        assert result["calibration"] == "EXCELLENT"

    def test_brier_score_random(self):
        from gradata._stats import brier_score
        # Worst case: always wrong
        result = brier_score([(0.0, 1), (1.0, 0)] * 10)
        assert result["score"] == pytest.approx(1.0)
        assert result["calibration"] == "WORSE_THAN_RANDOM"

    def test_brier_score_calibration_buckets(self):
        from gradata._stats import brier_score
        # EXCELLENT: score < 0.05
        assert brier_score([(0.9, 1)] * 10)["calibration"] == "EXCELLENT"    # score=0.01
        # GOOD: 0.05 <= score < 0.10
        assert brier_score([(0.7, 1)] * 10)["calibration"] == "GOOD"         # score=0.09
        # FAIR: 0.10 <= score < 0.20
        assert brier_score([(0.6, 1)] * 10)["calibration"] == "FAIR"         # score=0.16
        # POOR: 0.20 <= score < 0.25
        assert brier_score([(0.54, 1)] * 10)["calibration"] == "POOR"        # score~0.2116
        # WORSE_THAN_RANDOM: score >= 0.25
        assert brier_score([(0.5, 1)] * 10)["calibration"] == "WORSE_THAN_RANDOM"  # score=0.25

    def test_ewma_control_insufficient(self):
        from gradata._stats import ewma_control
        result = ewma_control([0.1, 0.2])
        assert result["status"] == "INSUFFICIENT_DATA"
        assert result["ewma_current"] is None

    def test_ewma_control_in_control(self):
        from gradata._stats import ewma_control
        values = [1.0, 1.1, 0.9, 1.0, 1.1, 0.95, 1.0, 1.05, 1.0, 0.98]
        result = ewma_control(values)
        assert result["ewma_current"] is not None
        assert "IN_CONTROL" in result["status"] or "OUT_OF_CONTROL" in result["status"]

    def test_correction_half_life_empty(self):
        from gradata._stats import correction_half_life
        result = correction_half_life([])
        assert result["overall"] == "NO_DATA"

    def test_correction_half_life_single_occurrence(self):
        from gradata._stats import correction_half_life
        corrections = [{"category": "DRAFTING", "session": 3}]
        result = correction_half_life(corrections)
        assert "DRAFTING" in result["categories"]
        assert result["categories"]["DRAFTING"]["status"] == "SINGLE_OCCURRENCE"
        assert result["learned"] == 1

    def test_correction_half_life_recurring(self):
        from gradata._stats import correction_half_life
        # High density = recurring
        corrections = [{"category": "ACCURACY", "session": i} for i in range(10)]
        result = correction_half_life(corrections)
        assert result["categories"]["ACCURACY"]["status"] == "RECURRING"

    def test_task_success_rate_empty(self):
        from gradata._stats import task_success_rate
        result = task_success_rate([])
        assert result["overall_pass_rate"] is None
        assert result["by_type"] == {}

    def test_task_success_rate_mixed(self):
        from gradata._stats import task_success_rate
        events = [
            {"task_type": "email", "corrected": False},
            {"task_type": "email", "corrected": True},
            {"task_type": "research", "corrected": False},
        ]
        result = task_success_rate(events)
        assert result["by_type"]["email"]["pass_rate"] == pytest.approx(0.5)
        assert result["by_type"]["research"]["pass_rate"] == pytest.approx(1.0)
        assert result["overall_pass_rate"] == pytest.approx(2 / 3, abs=1e-3)

    def test_mtbf_mttr_empty(self):
        from gradata._stats import mtbf_mttr
        result = mtbf_mttr([], 10)
        assert result["overall_mtbf"] is None

    def test_mtbf_mttr_single_correction(self):
        from gradata._stats import mtbf_mttr
        corrections = [{"category": "DRAFTING", "session": 5}]
        result = mtbf_mttr(corrections, total_sessions=10)
        assert result["overall_mtbf"] == pytest.approx(10.0)
        assert result["by_type"]["DRAFTING"]["mtbf"] == pytest.approx(10.0)
        # Single correction: no gap, so mttr is None
        assert result["by_type"]["DRAFTING"]["mttr"] is None

    def test_naive_bayes_score(self):
        from gradata._stats import naive_bayes_score
        base_rates = {
            "_overall": 0.015,
            "title": {"CEO": 0.05, "VP": 0.03},
            "company_size": {"large": 0.025},
        }
        prospect = {"title": "CEO", "company_size": "large"}
        result = naive_bayes_score(prospect, base_rates)
        assert result["predicted_probability"] > 0.015  # should be higher than base
        assert result["confidence"] in ("HIGH", "MEDIUM", "LOW")
        assert len(result["factors"]) == 2

    def test_naive_bayes_no_matching_keys(self):
        from gradata._stats import naive_bayes_score
        base_rates = {"_overall": 0.02}
        result = naive_bayes_score({"title": "SDR"}, base_rates)
        # No matching category → multiplier stays 1.0
        assert result["predicted_probability"] == pytest.approx(0.02)
        assert result["confidence"] == "LOW"

    def test_bayesian_confidence_update_success(self):
        from gradata._stats import bayesian_confidence_update
        new_alpha, new_beta, mean = bayesian_confidence_update(1.0, 1.0, success=True)
        assert new_alpha == 2.0
        assert new_beta == 1.0
        assert mean == pytest.approx(2 / 3, abs=0.01)

    def test_bayesian_confidence_update_failure(self):
        from gradata._stats import bayesian_confidence_update
        new_alpha, new_beta, mean = bayesian_confidence_update(2.0, 1.0, success=False)
        assert new_alpha == 2.0
        assert new_beta == 2.0
        assert mean == pytest.approx(0.5, abs=0.01)


# ===========================================================================
# 2. _events.py  — currently 24% covered
# ===========================================================================

class TestEventsModule:
    """Cover emit, query, supersede, correction_rate, compute_leading_indicators,
    emit_gate_result, emit_gate_override, find_contradictions, audit_trend."""

    def test_emit_gate_result(self, tmp_path):
        brain = _init_brain(tmp_path)
        from gradata._events import emit_gate_result
        event = emit_gate_result("demo-prep", "PASS", sources_checked=["LinkedIn", "web"], detail="OK")
        assert event["type"] == "GATE_RESULT"
        assert event["data"]["gate"] == "demo-prep"
        assert event["data"]["result"] == "PASS"
        assert event["data"]["sources_complete"] is True

    def test_emit_gate_override(self, tmp_path):
        brain = _init_brain(tmp_path)
        from gradata._events import emit_gate_override
        event = emit_gate_override("demo-prep", reason="urgent call", steps_skipped=["linkedin"])
        assert event["type"] == "GATE_OVERRIDE"
        assert event["data"]["reason"] == "urgent call"
        assert "override:explicit" in event["tags"]

    def test_query_with_event_type_filter(self, tmp_path):
        brain = _init_brain(tmp_path)
        brain.emit("CORRECTION", "pytest", {"category": "DRAFTING"}, session=1)
        brain.emit("OUTPUT", "pytest", {"output_type": "email"}, session=1)

        from gradata._events import query
        corrections = query(event_type="CORRECTION")
        assert all(e["type"] == "CORRECTION" for e in corrections)
        assert len(corrections) >= 1

    def test_query_with_session_filter(self, tmp_path):
        brain = _init_brain(tmp_path)
        brain.emit("OUTPUT", "pytest", {}, session=5)
        brain.emit("OUTPUT", "pytest", {}, session=7)

        from gradata._events import query
        session5_events = query(session=5)
        assert all(e["session"] == 5 for e in session5_events)

    def test_query_last_n_sessions(self, tmp_path):
        brain = _init_brain(tmp_path)
        for s in range(10):
            brain.emit("OUTPUT", "pytest", {}, session=s)

        from gradata._events import query
        recent = query(last_n_sessions=3)
        # Should only include sessions >= max(session) - 2
        sessions = {e["session"] for e in recent}
        assert max(sessions) >= 7  # at least within last 3 sessions

    def test_query_as_of(self, tmp_path):
        brain = _init_brain(tmp_path)
        from gradata._events import query
        future = "2099-01-01T00:00:00+00:00"
        results = query(as_of=future)
        # All events have valid_from <= future, so they should all be returned
        assert isinstance(results, list)

    def test_query_active_only(self, tmp_path):
        brain = _init_brain(tmp_path)
        brain.emit("OUTPUT", "pytest", {}, session=1)
        from gradata._events import query
        active = query(active_only=True)
        # All emitted events without valid_until should be returned
        assert isinstance(active, list)
        assert all(e.get("valid_until") is None for e in active)

    def test_supersede(self, tmp_path):
        brain = _init_brain(tmp_path)
        from gradata._events import query, supersede
        brain.emit("FACT", "pytest", {"value": "old"}, session=1)
        events = query(event_type="FACT")
        original_id = events[-1]["id"]

        replacement = supersede(original_id, new_data={"value": "updated"}, source="test")
        assert replacement is not None
        assert replacement["data"]["value"] == "updated"
        assert replacement["superseded_id"] == original_id

        # Original should now have valid_until set
        conn = sqlite3.connect(str(brain.db_path))
        row = conn.execute("SELECT valid_until FROM events WHERE id = ?", (original_id,)).fetchone()
        conn.close()
        assert row[0] is not None

    def test_supersede_nonexistent(self, tmp_path):
        brain = _init_brain(tmp_path)
        from gradata._events import supersede
        result = supersede(999999)
        assert result is None

    def test_correction_rate(self, tmp_path):
        brain = _init_brain(tmp_path)
        brain.emit("CORRECTION", "pytest", {"category": "DRAFTING"}, session=3)
        brain.emit("CORRECTION", "pytest", {"category": "ACCURACY"}, session=3)
        brain.emit("CORRECTION", "pytest", {"category": "DRAFTING"}, session=4)

        from gradata._events import correction_rate
        rates = correction_rate(last_n_sessions=5)
        assert isinstance(rates, dict)
        assert rates.get(3) == 2
        assert rates.get(4) == 1

    def test_compute_leading_indicators_empty(self, tmp_path):
        brain = _init_brain(tmp_path)
        from gradata._events import compute_leading_indicators
        indicators = compute_leading_indicators(session=99)
        assert "first_draft_acceptance" in indicators
        assert "correction_density" in indicators
        assert "source_coverage" in indicators
        assert "confidence_calibration" in indicators
        # All should be zero/defaults for an empty session
        assert indicators["first_draft_acceptance"] == pytest.approx(0.0)

    def test_compute_leading_indicators_with_data(self, tmp_path):
        brain = _init_brain(tmp_path)
        brain.emit("OUTPUT", "pytest", {"output_type": "email", "major_edit": False}, session=10)
        brain.emit("OUTPUT", "pytest", {"output_type": "email", "major_edit": True}, session=10)
        brain.emit("GATE_RESULT", "pytest", {"gate": "demo", "sources_complete": True}, session=10)

        from gradata._events import compute_leading_indicators
        ind = compute_leading_indicators(session=10)
        assert ind["first_draft_acceptance"] == pytest.approx(0.5)
        assert ind["correction_density"] == pytest.approx(0.0)  # no CORRECTION events
        assert ind["source_coverage"] == pytest.approx(1.0)

    def test_compute_leading_indicators_calibration_v1(self, tmp_path):
        """v1 calibration format: delta-based events."""
        brain = _init_brain(tmp_path)
        brain.emit("CALIBRATION", "pytest", {"delta": 0, "self_score": 8, "oliver_score": 8}, session=5)
        brain.emit("CALIBRATION", "pytest", {"delta": 1, "self_score": 7, "oliver_score": 8}, session=5)

        from gradata._events import compute_leading_indicators
        ind = compute_leading_indicators(session=5)
        assert 0 <= ind["confidence_calibration"] <= 1.0

    def test_compute_leading_indicators_calibration_v2(self, tmp_path):
        """v2 calibration format: brier_score events."""
        brain = _init_brain(tmp_path)
        brain.emit("CALIBRATION", "pytest",
                   {"brier_score": 0.04, "calibration_rating": "EXCELLENT"}, session=6)

        from gradata._events import compute_leading_indicators
        ind = compute_leading_indicators(session=6)
        # brier_score=0.04 → confidence_calibration = 1.0 - 0.04 = 0.96
        assert ind["confidence_calibration"] == pytest.approx(0.96, abs=0.01)

    def test_find_contradictions_no_conflicts(self, tmp_path):
        brain = _init_brain(tmp_path)
        brain.emit("FACT", "pytest", {"value": "A"}, tags=["prospect:Alice"], session=1)
        brain.emit("FACT", "pytest", {"value": "B"}, tags=["prospect:Bob"], session=1)

        from gradata._events import find_contradictions
        conflicts = find_contradictions(event_type="FACT", tag_prefix="prospect:")
        # Different prospects → no shared tags → no conflicts
        assert isinstance(conflicts, list)
        # Alice and Bob have different tags so zero conflicts
        assert len(conflicts) == 0

    def test_find_contradictions_detects_overlap(self, tmp_path):
        brain = _init_brain(tmp_path)
        brain.emit("FACT", "pytest", {"value": "old"}, tags=["prospect:Alice"], session=1)
        brain.emit("FACT", "pytest", {"value": "new"}, tags=["prospect:Alice"], session=2)

        from gradata._events import find_contradictions
        conflicts = find_contradictions(event_type="FACT", tag_prefix="prospect:")
        # Same type, same prospect tag, both active → contradiction
        assert len(conflicts) >= 1
        assert conflicts[0]["shared_tags"] == ["prospect:Alice"]

    def test_audit_trend(self, tmp_path):
        brain = _init_brain(tmp_path)
        brain.emit("AUDIT_SCORE", "pytest", {"score": 8.5, "rubric": "quality"}, session=1)
        brain.emit("AUDIT_SCORE", "pytest", {"score": 9.0, "rubric": "quality"}, session=2)

        from gradata._events import audit_trend
        trend = audit_trend(last_n_sessions=5)
        assert isinstance(trend, list)
        assert len(trend) >= 2
        assert all("session" in t and "data" in t for t in trend)

    def test_detect_session_from_loop_state(self, tmp_path):
        brain = _init_brain(tmp_path)
        # Write a loop-state.md with a session number
        loop_state = brain.dir / "loop-state.md"
        loop_state.write_text("# Loop State\n\nSession 42 — ongoing.\n", encoding="utf-8")

        import gradata._paths as _p
        import gradata._events as _ev
        _ev.BRAIN_DIR = _p.BRAIN_DIR

        from gradata._events import _detect_session
        session = _detect_session()
        assert session == 42

    def test_emit_valid_from_valid_until(self, tmp_path):
        brain = _init_brain(tmp_path)
        from gradata._events import emit
        event = emit(
            "FACT", "pytest",
            data={"value": "test"},
            valid_from="2026-01-01T00:00:00+00:00",
            valid_until="2026-12-31T00:00:00+00:00",
        )
        assert event["valid_from"] == "2026-01-01T00:00:00+00:00"
        assert event["valid_until"] == "2026-12-31T00:00:00+00:00"


# ===========================================================================
# 3. _self_improvement.py  — currently 26% covered
# ===========================================================================

class TestSelfImprovement:
    """Cover parse_lessons, update_confidence, format_lessons, graduate,
    compute_learning_velocity."""

    _SAMPLE_MD = """\
[2026-01-01] [INSTINCT:0.30] DRAFTING: Always hyperlink URLs. Root cause: Forgot to add link.

[2026-01-02] [PATTERN:0.70] ACCURACY: Cross-check facts before stating.

[2026-01-03] [RULE] PROCESS: Wrap-up is mandatory, no exceptions.

[2026-01-04] [UNTESTABLE] TONE: Avoid passive voice.
"""

    def test_parse_lessons_counts(self):
        from gradata._self_improvement import parse_lessons
        lessons = parse_lessons(self._SAMPLE_MD)
        assert len(lessons) == 4

    def test_parse_lessons_instinct(self):
        from gradata._self_improvement import parse_lessons, LessonState
        lessons = parse_lessons(self._SAMPLE_MD)
        instincts = [l for l in lessons if l.state == LessonState.INSTINCT]
        assert len(instincts) == 1
        assert instincts[0].confidence == pytest.approx(0.30)
        assert instincts[0].category == "DRAFTING"
        assert "hyperlink" in instincts[0].description.lower()
        assert "Forgot to add link" in instincts[0].root_cause

    def test_parse_lessons_rule_has_no_score(self):
        from gradata._self_improvement import parse_lessons, LessonState
        lessons = parse_lessons(self._SAMPLE_MD)
        rules = [l for l in lessons if l.state == LessonState.RULE]
        assert len(rules) == 1
        assert rules[0].confidence == pytest.approx(0.90)

    def test_parse_lessons_untestable(self):
        from gradata._self_improvement import parse_lessons, LessonState
        lessons = parse_lessons(self._SAMPLE_MD)
        untestedables = [l for l in lessons if l.state == LessonState.UNTESTABLE]
        assert len(untestedables) == 1
        assert untestedables[0].confidence == pytest.approx(0.0)

    def test_parse_lessons_empty_text(self):
        from gradata._self_improvement import parse_lessons
        lessons = parse_lessons("")
        assert lessons == []

    def test_parse_lessons_headers_skipped(self):
        from gradata._self_improvement import parse_lessons
        text = "# My Lessons\n\nSome preamble text.\n\n[2026-03-01] [INSTINCT:0.40] TONE: Be direct.\n"
        lessons = parse_lessons(text)
        assert len(lessons) == 1
        assert lessons[0].category == "TONE"

    def test_parse_lessons_pattern_default_confidence(self):
        from gradata._self_improvement import parse_lessons, LessonState
        text = "[2026-01-01] [PATTERN] ACCURACY: Check numbers.\n"
        lessons = parse_lessons(text)
        assert len(lessons) == 1
        assert lessons[0].state == LessonState.PATTERN
        # Default for unscored pattern
        assert lessons[0].confidence == pytest.approx(0.70)

    def test_update_confidence_contradiction(self):
        from gradata._self_improvement import parse_lessons, update_confidence, LessonState
        from gradata.enhancements.self_improvement import fsrs_penalty
        lessons = parse_lessons("[2026-01-01] [INSTINCT:0.50] DRAFTING: Hyperlink URLs.\n")
        updated = update_confidence(lessons, [{"category": "DRAFTING"}])
        expected = round(0.50 - fsrs_penalty(0.50), 2)
        assert updated[0].confidence == pytest.approx(expected)

    def test_update_confidence_survival_bonus(self):
        from gradata._self_improvement import parse_lessons, update_confidence, LessonState
        from gradata.enhancements.self_improvement import fsrs_bonus
        lessons = parse_lessons("[2026-01-01] [INSTINCT:0.50] DRAFTING: Hyperlink URLs.\n")
        # Correction in different category — lesson survives
        updated = update_confidence(lessons, [{"category": "ACCURACY"}])
        expected = round(0.50 + fsrs_bonus(0.50), 2)
        assert updated[0].confidence == pytest.approx(expected)

    def test_update_confidence_no_corrections(self):
        from gradata._self_improvement import parse_lessons, update_confidence
        lessons = parse_lessons("[2026-01-01] [INSTINCT:0.50] DRAFTING: Hyperlink URLs.\n")
        original_conf = lessons[0].confidence
        # No corrections → sessions_since_fire increments but confidence unchanged
        updated = update_confidence(lessons, [])
        assert updated[0].confidence == original_conf
        assert updated[0].sessions_since_fire == 1

    def test_update_confidence_promotion_instinct_to_pattern(self):
        from gradata._self_improvement import parse_lessons, update_confidence, LessonState
        lessons = parse_lessons("[2026-01-01] [INSTINCT:0.55] DRAFTING: Hyperlink URLs.\n")
        lessons[0].fire_count = 3  # MIN_APPLICATIONS_FOR_PATTERN
        updated = update_confidence(lessons, [{"category": "TONE"}])
        assert updated[0].state == LessonState.PATTERN

    def test_update_confidence_promotion_pattern_to_rule(self):
        from gradata._self_improvement import parse_lessons, update_confidence, LessonState
        lessons = parse_lessons("[2026-01-01] [PATTERN:0.85] DRAFTING: Hyperlink URLs.\n")
        lessons[0].fire_count = 5  # MIN_APPLICATIONS_FOR_RULE
        updated = update_confidence(lessons, [{"category": "TONE"}])
        assert updated[0].state == LessonState.RULE

    def test_update_confidence_rule_demoted_on_contradiction(self):
        from gradata._self_improvement import parse_lessons, update_confidence, LessonState
        from gradata.enhancements.self_improvement import fsrs_penalty
        lessons = parse_lessons("[2026-01-01] [RULE:0.95] PROCESS: Wrap-up mandatory.\n")
        conf_before = lessons[0].confidence
        updated = update_confidence(lessons, [{"category": "PROCESS"}])
        # RULE CAN be demoted — FSRS penalty applies (confidence-dependent)
        expected_penalty = fsrs_penalty(conf_before)
        assert updated[0].confidence == round(conf_before - expected_penalty, 2)

    def test_update_confidence_untestable_flag(self):
        from gradata._self_improvement import parse_lessons, update_confidence, LessonState
        lessons = parse_lessons("[2026-01-01] [INSTINCT:0.40] TONE: Be concise.\n")
        lessons[0].sessions_since_fire = 19
        # One more session with no corrections → hits 20 → UNTESTABLE
        updated = update_confidence(lessons, [])
        assert updated[0].state == LessonState.UNTESTABLE

    def test_format_lessons_roundtrip(self):
        from gradata._self_improvement import parse_lessons, format_lessons
        original = (
            "[2026-01-01] [INSTINCT:0.30] DRAFTING: Hyperlink URLs. Root cause: Forgot.\n\n"
            "[2026-01-02] [PATTERN:0.70] ACCURACY: Check facts.\n"
        )
        lessons = parse_lessons(original)
        serialized = format_lessons(lessons)
        # Re-parse to verify round-trip fidelity
        re_parsed = parse_lessons(serialized)
        assert len(re_parsed) == len(lessons)
        assert re_parsed[0].category == lessons[0].category
        assert re_parsed[0].confidence == pytest.approx(lessons[0].confidence)
        assert re_parsed[0].root_cause == lessons[0].root_cause

    def test_format_lessons_rule_includes_confidence(self):
        from gradata._self_improvement import parse_lessons, format_lessons
        text = "[2026-01-01] [RULE] PROCESS: Wrap-up mandatory.\n"
        lessons = parse_lessons(text)
        output = format_lessons(lessons)
        assert "[RULE:" in output
        assert "PROCESS" in output

    def test_graduate_splits_correctly(self):
        from gradata._self_improvement import parse_lessons, graduate, LessonState
        text = (
            "[2026-01-01] [INSTINCT:0.40] TONE: Be direct.\n\n"
            "[2026-01-02] [RULE] PROCESS: Wrap-up.\n\n"
            "[2026-01-03] [UNTESTABLE] STYLE: Avoid filler.\n"
        )
        lessons = parse_lessons(text)
        active, graduated = graduate(lessons)
        assert len(active) == 1
        assert active[0].state == LessonState.INSTINCT
        assert len(graduated) == 2
        assert all(l.state in (LessonState.RULE, LessonState.UNTESTABLE) for l in graduated)

    def test_compute_learning_velocity_empty(self):
        from gradata._self_improvement import compute_learning_velocity
        result = compute_learning_velocity([])
        assert result["graduation_rate"] == 0.0
        assert result["total_lessons"] == 0

    def test_compute_learning_velocity_full(self):
        from gradata._self_improvement import parse_lessons, compute_learning_velocity
        text = (
            "[2026-01-01] [INSTINCT:0.40] TONE: Be direct.\n\n"
            "[2026-01-02] [PATTERN:0.70] ACCURACY: Check facts.\n\n"
            "[2026-01-03] [RULE] PROCESS: Wrap-up.\n\n"
            "[2026-01-04] [RULE] DRAFTING: Hyperlink URLs.\n"
        )
        lessons = parse_lessons(text)
        result = compute_learning_velocity(lessons)
        assert result["total_lessons"] == 4
        assert result["graduation_rate"] == pytest.approx(0.5)  # 2 rules out of 4
        assert "INSTINCT" in result["state_distribution"]
        assert "RULE" in result["state_distribution"]
        assert result["state_distribution"]["RULE"] == 2
        assert result["avg_time_to_rule"] >= 0


# ===========================================================================
# 4. _query.py  — currently 37% covered
# ===========================================================================

class TestQueryModule:
    """Cover fts_index, fts_index_batch, fts_search, detect_query_mode,
    reciprocal_rank_fusion, compute_recency_weight, classify_confidence,
    infer_memory_type."""

    def test_fts_index_and_search(self, tmp_path):
        brain = _init_brain(tmp_path)
        from gradata._query import fts_index, fts_search
        fts_index("prospects/Acme.md", "prospect", "Budget concerns raised by CEO.", "2026-01-01")
        results = fts_search("Budget")
        assert len(results) >= 1
        assert results[0]["source"] == "prospects/Acme.md"
        assert "Budget" in results[0]["text"]

    def test_fts_index_batch(self, tmp_path):
        brain = _init_brain(tmp_path)
        from gradata._query import fts_index_batch, fts_search
        docs = [
            {"source": "sessions/s1.md", "file_type": "session", "text": "Retrospective notes.", "embed_date": "2026-01-01"},
            {"source": "sessions/s2.md", "file_type": "session", "text": "Follow-up action items.", "embed_date": "2026-01-02"},
        ]
        fts_index_batch(docs)
        results = fts_search("Retrospective")
        assert any(r["source"] == "sessions/s1.md" for r in results)

    def test_fts_search_no_results(self, tmp_path):
        brain = _init_brain(tmp_path)
        from gradata._query import fts_search
        results = fts_search("xyzzy_nonexistent_token_99999")
        assert results == []

    def test_fts_search_file_type_filter(self, tmp_path):
        brain = _init_brain(tmp_path)
        from gradata._query import fts_index_batch, fts_search
        docs = [
            {"source": "prospects/A.md", "file_type": "prospect", "text": "AI tooling budget.", "embed_date": "2026-01-01"},
            {"source": "sessions/S1.md", "file_type": "session", "text": "AI tooling notes.", "embed_date": "2026-01-01"},
        ]
        fts_index_batch(docs)
        results = fts_search("tooling", file_type="prospect")
        assert all(r["file_type"] == "prospect" for r in results)

    def test_detect_query_mode_keyword_quoted(self):
        from gradata._query import detect_query_mode
        assert detect_query_mode('"exact phrase"') == "keyword"
        assert detect_query_mode("'exact phrase'") == "keyword"

    def test_detect_query_mode_keyword_short(self):
        from gradata._query import detect_query_mode
        assert detect_query_mode("budget") == "keyword"
        assert detect_query_mode("two words") == "keyword"

    def test_detect_query_mode_semantic_question(self):
        from gradata._query import detect_query_mode
        assert detect_query_mode("what is the company budget") == "semantic"
        assert detect_query_mode("how does the product work") == "semantic"

    def test_detect_query_mode_hybrid_proper_noun(self):
        from gradata._query import detect_query_mode
        # Proper noun in multi-word query → hybrid
        assert detect_query_mode("Hassan Ali budget concerns") == "hybrid"

    def test_reciprocal_rank_fusion_merges(self):
        from gradata._query import reciprocal_rank_fusion
        list_a = [
            {"source": "a.md", "text": "AAA"},
            {"source": "b.md", "text": "BBB"},
        ]
        list_b = [
            {"source": "b.md", "text": "BBB"},
            {"source": "c.md", "text": "CCC"},
        ]
        merged = reciprocal_rank_fusion([list_a, list_b])
        sources = [r["source"] for r in merged]
        # b.md appears in both lists → should rank first
        assert sources[0] == "b.md"
        assert len(merged) == 3

    def test_reciprocal_rank_fusion_empty(self):
        from gradata._query import reciprocal_rank_fusion
        assert reciprocal_rank_fusion([]) == []
        assert reciprocal_rank_fusion([[]]) == []

    def test_compute_recency_weight_fresh(self):
        from gradata._query import compute_recency_weight
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        weight = compute_recency_weight(today)
        assert weight == pytest.approx(1.0, abs=0.01)

    def test_compute_recency_weight_old(self):
        from gradata._query import compute_recency_weight, RECENCY_FLOOR
        weight = compute_recency_weight("2000-01-01")
        assert weight == pytest.approx(RECENCY_FLOOR, abs=0.01)

    def test_compute_recency_weight_invalid(self):
        from gradata._query import compute_recency_weight, RECENCY_FLOOR
        weight = compute_recency_weight("not-a-date")
        assert weight == pytest.approx(RECENCY_FLOOR, abs=0.01)

    def test_compute_recency_weight_future(self):
        from gradata._query import compute_recency_weight
        weight = compute_recency_weight("2099-12-31")
        assert weight == pytest.approx(1.0, abs=0.01)

    def test_classify_confidence(self):
        from gradata._query import classify_confidence, CONFIDENCE_HIGH, CONFIDENCE_MED, CONFIDENCE_LOW
        assert classify_confidence(CONFIDENCE_HIGH) == "high"
        assert classify_confidence(CONFIDENCE_MED) == "medium"
        assert classify_confidence(CONFIDENCE_LOW) == "low"
        assert classify_confidence(0.0) == "below_threshold"

    def test_infer_memory_type_strategic(self):
        from gradata._query import infer_memory_type
        assert infer_memory_type("general", "competitive-intelligence/report.md") == "strategic"
        assert infer_memory_type("general", "forecasting/Q2.md") == "strategic"

    def test_infer_memory_type_procedural(self):
        from gradata._query import infer_memory_type
        assert infer_memory_type("general", "follow-up-cadence.md") == "procedural"
        assert infer_memory_type("general", "patterns.md") == "procedural"

    def test_infer_memory_type_episodic(self):
        from gradata._query import infer_memory_type
        assert infer_memory_type("general", "loop-state.md") == "episodic"
        assert infer_memory_type("general", "calibration-audit.md") == "episodic"

    def test_infer_memory_type_fallback_to_map(self):
        from gradata._query import infer_memory_type, MEMORY_TYPE_MAP
        # A prospect file with no special patterns
        result = infer_memory_type("prospect", "prospects/Acme.md")
        assert result == MEMORY_TYPE_MAP.get("prospect", "semantic")

    def test_brain_search_keyword_mode(self, tmp_path):
        brain = _init_brain(tmp_path)
        # Index some content
        prospect_file = brain.dir / "prospects" / "Zephyr Corp.md"
        prospect_file.write_text(
            "# Zephyr Corp\nPain point: rocketship manufacturing delay.\n",
            encoding="utf-8",
        )
        from gradata._query import fts_rebuild, brain_search
        fts_rebuild()
        results = brain_search("rocketship", mode="keyword")
        assert len(results) >= 1
        assert any("rocketship" in r.get("text", "").lower() for r in results)
        assert all(r.get("retrieval_mode") == "keyword" for r in results)


# ===========================================================================
# 5. brain.py  — currently 39% covered
# ===========================================================================

class TestBrainClass:
    """Cover Brain.__init__ error, _grep_search, stats, context_for fallback,
    emit fallback, extract_facts, get_facts, query_events, manifest fallback."""

    def test_init_missing_dir_raises(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            Brain(nonexistent)

    def test_repr(self, tmp_path):
        brain = _init_brain(tmp_path)
        assert repr(brain).startswith("Brain(")
        assert str(brain.dir) in repr(brain)

    def test_stats_structure(self, tmp_path):
        brain = _init_brain(tmp_path)
        stats = brain.stats()
        assert "brain_dir" in stats
        assert "markdown_files" in stats
        assert "db_size_mb" in stats
        assert "has_manifest" in stats
        assert stats["has_manifest"] is True

    def test_stats_counts_markdown_files(self, tmp_path):
        brain = _init_brain(tmp_path)
        # Add markdown files
        (brain.dir / "prospects" / "Alice.md").write_text("# Alice\nNotes.\n", encoding="utf-8")
        (brain.dir / "prospects" / "Bob.md").write_text("# Bob\nNotes.\n", encoding="utf-8")
        stats = brain.stats()
        assert stats["markdown_files"] >= 2

    def test_grep_search_finds_match(self, tmp_path):
        brain = _init_brain(tmp_path)
        (brain.dir / "prospects" / "Test.md").write_text(
            "# Test Prospect\nUnique phrase: XYZZY9999.\n", encoding="utf-8"
        )
        results = brain._grep_search("XYZZY9999", top_k=5)
        assert len(results) >= 1
        assert results[0]["source"].endswith(".md")
        assert results[0]["score"] == 1.0
        assert results[0]["confidence"] == "keyword_match"

    def test_grep_search_no_match(self, tmp_path):
        brain = _init_brain(tmp_path)
        results = brain._grep_search("zzznomatch_absurdquery", top_k=5)
        assert results == []

    def test_grep_search_respects_top_k(self, tmp_path):
        brain = _init_brain(tmp_path)
        for i in range(10):
            (brain.dir / "prospects" / f"Person{i}.md").write_text(
                f"# Person {i}\nCommon term: rocketship.\n", encoding="utf-8"
            )
        results = brain._grep_search("rocketship", top_k=3)
        assert len(results) <= 3

    def test_context_for_fallback(self, tmp_path):
        """context_for falls back to _grep_search when _context_compile is unavailable."""
        brain = _init_brain(tmp_path)
        (brain.dir / "prospects" / "Fallback.md").write_text(
            "# Fallback Corp\nThey need pipeline automation.\n", encoding="utf-8"
        )
        ctx = brain.context_for("pipeline automation")
        # Should return either empty string or a formatted context block
        assert isinstance(ctx, str)

    def test_context_for_returns_brain_context_header(self, tmp_path):
        """When search finds results, context includes ## Brain Context."""
        brain = _init_brain(tmp_path)
        (brain.dir / "prospects" / "Found.md").write_text(
            "# Found Corp\nThey have a rocketship_pipeline_xyz_unique budget issue.\n",
            encoding="utf-8",
        )
        ctx = brain.context_for("rocketship_pipeline_xyz_unique")
        if ctx:  # Only assert structure if results were found
            assert "Brain Context" in ctx

    def test_get_facts_returns_list(self, tmp_path):
        brain = _init_brain(tmp_path)
        # Module may or may not be importable — either way returns list
        result = brain.get_facts(prospect="Alice")
        assert isinstance(result, list)

    def test_extract_facts_returns_int(self, tmp_path):
        brain = _init_brain(tmp_path)
        result = brain.extract_facts()
        assert isinstance(result, int)
        assert result >= 0

    def test_query_events_returns_list(self, tmp_path):
        brain = _init_brain(tmp_path)
        brain.emit("OUTPUT", "pytest", {}, session=1)
        result = brain.query_events(event_type="OUTPUT")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_search_semantic_falls_back_to_fts5(self, tmp_path):
        """search() in semantic mode uses FTS5 (ChromaDB removed S66)."""
        brain = _init_brain(tmp_path)
        # Semantic mode should work without errors, falling back to FTS5
        results = brain.search("test query", mode="semantic")
        assert isinstance(results, list)

    def test_search_hybrid_falls_back_to_fts5(self, tmp_path):
        """search() in hybrid mode uses FTS5 (ChromaDB removed S66)."""
        brain = _init_brain(tmp_path)
        results = brain.search("test query", mode="hybrid")
        assert isinstance(results, list)

    def test_manifest_fallback_on_import_error(self, tmp_path):
        """manifest() returns minimal dict when _brain_manifest is unavailable."""
        brain = _init_brain(tmp_path)
        # Patch the import to simulate ImportError
        import unittest.mock as mock
        import builtins
        real_import = builtins.__import__

        def patched_import(name, *args, **kwargs):
            if name == "gradata._brain_manifest":
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=patched_import):
            result = brain.manifest()

        assert "schema_version" in result
        assert result["schema_version"] == "1.0.0"


# ===========================================================================
# 6. _export_brain.py  — currently 79% covered  (gap-fill)
# ===========================================================================

class TestExportBrainModule:
    """Cover sanitize_content patterns, sanitize_filename, build_prospect_map,
    read_version, read_domain_name, read_session_count, collect_brain_files,
    collect_domain_files, export_brain domain-only mode."""

    def test_sanitize_email(self):
        from gradata._export_brain import sanitize_content
        text = "Contact: user@example.com for details."
        result = sanitize_content(text, {})
        assert "user@example.com" not in result
        assert "[EMAIL_REDACTED]" in result

    def test_sanitize_phone(self):
        from gradata._export_brain import sanitize_content
        text = "Call me at +1 (555) 867-5309."
        result = sanitize_content(text, {})
        assert "867-5309" not in result
        assert "[PHONE_REDACTED]" in result

    def test_sanitize_api_key(self):
        from gradata._export_brain import sanitize_content
        text = "api_key: sk-abc123secret"
        result = sanitize_content(text, {})
        assert "sk-abc123secret" not in result
        assert "[API_KEY_REDACTED]" in result

    def test_sanitize_user_path(self):
        from gradata._export_brain import sanitize_content
        text = r"Path: C:\Users\oliver\brain"
        result = sanitize_content(text, {})
        assert "C:\\Users\\oliver" not in result.replace("/", "\\")
        assert "[USER_HOME]" in result

    def test_sanitize_pipedrive_url(self):
        from gradata._export_brain import sanitize_content
        text = "Deal at https://acme.pipedrive.com/deals/123"
        result = sanitize_content(text, {})
        assert "pipedrive.com" not in result
        assert "[PIPEDRIVE_URL_REDACTED]" in result

    def test_sanitize_prospect_name_replacement(self):
        from gradata._export_brain import sanitize_content
        name_map = {"John Smith": "[PROSPECT_1]"}
        text = "Meeting with John Smith at 10am."
        result = sanitize_content(text, name_map)
        assert "John Smith" not in result
        assert "[PROSPECT_1]" in result

    def test_sanitize_content_short_names_not_replaced(self):
        from gradata._export_brain import sanitize_content
        # Names shorter than 3 chars should be skipped
        name_map = {"Jo": "[PROSPECT_1]"}
        text = "Meet Jo today."
        result = sanitize_content(text, name_map)
        assert "Jo" in result  # not replaced

    def test_sanitize_filename(self):
        from gradata._export_brain import sanitize_filename
        name_map = {"John Smith": "[PROSPECT_1]"}
        result = sanitize_filename("brain/prospects/John Smith.md", name_map)
        assert "John Smith" not in result
        assert "[PROSPECT_1]" in result

    def test_build_prospect_map_empty_dir(self, tmp_path):
        from gradata._export_brain import build_prospect_map
        empty = tmp_path / "empty_prospects"
        empty.mkdir()
        result = build_prospect_map(empty)
        # Owner name is auto-detected from manifest, not hardcoded
        assert isinstance(result, dict)

    def test_build_prospect_map_with_files(self, tmp_path):
        from gradata._export_brain import build_prospect_map
        prospects = tmp_path / "prospects"
        prospects.mkdir()
        (prospects / "Alice Johnson - Acme Corp.md").write_text(
            "name: Alice Johnson\ncompany: Acme Corp\n", encoding="utf-8"
        )
        (prospects / "Bob Smith.md").write_text(
            "name: Bob Smith\n", encoding="utf-8"
        )
        result = build_prospect_map(prospects)
        assert "Alice Johnson" in result
        assert "Acme Corp" in result
        assert "Bob Smith" in result

    def test_build_prospect_map_skips_underscore_files(self, tmp_path):
        from gradata._export_brain import build_prospect_map
        prospects = tmp_path / "prospects"
        prospects.mkdir()
        (prospects / "_template.md").write_text("# Template\n", encoding="utf-8")
        result = build_prospect_map(prospects)
        # _template.md should be skipped — map has no entry beyond Oliver
        assert "template" not in " ".join(result.keys()).lower()

    def test_read_version_missing_file(self, tmp_path):
        import gradata._paths as _p
        import gradata._export_brain as _ex
        orig = _p.VERSION_FILE
        _p.VERSION_FILE = tmp_path / "nonexistent_VERSION.md"
        try:
            from gradata._export_brain import read_version
            # Need to re-import to pick up the changed path
            result = read_version()
            assert result == "v0.0.0"
        finally:
            _p.VERSION_FILE = orig

    def test_read_session_count_missing_file(self, tmp_path):
        import gradata._paths as _p
        orig = _p.VERSION_FILE
        _p.VERSION_FILE = tmp_path / "nonexistent_VERSION.md"
        try:
            from gradata._export_brain import read_session_count
            assert read_session_count() == 0
        finally:
            _p.VERSION_FILE = orig

    def test_count_lessons_missing_file(self, tmp_path):
        from gradata._export_brain import count_lessons
        nonexistent = tmp_path / "lessons.md"
        assert count_lessons(nonexistent) == 0

    def test_count_lessons_with_entries(self, tmp_path):
        from gradata._export_brain import count_lessons
        f = tmp_path / "lessons.md"
        f.write_text(
            "[2026-01-01] [INSTINCT:0.40] TONE: Lesson one.\n"
            "[2026-01-02] [PATTERN:0.70] ACCURACY: Lesson two.\n",
            encoding="utf-8",
        )
        assert count_lessons(f) == 2

    def test_collect_brain_files_no_prospects(self, tmp_path):
        brain = _init_brain(tmp_path)
        from gradata._export_brain import collect_brain_files
        files = collect_brain_files(include_prospects=False)
        sources = [arc for arc, _ in files]
        assert not any("prospects" in s for s in sources)

    def test_export_domain_only_mode(self, tmp_path):
        """export_brain with domain_only=True omits prospect files."""
        import zipfile as _zipfile
        brain = _init_brain(tmp_path)
        (brain.dir / "prospects" / "Secret Person.md").write_text(
            "name: Secret Person\nemail: secret@example.com\n", encoding="utf-8"
        )
        from gradata._export_brain import export_brain
        zip_path = export_brain(include_prospects=True, domain_only=True)
        assert zip_path.exists()
        with _zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        # domain-only: no brain/prospects/ entries
        assert not any("prospects" in n for n in names)

    def test_export_no_prospects_mode(self, tmp_path):
        """export_brain with include_prospects=False excludes prospect files."""
        import zipfile as _zipfile
        brain = _init_brain(tmp_path)
        (brain.dir / "prospects" / "Hidden.md").write_text(
            "name: Hidden\nemail: hidden@corp.com\n", encoding="utf-8"
        )
        from gradata._export_brain import export_brain
        zip_path = export_brain(include_prospects=False, domain_only=False)
        assert zip_path.exists()
        with _zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert not any("prospects" in n for n in names)


# ===========================================================================
# 7. onboard.py  — currently 55% covered (gap-fill for helper functions)
# ===========================================================================

class TestOnboard:
    """Cover _build_manifest, _create_db schema, _create_company_md,
    onboard with company, onboard invalid embedding fallback,
    onboard gemini warning."""

    def test_build_manifest_local_embedding(self):
        from gradata.onboard import _build_manifest
        m = _build_manifest(name="TestBrain", domain="Sales", embedding="local")
        assert m["schema_version"] == "1.0.0"
        assert m["metadata"]["brain_name"] == "TestBrain"
        assert m["metadata"]["domain"] == "Sales"
        assert m["rag"]["provider"] == "local"
        assert m["rag"]["dimensions"] == 384
        assert m["api_requirements"]["gemini"]["required"] is False

    def test_build_manifest_gemini_embedding(self):
        from gradata.onboard import _build_manifest
        m = _build_manifest(name="GeminiBrain", domain="Engineering", embedding="gemini")
        assert m["rag"]["provider"] == "gemini"
        assert m["rag"]["dimensions"] == 768
        assert m["api_requirements"]["gemini"]["required"] is True

    def test_build_manifest_bootstrap_steps(self):
        from gradata.onboard import _build_manifest
        m = _build_manifest("X", "General", "local")
        steps = [s["step"] for s in m["bootstrap"]]
        assert "set_env_vars" in steps
        assert "init_db" in steps
        assert "embed_brain" in steps

    def test_create_db_creates_tables(self, tmp_path):
        from gradata.onboard import _create_db
        db = tmp_path / "test.db"
        _create_db(db)
        conn = sqlite3.connect(str(db))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert "events" in tables
        assert "facts" in tables
        assert "lesson_applications" in tables
        assert "entities" in tables

    def test_create_company_md(self, tmp_path):
        from gradata.onboard import _create_company_md
        brain_dir = tmp_path / "brain"
        brain_dir.mkdir()
        _create_company_md(brain_dir, "Widgets Inc")
        company_file = brain_dir / "company.md"
        assert company_file.exists()
        content = company_file.read_text(encoding="utf-8")
        assert "Widgets Inc" in content
        assert "ICP" in content

    def test_onboard_creates_company_md(self, tmp_path):
        brain = _init_brain(tmp_path, name="CompanyBrain")
        # Re-init a second brain in a different dir WITH company
        brain_dir2 = tmp_path / "brain2"
        os.environ["BRAIN_DIR"] = str(brain_dir2)
        from gradata.onboard import onboard
        brain2 = onboard(brain_dir2, name="CompanyBrain2", domain="Sales",
                         company="Acme Corp", embedding="local", interactive=False)
        assert (brain2.dir / "company.md").exists()
        content = (brain2.dir / "company.md").read_text(encoding="utf-8")
        assert "Acme Corp" in content

    def test_onboard_invalid_embedding_falls_back(self, tmp_path):
        brain_dir = tmp_path / "fallback_brain"
        os.environ["BRAIN_DIR"] = str(brain_dir)
        from gradata.onboard import onboard
        # "openai" is not a valid embedding — should fall back to "local"
        brain = onboard(brain_dir, name="FallbackBrain", domain="General",
                        embedding="openai", interactive=False)
        manifest = json.loads((brain.dir / "brain.manifest.json").read_text())
        assert manifest["rag"]["provider"] == "local"

    def test_onboard_gemini_without_key_proceeds(self, tmp_path, capsys):
        brain_dir = tmp_path / "gemini_brain"
        # Remove the key if set
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ["BRAIN_DIR"] = str(brain_dir)
        from gradata.onboard import onboard
        # Should NOT raise — just print warning
        brain = onboard(brain_dir, name="GeminiBrain", domain="General",
                        embedding="gemini", interactive=False)
        assert brain.dir.exists()
        captured = capsys.readouterr()
        assert "GEMINI_API_KEY" in captured.out

    def test_onboard_creates_loop_state(self, tmp_path):
        brain = _init_brain(tmp_path)
        loop_state = brain.dir / "loop-state.md"
        assert loop_state.exists()
        content = loop_state.read_text(encoding="utf-8")
        assert "Session" in content or "Loop State" in content

    def test_onboard_creates_version_file(self, tmp_path):
        brain = _init_brain(tmp_path)
        version_file = brain.dir / "VERSION.md"
        assert version_file.exists()
        content = version_file.read_text(encoding="utf-8")
        assert "v0.1.0" in content

    def test_onboard_creates_embed_manifest(self, tmp_path):
        brain = _init_brain(tmp_path)
        embed_manifest = brain.dir / ".embed-manifest.json"
        assert embed_manifest.exists()
        data = json.loads(embed_manifest.read_text(encoding="utf-8"))
        assert data == {}

    def test_onboard_default_name_is_dirname(self, tmp_path):
        """When name is None in non-interactive mode, defaults to brain_dir.name."""
        brain_dir = tmp_path / "mybraindir"
        os.environ["BRAIN_DIR"] = str(brain_dir)
        from gradata.onboard import onboard
        brain = onboard(brain_dir, domain="Sales", embedding="local", interactive=False)
        manifest = json.loads((brain.dir / "brain.manifest.json").read_text())
        assert manifest["metadata"]["brain_name"] == "mybraindir"

    def test_onboard_default_domain_is_general(self, tmp_path):
        brain_dir = tmp_path / "domainbrain"
        os.environ["BRAIN_DIR"] = str(brain_dir)
        from gradata.onboard import onboard
        brain = onboard(brain_dir, name="X", embedding="local", interactive=False)
        manifest = json.loads((brain.dir / "brain.manifest.json").read_text())
        assert manifest["metadata"]["domain"] == "General"
