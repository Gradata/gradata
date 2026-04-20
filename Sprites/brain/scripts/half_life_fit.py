"""
Empirical Settles-Meeder half-life fit for Gradata lesson confidence decay.

Research question: Are Gradata's 0.40/0.60/0.90 promotion thresholds
(INSTINCT / PATTERN / RULE) empirically defensible, or are they magic
numbers that should be replaced with an empirically fitted decay curve?

Method:
- Settles & Meeder (2016) half-life regression. p = 2^(-delta/h)
  log(p) / log(2) = -delta/h   =>   linear regression on 1/h.
  Paper: "A Trainable Spaced Repetition Model for Language Learning"
  ACL 2016. https://doi.org/10.18653/v1/P16-1174
- Observed trajectory per lesson = ordered (confidence, timestamp) pairs
  from lesson_transitions table + CORRECTION events (reinforcements).
- We treat a "reinforcement" as a transition where fire_count increases
  or a CORRECTION event whose lesson_desc matches. Between reinforcements,
  confidence should decay toward 0 per the Settles-Meeder kernel.
- Fit h per category (CONTENT / CODE / PROCESS / TONE / ACCURACY / ...)
  because per-lesson data is too sparse.

Output: .tmp/half-life-fit/{plots, fit_results.json, decay_data.json}

Run: python brain/scripts/half_life_fit.py
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Optional scientific stack
try:
    from scipy import optimize, stats
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except ImportError:
    HAVE_MPL = False

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BRAIN = Path("C:/Users/olive/SpritesWork/brain")
EVENTS_PATH = BRAIN / "events.jsonl"
DB_PATH = BRAIN / "system.db"
OUT_DIR = Path("C:/Users/olive/OneDrive/Desktop/Sprites Work/.tmp/half-life-fit")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Current Gradata promotion thresholds
THRESH_INSTINCT = 0.40
THRESH_PATTERN = 0.60
THRESH_RULE = 0.90

# Minimum trajectory length (distinct obs) to attempt a fit
MIN_POINTS_PER_LESSON = 3
MIN_POINTS_PER_CATEGORY = 10


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
def parse_ts(ts: str) -> float:
    """Return POSIX timestamp in days."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp() / 86400.0
    except Exception:
        return float("nan")


def load_lesson_transitions(db: Path) -> list[dict]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT lesson_desc, category, old_state, new_state,
                  confidence, fire_count, transitioned_at
           FROM lesson_transitions
           ORDER BY lesson_desc, transitioned_at"""
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        t = parse_ts(r["transitioned_at"])
        if math.isnan(t):
            continue
        out.append(
            {
                "lesson": r["lesson_desc"],
                "category": (r["category"] or "UNKNOWN").upper(),
                "old_state": r["old_state"],
                "new_state": r["new_state"],
                "confidence": float(r["confidence"] or 0.0),
                "fire_count": int(r["fire_count"] or 0),
                "t_days": t,
            }
        )
    return out


def load_corrections(path: Path) -> list[dict]:
    corrections = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("type") != "CORRECTION":
                continue
            d = e.get("data", {}) or {}
            corrections.append(
                {
                    "t_days": parse_ts(e.get("ts", "")),
                    "category": (d.get("category") or "UNKNOWN").upper(),
                    "severity": d.get("severity", "?"),
                }
            )
    return corrections


# ---------------------------------------------------------------------------
# Build per-lesson trajectories
# ---------------------------------------------------------------------------
def build_trajectories(transitions: list[dict]) -> dict[str, list[dict]]:
    """Group transitions by lesson_desc. Each trajectory is a list of obs
    ordered by time, each carrying confidence at t_days plus flag for
    reinforcement (new state above old_state in ordering, OR fire_count bump).
    """
    by_lesson: dict[str, list[dict]] = defaultdict(list)
    for tr in transitions:
        by_lesson[tr["lesson"]].append(tr)

    order_rank = {"KILLED": -1, "UNTESTABLE": 0, "INSTINCT": 1, "PATTERN": 2, "RULE": 3}

    trajectories = {}
    for lesson, obs in by_lesson.items():
        obs.sort(key=lambda r: r["t_days"])
        out = []
        prev_fc = -1
        for r in obs:
            promoted = order_rank.get(r["new_state"], 0) > order_rank.get(
                r["old_state"], 0
            )
            reinforced = promoted or (r["fire_count"] > max(prev_fc, 0))
            out.append(
                {
                    "t_days": r["t_days"],
                    "confidence": r["confidence"],
                    "new_state": r["new_state"],
                    "category": r["category"],
                    "reinforced": reinforced,
                }
            )
            prev_fc = r["fire_count"]
        trajectories[lesson] = out
    return trajectories


def extract_decay_pairs(
    trajectories: dict[str, list[dict]],
) -> dict[str, list[tuple[float, float]]]:
    """For each lesson, emit (delta_days_since_last_reinforcement, p) pairs
    where p = observed confidence / confidence_at_last_reinforcement.

    p in (0, 1], delta >= 0. These are the regression inputs.
    Returns: dict category -> list of (delta, p).
    """
    by_cat: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for lesson, obs in trajectories.items():
        anchor_t = None
        anchor_c = None
        category = obs[0]["category"] if obs else "UNKNOWN"
        for o in obs:
            if o["reinforced"] or anchor_t is None:
                if o["confidence"] > 1e-6:
                    anchor_t = o["t_days"]
                    anchor_c = o["confidence"]
                    continue
            if anchor_t is None or anchor_c is None:
                continue
            delta = o["t_days"] - anchor_t
            if delta <= 0:
                continue
            # Skip KILLED (hard terminal, not decay)
            if o["new_state"] == "KILLED":
                continue
            # Normalise confidence
            if o["confidence"] <= 0:
                # Treat as near-0 recall to fit decay
                p = 1e-3
            else:
                p = min(1.0, o["confidence"] / max(anchor_c, 1e-6))
            if p <= 0 or p > 1.001:
                continue
            by_cat[category].append((delta, p))
    return by_cat


# ---------------------------------------------------------------------------
# Settles-Meeder fit
# ---------------------------------------------------------------------------
def fit_half_life(deltas: np.ndarray, ps: np.ndarray) -> dict:
    """Fit p = 2^(-delta/h). Linearise: y = log2(p) = -delta / h.
    So slope m = -1/h; h = -1/m. Use least squares through origin.

    Also fit via nonlinear curve_fit (if scipy) for a better estimate.
    """
    if len(deltas) < 3:
        return {"n": len(deltas), "h_days": None, "method": "insufficient"}

    # Clip to avoid log(0)
    ps_c = np.clip(ps, 1e-4, 1.0)
    y = np.log2(ps_c)

    # Linear fit through origin: minimise sum (y + delta/h)^2 -> h = -sum(d^2) / sum(d*y)
    num = float(np.sum(deltas * deltas))
    den = float(np.sum(deltas * y))
    if den >= 0 or num <= 0:
        h_lin = None
    else:
        h_lin = -num / den

    # Nonlinear fit: p = 2^(-delta/h)
    h_nl = None
    ci = None
    if HAVE_SCIPY and h_lin is not None and h_lin > 0:
        try:
            def model(d, h):
                h = max(h, 1e-3)
                return np.power(2.0, -d / h)

            popt, pcov = optimize.curve_fit(
                model, deltas, ps_c, p0=[h_lin], bounds=(1e-3, 1e4), maxfev=5000
            )
            h_nl = float(popt[0])
            if pcov is not None and np.all(np.isfinite(pcov)):
                se = float(np.sqrt(pcov[0, 0]))
                ci = (max(0.0, h_nl - 1.96 * se), h_nl + 1.96 * se)
        except Exception:
            h_nl = None

    h = h_nl if h_nl is not None else h_lin
    return {
        "n": int(len(deltas)),
        "h_days": h,
        "h_linear": h_lin,
        "h_nonlinear": h_nl,
        "ci95": ci,
        "method": "nonlinear" if h_nl is not None else ("linear" if h_lin else "failed"),
    }


def bootstrap_h(deltas: np.ndarray, ps: np.ndarray, n_boot: int = 500) -> dict:
    """Bootstrap over observations. Return median + 95% CI of h."""
    if len(deltas) < MIN_POINTS_PER_CATEGORY:
        return {"median": None, "ci95": None, "n_boot": 0}
    rng = np.random.default_rng(42)
    hs = []
    n = len(deltas)
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        f = fit_half_life(deltas[idx], ps[idx])
        if f["h_days"] and f["h_days"] > 0 and f["h_days"] < 1e4:
            hs.append(f["h_days"])
    if len(hs) < 20:
        return {"median": None, "ci95": None, "n_boot": len(hs)}
    hs = np.array(hs)
    return {
        "median": float(np.median(hs)),
        "ci95": (float(np.percentile(hs, 2.5)), float(np.percentile(hs, 97.5))),
        "n_boot": int(len(hs)),
    }


# ---------------------------------------------------------------------------
# Threshold analysis
# ---------------------------------------------------------------------------
def empirical_thresholds(
    fits: dict[str, dict],
    trajectories: dict[str, list[dict]],
    reinforcement_interval_days: float,
) -> dict:
    """Given fitted h per category, the steady-state confidence that a
    lesson will retain at its typical reinforcement interval (tau) is:

        p_steady = 2^(-tau / h)

    A promotion threshold T is defensible if, at the observed tau, a
    lesson reaching T has p_steady > some retention target (say 0.5).

    We compute p_steady at tau = reinforcement_interval_days for each
    category. If the observed promotion confidence (0.60 for PATTERN,
    0.90 for RULE) lands above p_steady(tau) the threshold is too
    strict for that category; below it, too lax.
    """
    out = {}
    for cat, f in fits.items():
        h = f.get("h_days")
        if not h or h <= 0:
            continue
        tau = reinforcement_interval_days
        p_steady = 2.0 ** (-tau / h)
        # Suggested empirical PATTERN threshold = p_steady at 2*tau
        # (lesson survives two reinforcement cycles => stable pattern)
        p_pattern_suggested = 2.0 ** (-(2 * tau) / h)
        # Suggested RULE = p_steady at 4*tau (robust across 4 cycles)
        p_rule_suggested = 2.0 ** (-(4 * tau) / h)
        out[cat] = {
            "h_days": h,
            "tau_days": tau,
            "p_steady_at_tau": p_steady,
            "p_pattern_suggested": p_pattern_suggested,
            "p_rule_suggested": p_rule_suggested,
        }
    return out


def estimate_reinforcement_interval(trajectories: dict[str, list[dict]]) -> float:
    """Median days between reinforcements across all lessons."""
    gaps = []
    for lesson, obs in trajectories.items():
        last_t = None
        for o in obs:
            if o["reinforced"]:
                if last_t is not None:
                    gaps.append(o["t_days"] - last_t)
                last_t = o["t_days"]
    if not gaps:
        return 1.0
    gaps = [g for g in gaps if g > 0]
    return float(np.median(gaps)) if gaps else 1.0


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def make_plot(
    by_cat_data: dict[str, list[tuple[float, float]]],
    fits: dict[str, dict],
    out_path: Path,
    thresholds: tuple[float, float, float] = (0.40, 0.60, 0.90),
):
    if not HAVE_MPL:
        return False
    categories = [c for c in by_cat_data if fits.get(c, {}).get("h_days")]
    categories = sorted(categories, key=lambda c: -len(by_cat_data[c]))[:6]
    if not categories:
        return False

    fig, ax = plt.subplots(figsize=(9, 6))
    colors = plt.cm.tab10(np.linspace(0, 1, len(categories)))

    # Max delta for x axis
    max_delta = 0
    for c in categories:
        if by_cat_data[c]:
            max_delta = max(max_delta, max(d for d, _ in by_cat_data[c]))
    max_delta = min(max_delta, 20.0) if max_delta > 0 else 10.0
    ds = np.linspace(0.01, max_delta, 200)

    for i, cat in enumerate(categories):
        pts = by_cat_data[cat]
        h = fits[cat]["h_days"]
        n = fits[cat]["n"]
        xs = np.array([p[0] for p in pts])
        ys = np.array([p[1] for p in pts])
        ax.scatter(xs, ys, s=14, alpha=0.35, color=colors[i])
        curve = np.power(2.0, -ds / h)
        ax.plot(ds, curve, color=colors[i], lw=2, label=f"{cat} (h={h:.2f}d, n={n})")

    # Promotion thresholds
    for t, name, style in [
        (thresholds[0], "INSTINCT (0.40)", "--"),
        (thresholds[1], "PATTERN (0.60)", "--"),
        (thresholds[2], "RULE (0.90)", "--"),
    ]:
        ax.axhline(y=t, color="black", linestyle=style, alpha=0.4, lw=1)
        ax.text(max_delta * 0.98, t + 0.01, name, fontsize=8, ha="right", alpha=0.6)

    ax.set_xlabel("Days since last reinforcement")
    ax.set_ylabel("Relative recall p = confidence / confidence_at_reinforcement")
    ax.set_title(
        "Gradata lesson confidence decay (Settles-Meeder fit)\n"
        "p = 2^(-delta/h) per category"
    )
    ax.set_ylim(-0.02, 1.05)
    ax.set_xlim(0, max_delta)
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right", fontsize=8)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f"[load] transitions from {DB_PATH}")
    transitions = load_lesson_transitions(DB_PATH)
    print(f"  -> {len(transitions)} transitions across "
          f"{len({t['lesson'] for t in transitions})} lessons")

    print(f"[load] corrections from {EVENTS_PATH}")
    corrections = load_corrections(EVENTS_PATH)
    print(f"  -> {len(corrections)} CORRECTION events")

    trajectories = build_trajectories(transitions)
    print(f"[build] {len(trajectories)} lesson trajectories")

    long_enough = {k: v for k, v in trajectories.items() if len(v) >= MIN_POINTS_PER_LESSON}
    print(f"  -> {len(long_enough)} trajectories with >= {MIN_POINTS_PER_LESSON} points")

    tau = estimate_reinforcement_interval(trajectories)
    print(f"[tau] median reinforcement interval: {tau:.3f} days")

    by_cat = extract_decay_pairs(trajectories)
    print(f"[decay] category pair counts:")
    for c, pairs in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        print(f"  {c:20s} n={len(pairs)}")

    fits = {}
    boots = {}
    for cat, pairs in by_cat.items():
        if len(pairs) < MIN_POINTS_PER_CATEGORY:
            continue
        deltas = np.array([p[0] for p in pairs], dtype=float)
        ps = np.array([p[1] for p in pairs], dtype=float)
        f = fit_half_life(deltas, ps)
        fits[cat] = f
        boots[cat] = bootstrap_h(deltas, ps)

    print(f"\n[fits] {len(fits)} categories fit:")
    for cat, f in sorted(fits.items(), key=lambda x: -x[1]["n"]):
        h = f["h_days"]
        ci = f.get("ci95")
        b = boots.get(cat, {})
        print(
            f"  {cat:20s} n={f['n']:3d}  h={h:7.3f}d  "
            f"{('ci=[%.3f,%.3f]' % ci) if ci else ''} "
            f"boot_median={b.get('median')}"
        )

    emp = empirical_thresholds(fits, trajectories, tau)

    # Aggregate across categories (weighted by n)
    total_n = sum(f["n"] for f in fits.values())
    if total_n:
        weighted_h = sum(f["h_days"] * f["n"] for f in fits.values() if f["h_days"]) / total_n
    else:
        weighted_h = None

    global_p_pattern = (
        2.0 ** (-(2 * tau) / weighted_h) if weighted_h else None
    )
    global_p_rule = (
        2.0 ** (-(4 * tau) / weighted_h) if weighted_h else None
    )

    # Save
    out = {
        "dataset": {
            "n_transitions": len(transitions),
            "n_unique_lessons": len({t["lesson"] for t in transitions}),
            "n_trajectories_usable": len(long_enough),
            "n_corrections": len(corrections),
            "tau_days_median": tau,
        },
        "fits_per_category": fits,
        "bootstraps_per_category": boots,
        "empirical_thresholds_per_category": emp,
        "weighted_global": {
            "h_days": weighted_h,
            "p_pattern_suggested_2tau": global_p_pattern,
            "p_rule_suggested_4tau": global_p_rule,
        },
        "current_thresholds": {
            "INSTINCT": THRESH_INSTINCT,
            "PATTERN": THRESH_PATTERN,
            "RULE": THRESH_RULE,
        },
        "scipy_available": HAVE_SCIPY,
        "matplotlib_available": HAVE_MPL,
    }
    fit_json = OUT_DIR / "fit_results.json"
    fit_json.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\n[save] {fit_json}")

    decay_json = OUT_DIR / "decay_data.json"
    decay_json.write_text(
        json.dumps({k: v for k, v in by_cat.items()}, indent=2), encoding="utf-8"
    )
    print(f"[save] {decay_json}")

    if HAVE_MPL:
        plot_path = OUT_DIR / "decay_curves.png"
        ok = make_plot(by_cat, fits, plot_path)
        if ok:
            print(f"[plot] {plot_path}")
    else:
        print("[plot] matplotlib unavailable; skipping figure.")

    return out


if __name__ == "__main__":
    main()
