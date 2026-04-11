"""Tests for privacy model — Laplace DP noise, sanitization, k-anonymity."""

from __future__ import annotations

import statistics

import pytest

from gradata.security.privacy_model import (
    MIN_K_ANONYMITY,
    add_laplace_noise,
    check_k_anonymity,
    sanitize_for_sharing,
)


# ---------------------------------------------------------------------------
# Laplace noise
# ---------------------------------------------------------------------------
class TestLaplaceNoise:
    def test_noise_changes_value(self):
        """Noised value should differ from input (vanishingly unlikely to be exact)."""
        original = 100.0
        results = [add_laplace_noise(original) for _ in range(20)]
        # At least some should differ
        assert any(r != original for r in results)

    def test_noise_preserves_approximate_magnitude(self):
        """Over many runs, mean should be close to original (unbiased estimator)."""
        original = 50.0
        results = [add_laplace_noise(original, epsilon=1.0) for _ in range(2000)]
        mean = statistics.mean(results)
        assert abs(mean - original) < 5.0, f"Mean {mean} too far from {original}"

    def test_higher_epsilon_less_noise(self):
        """Higher epsilon -> smaller variance (less privacy, more utility)."""
        original = 100.0
        n = 2000
        low_eps = [add_laplace_noise(original, epsilon=0.1) for _ in range(n)]
        high_eps = [add_laplace_noise(original, epsilon=10.0) for _ in range(n)]
        var_low = statistics.variance(low_eps)
        var_high = statistics.variance(high_eps)
        assert var_low > var_high, (
            f"Low-epsilon variance ({var_low:.1f}) should exceed "
            f"high-epsilon variance ({var_high:.1f})"
        )

    def test_sensitivity_scales_noise(self):
        """Higher sensitivity -> more noise."""
        original = 100.0
        n = 2000
        low_sens = [add_laplace_noise(original, sensitivity=0.1) for _ in range(n)]
        high_sens = [add_laplace_noise(original, sensitivity=10.0) for _ in range(n)]
        var_low = statistics.variance(low_sens)
        var_high = statistics.variance(high_sens)
        assert var_high > var_low

    def test_zero_value(self):
        """Noise works on zero input."""
        result = add_laplace_noise(0.0)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------
class TestSanitize:
    @pytest.fixture()
    def sample_lesson(self) -> dict:
        return {
            "description": "Always use Oxford comma",
            "category": "style",
            "confidence": 0.85,
            "state": "RULE",
            "path": "style.punctuation",
            "fire_count": 42,
            "misfire_count": 3,
            "sessions_since_fire": 7,
            "example_draft": "I like cats dogs and birds",
            "example_corrected": "I like cats, dogs, and birds",
            "correction_event_ids": ["evt_001", "evt_002"],
            "memory_ids": ["mem_abc"],
            "agent_type": "sales",
        }

    def test_strips_pii_fields(self, sample_lesson: dict):
        result = sanitize_for_sharing(sample_lesson)
        for field in (
            "example_draft",
            "example_corrected",
            "correction_event_ids",
            "memory_ids",
            "agent_type",
        ):
            assert field not in result

    def test_keeps_functional_fields(self, sample_lesson: dict):
        result = sanitize_for_sharing(sample_lesson)
        for field in ("description", "category", "confidence", "state", "path"):
            assert field in result
            assert result[field] == sample_lesson[field]

    def test_noises_statistics(self, sample_lesson: dict):
        """At least one stat field should differ after sanitization."""
        results = [sanitize_for_sharing(sample_lesson) for _ in range(20)]
        stat_fields = ("fire_count", "misfire_count", "sessions_since_fire")
        changed = False
        for r in results:
            for f in stat_fields:
                if r[f] != sample_lesson[f]:
                    changed = True
                    break
        assert changed, "Statistics should be noised"

    def test_statistics_non_negative(self, sample_lesson: dict):
        """Noised values must be clamped to >= 0."""
        # Use a small original so noise could push negative
        lesson = {**sample_lesson, "fire_count": 1, "misfire_count": 0, "sessions_since_fire": 0}
        for _ in range(100):
            result = sanitize_for_sharing(lesson, epsilon=0.1)
            assert result["fire_count"] >= 0
            assert result["misfire_count"] >= 0
            assert result["sessions_since_fire"] >= 0

    def test_does_not_mutate_original(self, sample_lesson: dict):
        original_copy = dict(sample_lesson)
        sanitize_for_sharing(sample_lesson)
        assert sample_lesson == original_copy

    def test_missing_optional_fields_ok(self):
        """Sanitize handles lessons without optional fields gracefully."""
        minimal = {"description": "Test rule", "confidence": 0.5}
        result = sanitize_for_sharing(minimal)
        assert result["description"] == "Test rule"
        assert result["confidence"] == 0.5

    def test_epsilon_propagates_to_noise(self, sample_lesson: dict):
        """High epsilon should produce values closer to originals on average."""
        n = 500
        high_eps = [sanitize_for_sharing(sample_lesson, epsilon=100.0) for _ in range(n)]
        deviations = [abs(r["fire_count"] - sample_lesson["fire_count"]) for r in high_eps]
        mean_dev = statistics.mean(deviations)
        # With epsilon=100, noise scale is tiny; mean deviation should be < 2
        assert mean_dev < 2.0, f"Mean deviation {mean_dev} too high for epsilon=100"


# ---------------------------------------------------------------------------
# k-anonymity
# ---------------------------------------------------------------------------
class TestKAnonymity:
    def test_below_threshold_fails(self):
        assert check_k_anonymity(0) is False
        assert check_k_anonymity(3) is False
        assert check_k_anonymity(4) is False

    def test_at_threshold_passes(self):
        assert check_k_anonymity(5) is True

    def test_above_threshold_passes(self):
        assert check_k_anonymity(100) is True

    def test_threshold_value(self):
        assert MIN_K_ANONYMITY == 5
