"""Statistical validation of brain.prove()'s trend test (issue #8).

Issue #8 asked for multi-user validation of a claimed "paired t-test".
Correction: brain.prove() actually uses **Mann-Kendall**
(_stats.trend_analysis), a non-parametric rank-based test that is more
robust than a paired t-test for this kind of data (integer correction
counts, non-normal, heteroskedastic, heavy-tied).

Methodology: rather than block on access to multi-user real data, we
validate statistically via Monte Carlo simulation where ground truth is
known by construction (no-trend vs. real-trend). This is complementary
to -- and arguably stronger than -- an observational multi-user study,
because it measures the test's properties directly:

- **Type I error rate** -- rejection rate under H0 (no trend). Should be ~= alpha.
- **Power** -- rejection rate under H1 (real trend). Should be high.
- **Robustness** -- both properties hold across normal, heavy-tailed,
  skewed, and tie-heavy distributions.

An observational multi-user study remains valuable for external-validity
checks (does real correction data actually look like these synthetic
distributions?); that is left as follow-up work when such data exists.

Seeds are fixed for determinism; bounds are set well outside the 99% CI
for n=400 Monte Carlo trials at p=0.05 to avoid flake.
"""

from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from gradata._stats import trend_analysis

ALPHA = 0.05
N_TRIALS = 400  # bounds below are conservative (~99.9% CI) to avoid flake
SERIES_LEN = 30  # realistic session count
SHORT_N = 10  # power-growth comparison


def _rejection_rate(series_factory, n_trials: int = N_TRIALS) -> float:
    """Fraction of runs where Mann-Kendall rejects H0 at alpha=0.05."""
    reject = 0
    for i in range(n_trials):
        rng = random.Random(1000 + i)
        _, p = trend_analysis(series_factory(rng))
        if p < ALPHA:
            reject += 1
    return reject / n_trials


# ---------------- Type I error (H0 true: no trend) ----------------


def test_type_i_normal_noise():
    """IID normal noise -> rejection rate ~= alpha."""
    rate = _rejection_rate(lambda rng: [rng.gauss(0, 1) for _ in range(SERIES_LEN)])
    assert 0.02 <= rate <= 0.09, f"Type I too far from alpha: {rate:.3f}"


def test_type_i_integer_counts():
    """Poisson-ish integer counts (realistic correction data) -> ~= alpha."""
    weights = [8, 6, 5, 4, 3, 2, 2, 1, 1, 1, 1]

    def gen(rng: random.Random) -> list[int]:
        return [rng.choices(range(11), weights=weights)[0] for _ in range(SERIES_LEN)]

    rate = _rejection_rate(gen)
    assert 0.02 <= rate <= 0.10, f"Type I integer counts: {rate:.3f}"


def test_type_i_heavy_tailed():
    """Laplace(0, 1) noise (difference of i.i.d. Exp(1)) -- Mann-Kendall is nonparametric."""
    rate = _rejection_rate(
        lambda rng: [rng.expovariate(1) - rng.expovariate(1) for _ in range(SERIES_LEN)],
    )
    assert 0.02 <= rate <= 0.09, f"Type I heavy-tailed: {rate:.3f}"


def test_type_i_skewed():
    """Right-skewed (exponential) noise, no trend -> ~= alpha."""
    rate = _rejection_rate(
        lambda rng: [rng.expovariate(1) for _ in range(SERIES_LEN)],
    )
    assert 0.02 <= rate <= 0.09, f"Type I skewed: {rate:.3f}"


# ---------------- Power (H1 true: genuine downtrend) ----------------


def test_power_downward_trend():
    """Real downtrend (-0.3/session + gaussian noise) -> high detection."""
    rate = _rejection_rate(
        lambda rng: [max(0.0, 10 - 0.3 * i + rng.gauss(0, 1)) for i in range(SERIES_LEN)],
    )
    assert rate > 0.80, f"Power too low: {rate:.3f}"


def test_power_grows_with_n():
    """Power should grow (not merely not-shrink) as sample size grows at fixed effect.

    Weak effect (slope=-0.15, sigma=1.5); expect a meaningful gap between n=10 and n=30.
    Bound of +0.10 is well above one standard error (~0.035 at 400 trials) so a
    seed-dependent single-trial flip cannot fail this.
    """

    def factory(n: int) -> Callable[[random.Random], list[float]]:
        return lambda rng: [max(0.0, 10 - 0.15 * i + rng.gauss(0, 1.5)) for i in range(n)]

    p_short = _rejection_rate(factory(SHORT_N))
    p_long = _rejection_rate(factory(SERIES_LEN))
    assert p_long >= p_short + 0.10, (
        f"Power should grow substantially with n: "
        f"n={SHORT_N} {p_short:.3f}, n={SERIES_LEN} {p_long:.3f}"
    )


# ---------------- Robustness & edge cases ----------------


@pytest.mark.parametrize("n", [0, 1])
def test_degenerate_lengths_safe(n):
    """n<2 returns the no-signal default -- never crashes."""
    slope, p = trend_analysis([1.0] * n)
    assert p == pytest.approx(1.0)
    assert slope == pytest.approx(0.0)


def test_all_ties_returns_no_signal():
    """Constant series: tie adjustment drives p -> 1.0."""
    slope, p = trend_analysis([3.0] * 20)
    assert slope == pytest.approx(0.0)
    assert p == pytest.approx(1.0)


def test_heavy_ties_does_not_false_positive():
    """Many-ties integer data (common in [0,3]) still respects alpha.

    Tight bound matching the other Type I tests: tie-correction in
    trend_analysis must actually work, not just approximately work.
    """
    rate = _rejection_rate(
        lambda rng: [float(rng.randint(0, 3)) for _ in range(SERIES_LEN)],
    )
    assert 0.02 <= rate <= 0.10, f"Ties broke Type I control: {rate:.3f}"


def test_fifty_element_cap_is_applied():
    """trend_analysis caps input at LAST 50 elements.

    Use a prefix with a strong DOWN-trend that differs from the tail's
    up-trend. If the cap were broken (kept first-50 or middle), the
    prefix+tail result would not match the tail-only result.
    """
    tail = [float(i) for i in range(50)]  # up-trend 0..49
    heavy_down_prefix = [float(100 - i) for i in range(50)]  # down-trend 100..51
    slope_tail, p_tail = trend_analysis(tail)
    slope_combined, p_combined = trend_analysis(heavy_down_prefix + tail)
    assert slope_tail == pytest.approx(slope_combined)
    assert p_tail == pytest.approx(p_combined)


def test_brain_prove_interprets_trend_results_correctly(tmp_path):
    """End-to-end: brain_prove must read p_value (not slope) for the 'strong'
    gate and handle the 'converging' trend string. Regression guard for the
    consumer of trend_analysis. brain_efficiency is patched so the test is
    decoupled from its implementation details."""
    from unittest.mock import patch

    from gradata.brain import Brain

    brain = Brain(str(tmp_path))
    # p_value = 0.02 (< 0.05 strong threshold) + converging + effort_ratio < 0.7
    cps = [10, 10, 10, 8, 6, 5, 4, 3, 2, 2]
    conv = {
        "sessions": list(range(1, 11)),
        "corrections_per_session": cps,
        "trend": "converging",
        "p_value": 0.02,
        "changepoints": [],
        "by_category": {},
        "total_corrections": sum(cps),
        "total_sessions": 10,
        "edit_distance_per_session": [],
        "edit_distance_trend": "insufficient_data",
    }
    efficiency = {
        "effort_ratio": 0.3,
        "corrections_initial": 10.0,
        "corrections_recent": 2.3,
        "total_corrections": sum(cps),
        "total_sessions": 10,
    }
    with (
        patch.object(brain, "_get_convergence", return_value=conv),
        patch("gradata._core.brain_efficiency", return_value=efficiency),
    ):
        result = brain.prove()
    assert result["proven"] is True
    assert result["confidence_level"] == "strong"
    assert result["evidence"]["p_value"] == pytest.approx(0.02)
