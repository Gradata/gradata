import pytest
"""
SPEC.md Gold Standard Compliance Tests
=======================================
Every testable claim in SPEC.md has a corresponding test here.
Run: pytest tests/test_spec_compliance.py -v

If a test fails, the build does NOT match the canonical spec.
Fix the build or update the spec — never let them diverge silently.
"""

import importlib
import sqlite3
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Section 2: Architecture — 3 layers exist
# ---------------------------------------------------------------------------


class TestArchitectureLayers:
    """SPEC Section 2: patterns/ and enhancements/ packages exist."""

    def test_patterns_package_importable(self):
        importlib.import_module("gradata.patterns")

    def test_enhancements_package_importable(self):
        importlib.import_module("gradata.enhancements")

    @pytest.mark.parametrize(
        "module",
        [
            "orchestrator",
            "pipeline",
            "parallel",
            "human_loop",
            "sub_agents",
            "reflection",
            "evaluator",
            "memory",
            "guardrails",
            "rag",
            "tools",
            "mcp",
        ],
    )
    def test_all_15_base_patterns_importable(self, module):
        """SPEC Section 2: 15 base patterns (contrib.patterns + rules)."""
        importlib.import_module(f"gradata.contrib.patterns.{module}")

    @pytest.mark.parametrize(
        "module",
        [
            "scope",
            "rule_engine",
            "rule_tracker",
        ],
    )
    def test_rule_modules_importable(self, module):
        """SPEC Section 2: rule modules moved to gradata.rules."""
        importlib.import_module(f"gradata.rules.{module}")

    @pytest.mark.parametrize(
        "module",
        [
            "self_improvement",
            "diff_engine",
            "edit_classifier",
            "pattern_extractor",
            "metrics",
            "quality_monitoring",
            "reporting",
            "carl",
            "learning_pipeline",
        ],
    )
    def test_all_enhancements_importable(self, module):
        """SPEC Section 2: core enhancements."""
        importlib.import_module(f"gradata.enhancements.{module}")

    @pytest.mark.parametrize(
        "module",
        [
            "quality_gates",
            "truth_protocol",
            "eval_benchmark",
            "install_manifest",
        ],
    )
    def test_contrib_enhancements_importable(self, module):
        """SPEC Section 2: contrib enhancements (moved from core)."""
        importlib.import_module(f"gradata.contrib.enhancements.{module}")


# ---------------------------------------------------------------------------
# Section 3: Core Loop — all functions exist
# ---------------------------------------------------------------------------


class TestCoreLoop:
    """SPEC Section 3: User→Draft→Edit→Diff→Classify→Extract→Graduate→Apply→Metrics."""

    def test_brain_correct_exists(self):
        from gradata.brain import Brain

        assert hasattr(Brain, "correct")

    def test_brain_log_output_exists(self):
        from gradata.brain import Brain

        assert hasattr(Brain, "log_output")

    def test_brain_apply_brain_rules_exists(self):
        from gradata.brain import Brain

        assert hasattr(Brain, "apply_brain_rules")

    def test_compute_diff_exists(self):
        from gradata.enhancements.diff_engine import compute_diff

        assert callable(compute_diff)

    def test_classify_edits_exists(self):
        from gradata.enhancements.edit_classifier import classify_edits

        assert callable(classify_edits)

    def test_extract_patterns_exists(self):
        from gradata.enhancements.pattern_extractor import extract_patterns

        assert callable(extract_patterns)

    def test_apply_rules_exists(self):
        from gradata.rules.rule_engine import apply_rules

        assert callable(apply_rules)

    def test_compute_metrics_exists(self):
        from gradata.enhancements.metrics import compute_metrics

        assert callable(compute_metrics)


# ---------------------------------------------------------------------------
# Section 4: Data Model — event-sourced
# ---------------------------------------------------------------------------


class TestDataModel:
    """SPEC Section 4: Event-sourced, no domain tables."""

    def test_migrations_create_events_table(self, tmp_path):
        from gradata._migrations import run_migrations

        db = tmp_path / "test.db"
        sqlite3.connect(str(db)).close()
        run_migrations(db)
        conn = sqlite3.connect(str(db))
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()
        assert "events" in tables
        # SPEC says NO domain tables
        assert "outputs" not in tables
        assert "corrections" not in tables
        assert "rule_applications" not in tables

    def test_output_classification_5_levels(self):
        """SPEC Section 4: as-is, minor, moderate, major, discarded."""
        from gradata.enhancements.diff_engine import compute_diff

        # Identical = as-is
        assert compute_diff("hello", "hello").severity == "as-is"
        # Very different = major or discarded
        r = compute_diff(
            "completely original text here with many words",
            "nothing remotely similar to the above at all",
        )
        assert r.severity in ("major", "discarded")


# ---------------------------------------------------------------------------
# Section 5: Metrics + Success Conditions
# ---------------------------------------------------------------------------


class TestMetricsAndSuccess:
    """SPEC Section 5: 6 success conditions + 4 failure detectors."""

    def test_success_conditions_evaluator_exists(self):
        from gradata.contrib.enhancements.quality_gates import evaluate_success_conditions

        assert callable(evaluate_success_conditions)

    def test_4_failure_detectors_exist(self):
        from gradata.enhancements.scoring import failure_detectors as fd

        assert hasattr(fd, "detect_being_ignored")
        assert hasattr(fd, "detect_playing_safe")
        assert hasattr(fd, "detect_overfitting")
        assert hasattr(fd, "detect_regression_to_mean")

    def test_blandness_computation(self):
        from gradata.enhancements.metrics import compute_blandness

        # Empty = not bland
        assert compute_blandness([]) == 0.0
        # Repetitive = bland
        assert compute_blandness(["the the the the the"]) > 0.5


# ---------------------------------------------------------------------------
# Section 6: Guardrails
# ---------------------------------------------------------------------------


class TestGuardrails:
    """SPEC Section 6: 6 guardrails from Build Directive."""

    def test_behavioral_engine_directives_exist(self):
        from gradata.enhancements.behavioral_engine import DirectiveRegistry

        reg = DirectiveRegistry()
        assert reg.stats()["total_contracts"] == 0

    def test_quality_gate_8_0_threshold(self):
        from gradata.contrib.enhancements.quality_gates import QualityGate, GENERAL_RUBRICS

        gate = QualityGate(GENERAL_RUBRICS, threshold=8.0)
        assert gate is not None

    def test_truth_protocol_banned_phrases(self):
        from gradata.contrib.enhancements.truth_protocol import BANNED_PHRASES

        assert len(BANNED_PHRASES) > 20

    def test_truth_protocol_verify_claims(self):
        from gradata.contrib.enhancements.truth_protocol import verify_claims

        result = verify_claims("I've successfully completed all tasks perfectly!")
        assert not result.all_passed


# ---------------------------------------------------------------------------
# Section 7: Domain Agnostic
# ---------------------------------------------------------------------------


class TestDomainAgnostic:
    """SPEC Section 7: configurable task types, multi-domain."""

    def test_audience_tier_enum_has_non_sales_tiers(self):
        from gradata.rules.scope import AudienceTier

        assert hasattr(AudienceTier, "CANDIDATE")
        assert hasattr(AudienceTier, "INTERVIEWER")
        assert hasattr(AudienceTier, "PEER")

    def test_register_custom_task_type(self):
        from gradata.rules.scope import register_task_type, classify_scope

        register_task_type("legal_review", ["review contract", "compliance check"], "legal")
        task, _ = classify_scope("review contract for compliance")
        assert task == "legal_review"

    def test_behavioral_engine_multi_domain(self):
        from gradata.enhancements.behavioral_engine import Directive, DirectiveRegistry

        reg = DirectiveRegistry()
        reg.register(
            Directive(
                name="sales-email",
                domain="sales",
                trigger_keywords=["email"],
                constraints=["Under 100 words"],
            )
        )
        reg.register(
            Directive(
                name="eng-review",
                domain="engineering",
                trigger_keywords=["review"],
                constraints=["Check security"],
            )
        )
        assert reg.stats()["total_contracts"] == 2
        assert "sales" in reg.domains
        assert "engineering" in reg.domains


# ---------------------------------------------------------------------------
# Section 8: Zero Dependencies
# ---------------------------------------------------------------------------


class TestZeroDeps:
    """SPEC Section 8: pip install gradata works with no external deps."""

    def test_core_import_no_chromadb(self):
        """Brain class imports without chromadb (removed S66)."""
        from gradata.brain import Brain

        assert Brain is not None

    def test_patterns_import_no_deps(self):
        """All patterns are pure stdlib."""
        from gradata.patterns import pipeline, reflection, guardrails

        assert pipeline is not None


# ---------------------------------------------------------------------------
# Section 10: Brain Class API
# ---------------------------------------------------------------------------


class TestBrainAPI:
    """SPEC Section 11: Brain class methods wired to patterns/enhancements."""

    def test_brain_health(self):
        from gradata.brain import Brain

        assert hasattr(Brain, "health")

    def test_brain_register_tool(self):
        from gradata.brain import Brain

        assert hasattr(Brain, "register_tool")


# ---------------------------------------------------------------------------
# Section 13: Research-Backed Constants
# ---------------------------------------------------------------------------


class TestResearchBackedConstants:
    """SPEC Section 13: every constant has published justification."""

    def test_loss_aversion_ratio_calibrated(self):
        """Calibrated from 2992 events: 1:1 ratio (sweep_penalty_ratio.py)."""
        from gradata.enhancements.self_improvement import CONTRADICTION_PENALTY, ACCEPTANCE_BONUS

        ratio = abs(CONTRADICTION_PENALTY) / ACCEPTANCE_BONUS
        assert 0.8 <= ratio <= 1.5, f"Loss aversion ratio {ratio} outside [0.8, 1.5]"

    def test_pattern_threshold_bayesian(self):
        """Bayesian posterior > 0.6."""
        from gradata.enhancements.self_improvement import PATTERN_THRESHOLD

        assert PATTERN_THRESHOLD == 0.60

    def test_rule_threshold_bayesian(self):
        """Bayesian posterior >= 0.80 (cold-start optimized from 0.90)."""
        from gradata.enhancements.self_improvement import RULE_THRESHOLD

        assert 0.80 <= RULE_THRESHOLD <= 0.95

    def test_min_applications_few_shot(self):
        """3-5 shot learning standard."""
        from gradata.enhancements.self_improvement import (
            MIN_APPLICATIONS_FOR_PATTERN,
            MIN_APPLICATIONS_FOR_RULE,
        )

        assert 2 <= MIN_APPLICATIONS_FOR_PATTERN <= 5
        assert 3 <= MIN_APPLICATIONS_FOR_RULE <= 8

    def test_graduation_constants_frozen(self):
        """Canonical spec values — catches accidental tuning drift.

        Ranges above allow policy changes; these assertions pin the CURRENT
        shipped values. If you deliberately retune, update these with a
        CHANGELOG entry noting the behavioral impact.
        """
        from gradata.enhancements.self_improvement import (
            MIN_APPLICATIONS_FOR_PATTERN,
            MIN_APPLICATIONS_FOR_RULE,
            PATTERN_THRESHOLD,
            RULE_THRESHOLD,
        )

        assert PATTERN_THRESHOLD == 0.60
        assert RULE_THRESHOLD == 0.90
        assert MIN_APPLICATIONS_FOR_PATTERN == 3
        assert MIN_APPLICATIONS_FOR_RULE == 5
