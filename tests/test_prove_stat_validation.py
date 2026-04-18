"""Statistical validation of brain.prove()'s trend test (issue #8).

Issue #8 asked for multi-user validation of a "paired t-test". Correction:
brain.prove() uses **Mann-Kendall** (_stats.trend_analysis), a non-parametric
rank-based test that is more robust than a paired t-test for this kind of
data (integer counts, non-normal, heteroskedastic, heavy-tied).

Rather than blocking on real multi-user data, this module validates the test
via Monte Carlo simulation on synthetic distributions. Ground truth is known
by construction (no-trend vs. real-trend), so we can measure:

- **Type I error rate** — rejection rate under H0 (no trend). Should ≈ α.
- **Power** — rejection rate under H1 (real trend). Should be high.
- **Robustness** — both properties hold across normal, heavy-tailed,
  skewed, and tie-heavy distributions.

Assertions use generous tolerances since this is probabilistic; seeds are
fixed for determinism.
"""
from __future__ import annotations

import random

import pytest

from gradata._stats import trend_analysis

ALPHA = 0.05
N_TRIALS = 400     # 95% CI for p=0.05 at n=400 ≈ [0.031, 0.077]
SERIES_LEN = 30    # realistic session count


def _rejection_rate(series_factory, n_trials: int = N_TRIALS) -> float:
    """Fraction of runs where Mann-Kendall rejects H0 at α=0.05."""
    reject = 0
    for i in range(n_trials):
        rng = random.Random(1000 + i)
        _, p = trend_analysis(series_factory(rng))
        if p < ALPHA:
            reject += 1
    return reject / n_trials


# ───────────────── Type I error (H0 true: no trend) ─────────────────


def test_type_i_normal_noise():
    """IID normal noise → rejection rate ≈ α."""
    rate = _rejection_rate(lambda rng: [rng.gauss(0, 1) for _ in range(SERIES_LEN)])
    assert 0.02 <= rate <= 0.09, f"Type I too far from α: {rate:.3f}"


def test_type_i_integer_counts():
    """Poisson-ish integer counts (realistic correction data) → ≈ α."""
    weights = [8, 6, 5, 4, 3, 2, 2, 1, 1, 1, 1]

    def gen(rng):
        return [rng.choices(range(11), weights=weights)[0] for _ in range(SERIES_LEN)]

    rate = _rejection_rate(gen)
    assert 0.02 <= rate <= 0.10, f"Type I integer counts: {rate:.3f}"


def test_type_i_heavy_tailed():
    """Laplace-ish noise still respects α — Mann-Kendall is nonparametric."""
    rate = _rejection_rate(
        lambda rng: [rng.expovariate(1) - rng.expovariate(1) for _ in range(SERIES_LEN)],
    )
    assert 0.02 <= rate <= 0.09, f"Type I heavy-tailed: {rate:.3f}"


def test_type_i_skewed():
    """Right-skewed (exponential) noise, no trend → ≈ α."""
    rate = _rejection_rate(
        lambda rng: [rng.expovariate(1) for _ in range(SERIES_LEN)],
    )
    assert 0.02 <= rate <= 0.09, f"Type I skewed: {rate:.3f}"


# ───────────────── Power (H1 true: genuine downtrend) ─────────────────


def test_power_downward_trend():
    """Real downtrend (−0.3/session + gaussian noise) → high detection."""
    rate = _rejection_rate(
        lambda rng: [max(0.0, 10 - 0.3 * i + rng.gauss(0, 1)) for i in range(SERIES_LEN)],
    )
    assert rate > 0.80, f"Power too low: {rate:.3f}"


def test_power_grows_with_n():
    """Power should not decrease as sample size grows (same effect size)."""
    def factory(n):
        return lambda rng: [max(0.0, 10 - 0.15 * i + rng.gauss(0, 1.5)) for i in range(n)]

    p_short = _rejection_rate(factory(10), n_trials=200)
    p_long = _rejection_rate(factory(30), n_trials=200)
    assert p_long >= p_short, f"Power shrank: n=10 {p_short:.2f} > n=30 {p_long:.2f}"


# ───────────────── Robustness & edge cases ─────────────────


@pytest.mark.parametrize("n", [0, 1])
def test_degenerate_lengths_safe(n):
    """n<2 returns the no-signal default — never crashes."""
    slope, p = trend_analysis([1.0] * n)
    assert p == 1.0
    assert slope == 0.0


def test_all_ties_returns_no_signal():
    """Constant series: tie adjustment drives p→1.0."""
    slope, p = trend_analysis([3.0] * 20)
    assert slope == 0.0
    assert p == pytest.approx(1.0)


def test_heavy_ties_does_not_false_positive():
    """Many-ties integer data (common in [0,3]) doesn't inflate Type I past tolerance."""
    rate = _rejection_rate(
        lambda rng: [float(rng.randint(0, 3)) for _ in range(SERIES_LEN)],
    )
    assert rate <= 0.12, f"Ties inflated Type I: {rate:.3f}"
