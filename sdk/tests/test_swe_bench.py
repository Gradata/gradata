"""
Tests for SWE-bench harness (no Docker, no HuggingFace download required).
===========================================================================
Uses mock instances to verify the full flow:
  agent attempts fix → compare to gold → brain.correct() on failure → lessons accumulate
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from gradata.benchmarks.swe_bench import (
    PatchResult,
    RunConfig,
    RunResults,
    SWEBenchHarness,
    SWEInstance,
    compare_patches,
)


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

def _mock_instances(n: int = 10) -> list[SWEInstance]:
    """Generate mock SWE-bench instances for testing."""
    instances = []
    for i in range(n):
        instances.append(SWEInstance(
            instance_id=f"test__repo-{i}",
            repo="test/repo",
            problem_statement=f"Bug #{i}: function returns wrong value",
            gold_patch=f"--- a/src/foo.py\n+++ b/src/foo.py\n@@ -1 +1 @@\n-return {i}\n+return {i + 1}",
            fail_to_pass=[f"test_bug_{i}"],
        ))
    return instances


def _perfect_agent(instance: SWEInstance, brain_rules: str) -> str:
    """Agent that always returns the gold patch (100% resolve rate)."""
    return instance.gold_patch


def _bad_agent(instance: SWEInstance, brain_rules: str) -> str:
    """Agent that always returns wrong patch (0% resolve rate)."""
    return "--- a/wrong.py\n+++ b/wrong.py\n@@ -1 +1 @@\n-wrong\n+still wrong"


def _improving_agent_factory(improve_after: int = 5):
    """Agent that starts bad but gets better (simulates learning)."""
    call_count = [0]

    def agent(instance: SWEInstance, brain_rules: str) -> str:
        call_count[0] += 1
        if call_count[0] > improve_after and brain_rules:
            return instance.gold_patch  # "Learned" from brain rules
        return "--- a/bad.py\n+++ b/bad.py\n@@ -1 +1 @@\n-bad\n+still bad"

    return agent


# ---------------------------------------------------------------------------
# Patch comparison tests
# ---------------------------------------------------------------------------


class TestPatchComparison:
    def test_identical_patches(self):
        patch = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new"
        assert compare_patches(patch, patch) == 1.0

    def test_completely_different(self):
        a = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-alpha\n+beta"
        b = "--- a/g.py\n+++ b/g.py\n@@ -1 +1 @@\n-gamma\n+delta"
        assert compare_patches(a, b) == 0.0

    def test_partial_overlap(self):
        a = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new\n+extra"
        b = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new"
        sim = compare_patches(a, b)
        assert 0.0 < sim < 1.0

    def test_empty_patches(self):
        assert compare_patches("", "") == 1.0
        assert compare_patches("some patch", "") == 0.0
        assert compare_patches("", "some patch") == 0.0

    def test_whitespace_normalized(self):
        a = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n+return   x  +  1"
        b = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n+return x + 1"
        assert compare_patches(a, b) == 1.0


# ---------------------------------------------------------------------------
# Harness tests (no external deps)
# ---------------------------------------------------------------------------


class TestSWEBenchHarness:
    def test_perfect_agent_100_percent(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            harness = SWEBenchHarness(brain_dir=tmpdir)
            instances = _mock_instances(5)
            config = RunConfig(run_id="perfect", batch_size=5, use_brain=False)
            results = harness.run(instances, _perfect_agent, config)
            assert results.resolve_rate == 1.0
            assert results.total_resolved == 5

    def test_bad_agent_0_percent(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            harness = SWEBenchHarness(brain_dir=tmpdir)
            instances = _mock_instances(5)
            config = RunConfig(run_id="bad", batch_size=5, use_brain=True)
            results = harness.run(instances, _bad_agent, config)
            assert results.resolve_rate == 0.0
            assert results.total_resolved == 0

    def test_corrections_captured_on_failure(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            harness = SWEBenchHarness(brain_dir=tmpdir)
            instances = _mock_instances(3)
            config = RunConfig(run_id="capture", batch_size=3, use_brain=True)
            results = harness.run(instances, _bad_agent, config)
            captured = sum(1 for r in results.results if r.correction_captured)
            assert captured == 3  # All failures captured

    def test_lessons_created_from_corrections(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            harness = SWEBenchHarness(brain_dir=tmpdir)
            instances = _mock_instances(5)
            config = RunConfig(run_id="lessons", batch_size=5, use_brain=True)
            results = harness.run(instances, _bad_agent, config)
            # At least some lessons should be created
            assert results.brain_lessons_created > 0

    def test_batch_stats_computed(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            harness = SWEBenchHarness(brain_dir=tmpdir)
            instances = _mock_instances(10)
            config = RunConfig(run_id="batches", batch_size=5, use_brain=False)
            results = harness.run(instances, _bad_agent, config)
            assert len(results.batch_stats) == 2  # 10 instances / 5 per batch

    def test_summary_output(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            harness = SWEBenchHarness(brain_dir=tmpdir)
            instances = _mock_instances(3)
            config = RunConfig(run_id="summary", batch_size=3, use_brain=False)
            results = harness.run(instances, _perfect_agent, config)
            summary = results.summary()
            assert "summary" in summary.lower() or "SWE-bench" in summary

    def test_to_dict_serializable(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            harness = SWEBenchHarness(brain_dir=tmpdir)
            instances = _mock_instances(3)
            results = harness.run(instances, _perfect_agent, RunConfig(batch_size=3))
            d = results.to_dict()
            assert "resolve_rate" in d
            assert "batch_stats" in d
            # Should be JSON-serializable
            import json
            json.dumps(d)

    def test_compare_runs(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            harness = SWEBenchHarness(brain_dir=tmpdir)
            instances = _mock_instances(5)

            baseline = harness.run(
                instances, _bad_agent,
                RunConfig(run_id="baseline", batch_size=5, use_brain=False),
            )
            enhanced = harness.run(
                instances, _perfect_agent,
                RunConfig(run_id="enhanced", batch_size=5, use_brain=True),
            )

            comparison = harness.compare_runs(baseline, enhanced)
            assert comparison["enhanced_resolve_rate"] > comparison["baseline_resolve_rate"]
            assert "verdict" in comparison
            assert "improved" in comparison["verdict"].lower()

    def test_max_instances_cap(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            harness = SWEBenchHarness(brain_dir=tmpdir)
            instances = _mock_instances(20)
            config = RunConfig(max_instances=5, batch_size=5, use_brain=False)
            results = harness.run(instances, _perfect_agent, config)
            assert results.total_attempted == 5

    def test_agent_crash_handled(self):
        def crashing_agent(instance, rules):
            raise RuntimeError("Agent exploded")

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            harness = SWEBenchHarness(brain_dir=tmpdir)
            instances = _mock_instances(2)
            config = RunConfig(batch_size=2, use_brain=False)
            results = harness.run(instances, crashing_agent, config)
            assert results.total_attempted == 2
            assert results.total_resolved == 0

    def test_no_brain_dir_works(self):
        harness = SWEBenchHarness()  # No brain
        instances = _mock_instances(3)
        config = RunConfig(batch_size=3, use_brain=False)
        results = harness.run(instances, _perfect_agent, config)
        assert results.total_resolved == 3


class TestSWEInstance:
    def test_instance_fields(self):
        inst = SWEInstance(
            instance_id="django__django-123",
            repo="django/django",
            problem_statement="Bug in ORM",
        )
        assert inst.repo == "django/django"
        assert inst.fail_to_pass == []
