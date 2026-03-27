import pytest; pytest.importorskip('gradata.enhancements.self_improvement', reason='requires gradata_cloud')
"""
Wave 1 unit tests — Diff Engine, Edit Classifier, Scope Builder,
Metrics, Failure Detectors, Migrations.

Run: pytest sdk/tests/test_wave1.py -v
"""

import sqlite3
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 1. Diff Engine
# ---------------------------------------------------------------------------

class TestDiffEngine:
    def test_identical_texts(self):
        from gradata._diff_engine import compute_diff
        result = compute_diff("hello world", "hello world")
        assert result.severity == "as-is"
        assert result.edit_distance < 0.02

    def test_minor_edit(self):
        from gradata._diff_engine import compute_diff
        result = compute_diff("hello world", "hello World")
        assert result.severity in ("as-is", "minor")

    def test_major_edit(self):
        from gradata._diff_engine import compute_diff
        result = compute_diff("hello world", "goodbye cruel new world order")
        assert result.severity in ("moderate", "major", "discarded")
        assert result.edit_distance > 0.10

    def test_discarded(self):
        from gradata._diff_engine import compute_diff
        result = compute_diff("completely original text here", "nothing remotely similar")
        assert result.edit_distance > 0.30

    def test_summary_stats_keys(self):
        from gradata._diff_engine import compute_diff
        result = compute_diff("line one\nline two", "line one\nline three\nline four")
        assert "lines_added" in result.summary_stats
        assert "lines_removed" in result.summary_stats


# ---------------------------------------------------------------------------
# 2. Edit Classifier
# ---------------------------------------------------------------------------

class TestEditClassifier:
    def test_classify_returns_list(self):
        from gradata._diff_engine import compute_diff
        from gradata._edit_classifier import classify_edits
        diff = compute_diff("Please review the budget.", "Review the budget now.")
        classifications = classify_edits(diff)
        assert isinstance(classifications, list)

    def test_summarize_edits(self):
        from gradata._diff_engine import compute_diff
        from gradata._edit_classifier import classify_edits, summarize_edits
        diff = compute_diff("The price is $100.", "The price is $500.")
        classifications = classify_edits(diff)
        summary = summarize_edits(classifications)
        assert isinstance(summary, str)


# ---------------------------------------------------------------------------
# 3. Scope Builder
# ---------------------------------------------------------------------------

class TestScopeBuilder:
    def test_build_scope_sales_email(self):
        from gradata._scope import build_scope, RuleScope
        scope = build_scope({"task": "draft email to CEO", "domain": "sales"})
        assert scope.domain == "sales"
        assert scope.task_type == "email_draft"
        assert scope.audience == "c_suite"

    def test_scope_matches_wildcard(self):
        from gradata._scope import scope_matches, RuleScope
        universal = RuleScope()  # all defaults = wildcard
        specific = RuleScope(domain="sales", task_type="email_draft")
        assert scope_matches(universal, specific) == 1.0

    def test_scope_matches_exact(self):
        from gradata._scope import scope_matches, RuleScope
        rule = RuleScope(domain="sales")
        query = RuleScope(domain="sales", task_type="demo_prep")
        assert scope_matches(rule, query) == 1.0  # only domain is non-default

    def test_scope_matches_mismatch(self):
        from gradata._scope import scope_matches, RuleScope
        rule = RuleScope(domain="engineering")
        query = RuleScope(domain="sales")
        assert scope_matches(rule, query) == 0.0

    def test_scope_roundtrip(self):
        from gradata._scope import RuleScope, scope_to_dict, scope_from_dict
        original = RuleScope(domain="sales", task_type="email_draft", stakes="high")
        roundtripped = scope_from_dict(scope_to_dict(original))
        assert roundtripped == original


# ---------------------------------------------------------------------------
# 4. Metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    def test_compute_blandness_empty(self):
        from gradata._metrics import compute_blandness
        assert compute_blandness([]) == 0.0

    def test_compute_blandness_diverse(self):
        from gradata._metrics import compute_blandness
        score = compute_blandness(["the quick brown fox jumps over the lazy dog"])
        # 8 unique / 9 total = TTR ~0.89, blandness ~0.11
        assert score < 0.3

    def test_compute_blandness_repetitive(self):
        from gradata._metrics import compute_blandness
        score = compute_blandness(["the the the the the the the the"])
        # 1 unique / 8 total = TTR 0.125, blandness 0.875
        assert score > 0.7

    def test_metrics_window_defaults(self):
        from gradata._metrics import MetricsWindow
        m = MetricsWindow()
        assert m.sample_size == 0
        assert m.rewrite_rate == 0.0


# ---------------------------------------------------------------------------
# 5. Failure Detectors
# ---------------------------------------------------------------------------

class TestFailureDetectors:
    def test_no_alerts_without_baseline(self):
        from gradata._metrics import MetricsWindow
        from gradata._failure_detectors import detect_failures
        current = MetricsWindow(blandness_score=0.3)
        alerts = detect_failures(current, previous=None)
        # Only regression_to_mean can fire without baseline, and 0.3 is below threshold
        assert len(alerts) == 0

    def test_regression_to_mean_fires(self):
        from gradata._metrics import MetricsWindow
        from gradata._failure_detectors import detect_failures
        current = MetricsWindow(blandness_score=0.75)
        alerts = detect_failures(current)
        assert any(a.detector == "regression_to_mean" for a in alerts)

    def test_format_alerts(self):
        from gradata._failure_detectors import Alert, format_alerts
        alerts = [Alert(detector="test", severity="warning", message="Test alert")]
        output = format_alerts(alerts)
        assert "Test alert" in output


# ---------------------------------------------------------------------------
# 6. Migrations
# ---------------------------------------------------------------------------

class TestMigrations:
    def test_creates_events_table(self, tmp_path):
        """Migrations ensure events table exists with all columns."""
        from gradata._migrations import run_migrations
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        run_migrations(db_path)
        conn = sqlite3.connect(str(db_path))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        cols = {r[1] for r in conn.execute("PRAGMA table_info(events)").fetchall()}
        conn.close()
        assert "events" in tables
        assert "valid_from" in cols
        assert "valid_until" in cols
        assert "scope" in cols

    def test_idempotent(self, tmp_path):
        from gradata._migrations import run_migrations
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        # Run twice — should not error
        run_migrations(db_path)
        run_migrations(db_path)
