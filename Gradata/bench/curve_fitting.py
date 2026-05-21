"""GRA-1300: Convergence curve math — model comparison bench.

Fits four candidate curves against (session_n, corrections_per_session) data:

  1. Exponential decay   y = a * exp(-k * n)
  2. Power law           y = a * (n+1)^(-k)
  3. Smoothed MA         rolling mean, window=5 (visual smoother, no params)
  4. Cumul. plateau      y_cumul = C_inf * n / (n + n_half)   (Michaelis-Menten)

For each model:
  - Fit parameters (MLE / OLS)
  - R² on original scale
  - AIC  (n * ln(RSS/n) + 2k)
  - Chart saved to bench/results/curve_fitting_charts/

Usage
-----
    python -m bench.curve_fitting                 # synthetic profiles only
    python -m bench.curve_fitting --brain-path ~/.gradata  # real brain
    python -m bench.curve_fitting --quick          # skip chart generation

Output
------
  bench/results/curve_fitting_<timestamp>.json
  bench/results/curve_fitting_charts/<profile>_<model>.png
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FitResult:
    model: str
    params: dict[str, float]
    r2: float
    aic: float
    rss: float


@dataclass
class ProfileResult:
    name: str
    description: str
    n_sessions: int
    sessions: list[int]
    corrections: list[float]
    cumulative: list[float]
    fits: list[FitResult]
    recommendation: str = ""
    chart_path: str = ""


# ---------------------------------------------------------------------------
# Synthetic brain profiles
# ---------------------------------------------------------------------------


def _rng_seed(seed: int) -> random.Random:
    return random.Random(seed)


def generate_exponential_profile(seed: int = 1) -> tuple[list[int], list[float]]:
    """Clean exponential decay: a=6, k=0.045, Gaussian noise σ=0.5."""
    rng = _rng_seed(seed)
    sessions = list(range(1, 81))
    corrections = [max(0.1, 6.0 * math.exp(-0.045 * n) + rng.gauss(0, 0.5)) for n in sessions]
    return sessions, corrections


def generate_power_law_profile(seed: int = 2) -> tuple[list[int], list[float]]:
    """Power-law decay: a=7, k=0.55, Gaussian noise σ=0.4."""
    rng = _rng_seed(seed)
    sessions = list(range(1, 81))
    corrections = [max(0.1, 7.0 * (n**-0.55) + rng.gauss(0, 0.4)) for n in sessions]
    return sessions, corrections


def generate_plateau_profile(seed: int = 3) -> tuple[list[int], list[float]]:
    """Fast early decay then flat: decays to ~1 by session 20, stable after."""
    rng = _rng_seed(seed)
    sessions = list(range(1, 81))
    corrections = []
    for n in sessions:
        if n <= 20:
            base = 5.0 * math.exp(-0.15 * n) + 1.0
        else:
            base = 1.0 + rng.gauss(0, 0.3)
        corrections.append(max(0.1, base + rng.gauss(0, 0.4)))
    return sessions, corrections


def generate_noisy_real_profile(seed: int = 4) -> tuple[list[int], list[float]]:
    """Realistic jagged brain: partial convergence with spikes."""
    rng = _rng_seed(seed)
    sessions = list(range(1, 101))
    corrections = []
    for n in sessions:
        # Trend: slow exponential with occasional spikes (new domain, regression)
        trend = 5.0 * math.exp(-0.025 * n) + 1.5
        spike = rng.gauss(0, 1.2)
        if rng.random() < 0.08:  # 8% spike probability
            spike += rng.uniform(2, 5)
        corrections.append(max(0.1, trend + spike))
    return sessions, corrections


# ---------------------------------------------------------------------------
# Model fitting helpers
# ---------------------------------------------------------------------------


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot == 0:
        return 1.0
    return 1.0 - ss_res / ss_tot


def _aic(y_true: np.ndarray, y_pred: np.ndarray, k: int) -> float:
    """AIC = n * ln(RSS/n) + 2k (Gaussian MLE form)."""
    n = len(y_true)
    rss = float(np.sum((y_true - y_pred) ** 2))
    if rss <= 0:
        rss = 1e-12
    return n * math.log(rss / n) + 2 * k


def fit_exponential(sessions: np.ndarray, corrections: np.ndarray) -> FitResult:
    """Fit y = a * exp(-k * n) via log-linear OLS (log(y) = log(a) - k*n)."""
    # Only fit on positive values
    mask = corrections > 0
    if mask.sum() < 3:
        return FitResult("exponential", {"a": float("nan"), "k": float("nan")}, -99.0, float("inf"), float("inf"))

    log_y = np.log(corrections[mask])
    n_fit = sessions[mask].astype(float)

    # OLS: log_y = beta0 + beta1 * n
    A = np.column_stack([np.ones_like(n_fit), n_fit])
    try:
        coeffs, _, _, _ = np.linalg.lstsq(A, log_y, rcond=None)
    except np.linalg.LinAlgError:
        return FitResult("exponential", {"a": float("nan"), "k": float("nan")}, -99.0, float("inf"), float("inf"))

    beta0, beta1 = coeffs
    a = math.exp(beta0)
    k = -beta1  # k > 0 means decay

    y_pred = a * np.exp(-k * sessions)
    r2 = _r2(corrections, y_pred)
    aic = _aic(corrections, y_pred, k=2)
    rss = float(np.sum((corrections - y_pred) ** 2))
    return FitResult("exponential", {"a": round(a, 4), "k": round(k, 4)}, round(r2, 4), round(aic, 2), round(rss, 4))


def fit_power_law(sessions: np.ndarray, corrections: np.ndarray) -> FitResult:
    """Fit y = a * (n+1)^(-k) via log-log OLS (log(y) = log(a) - k*log(n+1))."""
    mask = corrections > 0
    if mask.sum() < 3:
        return FitResult("power_law", {"a": float("nan"), "k": float("nan")}, -99.0, float("inf"), float("inf"))

    log_y = np.log(corrections[mask])
    log_n = np.log(sessions[mask] + 1.0)  # n+1 to handle session=0 edge

    A = np.column_stack([np.ones_like(log_n), log_n])
    try:
        coeffs, _, _, _ = np.linalg.lstsq(A, log_y, rcond=None)
    except np.linalg.LinAlgError:
        return FitResult("power_law", {"a": float("nan"), "k": float("nan")}, -99.0, float("inf"), float("inf"))

    beta0, beta1 = coeffs
    a = math.exp(beta0)
    k = -beta1  # k > 0 means decay

    y_pred = a * ((sessions + 1) ** (-k))
    r2 = _r2(corrections, y_pred)
    aic = _aic(corrections, y_pred, k=2)
    rss = float(np.sum((corrections - y_pred) ** 2))
    return FitResult("power_law", {"a": round(a, 4), "k": round(k, 4)}, round(r2, 4), round(aic, 2), round(rss, 4))


def fit_smoothed_ma(sessions: np.ndarray, corrections: np.ndarray, window: int = 5) -> FitResult:
    """Rolling mean (window=5). Treat boundary via 'shrinking' window."""
    n = len(corrections)
    y_pred = np.zeros(n)
    for i in range(n):
        lo = max(0, i - window // 2)
        hi = min(n, i + window // 2 + 1)
        y_pred[i] = np.mean(corrections[lo:hi])

    r2 = _r2(corrections, y_pred)
    # MA has no free parameters in the traditional sense; treat as k=1 (the window width)
    aic = _aic(corrections, y_pred, k=1)
    rss = float(np.sum((corrections - y_pred) ** 2))
    return FitResult(
        "smoothed_ma",
        {"window": window},
        round(r2, 4),
        round(aic, 2),
        round(rss, 4),
    )


def fit_cumulative_plateau(sessions: np.ndarray, corrections: np.ndarray) -> FitResult:
    """Fit cumulative curve C(n) = C_inf * n / (n + n_half) via OLS linearisation.

    Linearise: n / C(n) = n_half/C_inf + (1/C_inf)*n
    i.e. z = alpha + beta * n  where z = n / C(n)
    alpha = n_half / C_inf,  beta = 1 / C_inf
    """
    cumul = np.cumsum(corrections)
    n_arr = sessions.astype(float)

    # z = n / C(n), but avoid divide-by-zero for first session
    z = n_arr / cumul
    mask = np.isfinite(z) & (cumul > 0)
    if mask.sum() < 3:
        return FitResult("cumul_plateau", {"C_inf": float("nan"), "n_half": float("nan")}, -99.0, float("inf"), float("inf"))

    A = np.column_stack([np.ones(mask.sum()), n_arr[mask]])
    try:
        coeffs, _, _, _ = np.linalg.lstsq(A, z[mask], rcond=None)
    except np.linalg.LinAlgError:
        return FitResult("cumul_plateau", {"C_inf": float("nan"), "n_half": float("nan")}, -99.0, float("inf"), float("inf"))

    alpha, beta = coeffs
    if abs(beta) < 1e-10:
        return FitResult("cumul_plateau", {"C_inf": float("nan"), "n_half": float("nan")}, -99.0, float("inf"), float("inf"))

    c_inf = 1.0 / beta
    n_half = alpha * c_inf

    cumul_pred = c_inf * n_arr / (n_arr + n_half)
    r2 = _r2(cumul, cumul_pred)
    aic = _aic(cumul, cumul_pred, k=2)
    rss = float(np.sum((cumul - cumul_pred) ** 2))
    return FitResult(
        "cumul_plateau",
        {"C_inf": round(c_inf, 2), "n_half": round(n_half, 2)},
        round(r2, 4),
        round(aic, 2),
        round(rss, 4),
    )


# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------


def make_charts(profile: ProfileResult, out_dir: Path) -> dict[str, str]:
    """Generate one multi-panel chart for this profile. Returns {model: path}."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return {}

    out_dir.mkdir(parents=True, exist_ok=True)
    sessions = np.array(profile.sessions, dtype=float)
    corrections = np.array(profile.corrections, dtype=float)
    cumul = np.array(profile.cumulative, dtype=float)

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    fig.suptitle(
        f"Convergence Curve Models — {profile.name}\n{profile.description}",
        fontsize=11,
        fontweight="bold",
    )

    model_map = {f.model: f for f in profile.fits}
    plot_configs = [
        ("exponential", axes[0, 0]),
        ("power_law", axes[0, 1]),
        ("smoothed_ma", axes[1, 0]),
        ("cumul_plateau", axes[1, 1]),
    ]

    colors = {"exponential": "#e74c3c", "power_law": "#2980b9", "smoothed_ma": "#27ae60", "cumul_plateau": "#8e44ad"}
    labels = {
        "exponential": "Exponential decay  y = a·e^(−kn)",
        "power_law": "Power law  y = a·(n+1)^(−k)",
        "smoothed_ma": "Smoothed MA  (window=5)",
        "cumul_plateau": "Cumulative plateau  C(n) = C∞·n/(n+n½)",
    }

    for model_key, ax in plot_configs:
        fit = model_map.get(model_key)

        if model_key == "cumul_plateau":
            # Plot cumulative
            ax.scatter(sessions, cumul, s=12, alpha=0.6, color="#555", label="Cumulative (raw)")
            if fit and "C_inf" in fit.params and not math.isnan(fit.params["C_inf"]):
                c_inf = fit.params["C_inf"]
                n_half = fit.params["n_half"]
                n_smooth = np.linspace(sessions[0], sessions[-1], 300)
                y_smooth = c_inf * n_smooth / (n_smooth + n_half)
                ax.plot(n_smooth, y_smooth, color=colors[model_key], lw=2,
                        label=f"C∞={c_inf:.0f}, n½={n_half:.1f}\nR²={fit.r2:.3f}  AIC={fit.aic:.0f}")
            ax.set_ylabel("Cumulative corrections")
        else:
            # Plot raw corrections
            ax.scatter(sessions, corrections, s=12, alpha=0.5, color="#555", label="Raw corrections/session")

            if fit and not math.isnan(fit.r2):
                n_smooth = np.linspace(sessions[0], sessions[-1], 300)
                params = fit.params

                if model_key == "exponential":
                    y_smooth = params["a"] * np.exp(-params["k"] * n_smooth)
                    label_ext = f"a={params['a']:.2f}, k={params['k']:.3f}\nR²={fit.r2:.3f}  AIC={fit.aic:.0f}"
                elif model_key == "power_law":
                    y_smooth = params["a"] * ((n_smooth + 1) ** (-params["k"]))
                    label_ext = f"a={params['a']:.2f}, k={params['k']:.3f}\nR²={fit.r2:.3f}  AIC={fit.aic:.0f}"
                elif model_key == "smoothed_ma":
                    # MA: plot the smoothed values at actual session points
                    w = int(params.get("window", 5))
                    ma_vals = np.array([
                        np.mean(corrections[max(0, i - w // 2): min(len(corrections), i + w // 2 + 1)])
                        for i in range(len(corrections))
                    ])
                    ax.plot(sessions, ma_vals, color=colors[model_key], lw=2,
                            label=f"window={w}\nR²={fit.r2:.3f}  AIC={fit.aic:.0f}")
                    ax.set_title(labels[model_key], fontsize=9)
                    ax.set_xlabel("Session")
                    ax.set_ylabel("Corrections/session")
                    ax.legend(fontsize=8)
                    continue

                ax.plot(n_smooth, y_smooth, color=colors[model_key], lw=2, label=label_ext)

            ax.set_ylabel("Corrections/session")

        ax.set_xlabel("Session")
        ax.set_title(labels[model_key], fontsize=9)
        ax.legend(fontsize=8)
        ax.set_ylim(bottom=0)

    plt.tight_layout()
    chart_path = out_dir / f"{profile.name.replace(' ', '_').lower()}.png"
    fig.savefig(str(chart_path), dpi=130, bbox_inches="tight")
    plt.close(fig)
    return str(chart_path)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


PROFILES: list[tuple[str, str, tuple[list[int], list[float]]]] = [
    ("exponential", "Clean exponential decay (a=6, k=0.045, σ=0.5)", generate_exponential_profile()),
    ("power_law", "Anderson-style power-law decay (a=7, k=0.55, σ=0.4)", generate_power_law_profile()),
    ("plateau", "Fast early decay then stable floor", generate_plateau_profile()),
    ("noisy_real", "Noisy real-world brain (spikes, partial convergence, 100 sessions)", generate_noisy_real_profile()),
]


def run_profile(name: str, description: str, sessions: list[int], corrections: list[float], charts: bool) -> ProfileResult:
    n_arr = np.array(sessions, dtype=float)
    c_arr = np.array(corrections, dtype=float)
    cumul = list(np.cumsum(c_arr))

    fits = [
        fit_exponential(n_arr, c_arr),
        fit_power_law(n_arr, c_arr),
        fit_smoothed_ma(n_arr, c_arr, window=5),
        fit_cumulative_plateau(n_arr, c_arr),
    ]

    # Recommendation: best R² on per-session scale (exclude cumul_plateau which is on cumulative scale)
    per_session_fits = [f for f in fits if f.model != "cumul_plateau"]
    best = max(per_session_fits, key=lambda f: f.r2) if per_session_fits else fits[0]
    rec = f"Best fit (per-session R²): {best.model}  R²={best.r2:.3f}  AIC={best.aic:.0f}"

    result = ProfileResult(
        name=name,
        description=description,
        n_sessions=len(sessions),
        sessions=sessions,
        corrections=[round(c, 3) for c in corrections],
        cumulative=[round(c, 3) for c in cumul],
        fits=fits,
        recommendation=rec,
    )

    if charts:
        out_dir = HERE / "results" / "curve_fitting_charts"
        chart_path = make_charts(result, out_dir)
        result.chart_path = chart_path

    return result


def print_table(results: list[ProfileResult]) -> None:
    models = ["exponential", "power_law", "smoothed_ma", "cumul_plateau"]
    model_labels = {
        "exponential": "Exp decay",
        "power_law": "Power law",
        "smoothed_ma": "Smoothed MA",
        "cumul_plateau": "Cumul plateau",
    }

    header = f"{'Profile':<20}  {'Model':<14}  {'R²':>7}  {'AIC':>8}  {'RSS':>10}  {'Params'}"
    sep = "-" * len(header)
    print()
    print("Convergence Curve Model Comparison (GRA-1300)")
    print(sep)
    print(header)
    print(sep)

    for pr in results:
        fit_map = {f.model: f for f in pr.fits}
        first = True
        for model in models:
            fit = fit_map.get(model)
            if not fit:
                continue
            profile_col = pr.name if first else ""
            first = False
            r2_str = f"{fit.r2:.4f}" if not math.isnan(fit.r2) else "  N/A "
            aic_str = f"{fit.aic:.1f}" if not math.isinf(fit.aic) else "  ∞   "
            rss_str = f"{fit.rss:.2f}" if not math.isinf(fit.rss) else "  ∞   "
            param_str = "  ".join(f"{k}={v}" for k, v in fit.params.items())
            print(f"{profile_col:<20}  {model_labels[model]:<14}  {r2_str:>7}  {aic_str:>8}  {rss_str:>10}  {param_str}")
        print()

    print(sep)
    print()
    print("Notes:")
    print("  R²: on original per-session scale (except cumul_plateau: on cumulative scale)")
    print("  AIC: n·ln(RSS/n) + 2k.  Lower = better fit per parameter count.")
    print("  Smoothed MA k=1 (window treated as single hyperparameter)")
    print()

    # Aggregate winner table
    print("Winner by profile (highest per-session R²):")
    for pr in results:
        per_session = [f for f in pr.fits if f.model != "cumul_plateau"]
        if per_session:
            best = max(per_session, key=lambda f: f.r2 if not math.isnan(f.r2) else -99)
            print(f"  {pr.name:<20}  {best.model:<14}  R²={best.r2:.4f}")
    print()


def main() -> None:
    p = argparse.ArgumentParser(description="GRA-1300 convergence curve model comparison")
    p.add_argument("--brain-path", default=None, help="Path to real brain dir for additional data")
    p.add_argument("--quick", action="store_true", help="Skip chart generation")
    args = p.parse_args()

    profiles_to_run = list(PROFILES)

    # Optionally load real brain data
    if args.brain_path:
        import sqlite3

        db_path = Path(args.brain_path) / "system.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            rows = conn.execute(
                "SELECT session, COUNT(*) as cnt FROM events "
                "WHERE type = 'CORRECTION' AND session IS NOT NULL AND session > 0 "
                "GROUP BY session ORDER BY session"
            ).fetchall()
            conn.close()
            if len(rows) >= 5:
                real_sessions = [r[0] for r in rows]
                real_corrections = [float(r[1]) for r in rows]
                profiles_to_run.append(
                    ("real_brain", f"Real brain from {args.brain_path} ({len(real_sessions)} sessions)", (real_sessions, real_corrections))
                )
                print(f"[curve_fitting] loaded real brain: {len(real_sessions)} sessions", file=sys.stderr)
            else:
                print(f"[curve_fitting] real brain too sparse ({len(rows)} sessions) — skipping", file=sys.stderr)

    results = []
    for name, desc, (sessions, corrections) in profiles_to_run:
        print(f"[curve_fitting] fitting: {name}", file=sys.stderr)
        result = run_profile(name, desc, sessions, corrections, charts=not args.quick)
        results.append(result)

    print_table(results)

    # Save JSON
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    out_path = out_dir / f"curve_fitting_{ts}.json"
    out_path.write_text(
        json.dumps(
            [
                {
                    "name": pr.name,
                    "description": pr.description,
                    "n_sessions": pr.n_sessions,
                    "recommendation": pr.recommendation,
                    "chart": pr.chart_path,
                    "fits": [asdict(f) for f in pr.fits],
                }
                for pr in results
            ],
            indent=2,
        )
    )
    print(f"[curve_fitting] results saved: {out_path}", file=sys.stderr)

    if not args.quick:
        chart_dir = HERE / "results" / "curve_fitting_charts"
        print(f"[curve_fitting] charts saved: {chart_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
