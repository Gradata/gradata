"""
Statistical & ML engine for Gradata (SDK Copy).
====================================================
Portable version — uses _paths for DB_PATH instead of hardcoded paths.
All functions work with ANY data volume including 0.

Implements: Bayesian Beta-Binomial, Wilson CI, Rolling Window,
Brier Score, EWMA Control Charts, Correction Half-Life,
Task Success Rate, MTBF/MTTR, Fisher's Exact, Power Analysis,
Logistic Regression, Naive Bayes Lead Scoring,
Theil-Sen + Mann-Kendall Trend Analysis.
"""

import math
from collections import Counter, defaultdict


# ============================================================================
# 0. TREND ANALYSIS (Theil-Sen + Mann-Kendall)
# ============================================================================

def trend_analysis(y: list[float]) -> tuple[float, float]:
    """Combined Theil-Sen slope + Mann-Kendall p-value in a single O(n^2) pass.

    Returns (slope, p_value). Outlier-resistant (29% breakdown point).
    EPA/USGS standard for environmental trend detection. Capped at last
    50 data points for performance. (Amorim et al. 2024, Frontiers 2020)
    """
    y = y[-50:]
    n = len(y)
    if n < 2:
        return 0.0, 1.0

    slopes = []
    s = 0
    for i in range(n):
        for j in range(i + 1, n):
            diff = y[j] - y[i]
            slopes.append(diff / (j - i))
            s += 1 if diff > 0 else (-1 if diff < 0 else 0)

    slopes.sort()
    mid = len(slopes) // 2
    slope = (slopes[mid - 1] + slopes[mid]) / 2.0 if len(slopes) % 2 == 0 else slopes[mid]

    ties = Counter(y)
    var_s = (n * (n - 1) * (2 * n + 5)) / 18
    for t in ties.values():
        if t > 1:
            var_s -= t * (t - 1) * (2 * t + 5) / 18
    if var_s <= 0:
        return slope, 1.0
    z = (s - 1) / math.sqrt(var_s) if s > 0 else (s + 1) / math.sqrt(var_s) if s < 0 else 0
    p_value = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
    return slope, p_value

# ============================================================================
# 1. BAYESIAN BETA-BINOMIAL
# ============================================================================

def beta_posterior(successes: int, trials: int, prior_alpha: float = 1.0, prior_beta: float = 1.0) -> dict:
    alpha = prior_alpha + successes
    beta_param = prior_beta + trials - successes
    mean = alpha / (alpha + beta_param)

    try:
        from scipy.stats import beta as beta_dist
        ci_low = beta_dist.ppf(0.025, alpha, beta_param)
        ci_high = beta_dist.ppf(0.975, alpha, beta_param)
    except ImportError:
        std = math.sqrt(alpha * beta_param / ((alpha + beta_param) ** 2 * (alpha + beta_param + 1)))
        ci_low = max(0, mean - 1.96 * std)
        ci_high = min(1, mean + 1.96 * std)

    def prob_above(baseline: float) -> float:
        try:
            from scipy.stats import beta as beta_dist
            return 1 - beta_dist.cdf(baseline, alpha, beta_param)
        except ImportError:
            if mean > baseline:
                return min(0.99, 0.5 + (mean - baseline) / (ci_high - ci_low + 0.001))
            return max(0.01, 0.5 - (baseline - mean) / (ci_high - ci_low + 0.001))

    p_above = prob_above(0.015)
    if p_above > 0.90:
        label = "PROVEN"
    elif p_above > 0.70:
        label = "EMERGING"
    elif p_above > 0.30:
        label = "HYPOTHESIS"
    else:
        label = "UNDERPERFORMING"

    return {
        "posterior_mean": round(mean, 4),
        "ci_95": (round(ci_low, 4), round(ci_high, 4)),
        "prob_above_baseline": round(p_above, 3),
        "confidence_label": label,
        "alpha": alpha, "beta": beta_param, "n": trials,
    }



# ============================================================================
# 2. WILSON CONFIDENCE INTERVALS
# ============================================================================

def wilson_ci(successes: int, total: int, z: float = 1.96) -> dict:
    if total == 0:
        return {"point_estimate": 0, "ci_low": 0, "ci_high": 0, "margin": 0, "display": "0% (no data)"}
    p = successes / total
    denom = 1 + z ** 2 / total
    center = (p + z ** 2 / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * total)) / total) / denom
    ci_low = max(0, center - margin)
    ci_high = min(1, center + margin)
    return {
        "point_estimate": round(p, 4),
        "ci_low": round(ci_low, 4), "ci_high": round(ci_high, 4),
        "margin": round(margin, 4),
        "display": f"{p:.1%} (CI: {ci_low:.1%}-{ci_high:.1%})",
    }


# ============================================================================
# 3. ROLLING WINDOW COMPARISON
# ============================================================================

def rolling_comparison(values: list, window: int = 10) -> dict:
    if not values:
        return {"lifetime_avg": 0, "recent_avg": 0, "delta": 0, "trend": "NO_DATA", "pct_change": 0}
    lifetime_avg = sum(values) / len(values)
    if len(values) <= window:
        return {
            "lifetime_avg": round(lifetime_avg, 4), "recent_avg": round(lifetime_avg, 4),
            "delta": 0, "trend": "INSUFFICIENT_WINDOW", "pct_change": 0,
        }
    recent = values[-window:]
    recent_avg = sum(recent) / len(recent)
    delta = recent_avg - lifetime_avg
    pct = (delta / abs(lifetime_avg)) * 100 if lifetime_avg != 0 else 0
    if abs(pct) < 5:
        trend = "STABLE"
    elif pct > 0:
        trend = "IMPROVING"
    else:
        trend = "DEGRADING"
    return {
        "lifetime_avg": round(lifetime_avg, 4), "recent_avg": round(recent_avg, 4),
        "delta": round(delta, 4), "trend": trend, "pct_change": round(pct, 1),
    }


# ============================================================================
# 4. BRIER SCORE
# ============================================================================

def brier_score(predictions_and_outcomes: list) -> dict:
    if not predictions_and_outcomes:
        return {"score": None, "calibration": "NO_DATA", "n": 0}
    n = len(predictions_and_outcomes)
    total = sum((pred - actual) ** 2 for pred, actual in predictions_and_outcomes)
    score = total / n
    if score < 0.05:
        cal = "EXCELLENT"
    elif score < 0.10:
        cal = "GOOD"
    elif score < 0.20:
        cal = "FAIR"
    elif score < 0.25:
        cal = "POOR"
    else:
        cal = "WORSE_THAN_RANDOM"
    return {"score": round(score, 4), "calibration": cal, "n": n}


# ============================================================================
# 5. EWMA CONTROL CHARTS
# ============================================================================

def ewma_control(values: list, lambda_param: float = 0.2, sigma_multiplier: float = 2.0) -> dict:
    if len(values) < 3:
        return {"ewma_current": None, "alerts": [], "status": "INSUFFICIENT_DATA"}
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    sigma = math.sqrt(variance) if variance > 0 else 0.001
    ewma = [values[0]]
    for i in range(1, len(values)):
        ewma.append(lambda_param * values[i] + (1 - lambda_param) * ewma[-1])
    alerts = []
    for i in range(len(ewma)):
        ewma_sigma = sigma * math.sqrt(
            (lambda_param / (2 - lambda_param)) * (1 - (1 - lambda_param) ** (2 * (i + 1)))
        )
        ucl = mean + sigma_multiplier * ewma_sigma
        lcl = mean - sigma_multiplier * ewma_sigma
        if ewma[i] > ucl or ewma[i] < lcl:
            alerts.append({"index": i, "value": round(values[i], 4),
                          "ewma": round(ewma[i], 4), "type": "above" if ewma[i] > ucl else "below"})
    return {
        "ewma_current": round(ewma[-1], 4), "mean": round(mean, 4), "sigma": round(sigma, 4),
        "ucl": round(mean + sigma_multiplier * sigma, 4),
        "lcl": round(max(0, mean - sigma_multiplier * sigma), 4),
        "alerts": alerts[-3:],
        "status": "IN_CONTROL" if not alerts else f"OUT_OF_CONTROL ({len(alerts)} alerts)",
    }


# ============================================================================
# 6. CORRECTION HALF-LIFE
# ============================================================================

def correction_half_life(corrections: list) -> dict:
    if not corrections:
        return {"categories": {}, "overall": "NO_DATA"}
    by_category = defaultdict(list)
    for c in corrections:
        by_category[c.get("category", "UNKNOWN")].append(c.get("session", 0))
    results = {}
    learned = 0
    recurring = 0
    for cat, sessions in by_category.items():
        sessions_sorted = sorted(sessions)
        count = len(sessions_sorted)
        span = sessions_sorted[-1] - sessions_sorted[0] if count > 1 else 0
        if count == 1:
            status = "SINGLE_OCCURRENCE"
            learned += 1
        elif span > 0:
            density = count / span
            if density < 0.1:
                status = "LEARNED"
                learned += 1
            elif density < 0.3:
                status = "IMPROVING"
            else:
                status = "RECURRING"
                recurring += 1
        else:
            status = "SAME_SESSION"
        results[cat] = {
            "occurrences": count, "first_session": sessions_sorted[0],
            "last_session": sessions_sorted[-1], "span": span,
            "density": round(count / max(span, 1), 3), "status": status,
        }
    overall = "LEARNING" if learned > recurring else "STRUGGLING" if recurring > learned else "MIXED"
    return {"categories": results, "total_categories": len(results), "learned": learned, "recurring": recurring, "overall": overall}


# ============================================================================
# 7. TASK SUCCESS RATE BY TYPE
# ============================================================================

def task_success_rate(events: list) -> dict:
    if not events:
        return {"by_type": {}, "overall_pass_rate": None}
    by_type = defaultdict(lambda: {"total": 0, "passed": 0})
    for e in events:
        t = e.get("task_type", "unknown")
        by_type[t]["total"] += 1
        if not e.get("corrected", False):
            by_type[t]["passed"] += 1
    results = {}
    for t, counts in by_type.items():
        rate = counts["passed"] / counts["total"] if counts["total"] > 0 else 0
        ci = wilson_ci(counts["passed"], counts["total"])
        results[t] = {"pass_rate": round(rate, 3), "total": counts["total"], "passed": counts["passed"], "ci": ci["display"]}
    total = sum(c["total"] for c in by_type.values())
    passed = sum(c["passed"] for c in by_type.values())
    return {
        "by_type": results,
        "overall_pass_rate": round(passed / total, 3) if total > 0 else None,
        "overall_ci": wilson_ci(passed, total)["display"] if total > 0 else "no data",
    }


# ============================================================================
# 8. MTBF / MTTR
# ============================================================================

def mtbf_mttr(corrections: list, total_sessions: int) -> dict:
    if not corrections or total_sessions == 0:
        return {"by_type": {}, "overall_mtbf": None}
    by_type = defaultdict(list)
    for c in corrections:
        by_type[c.get("task_type", c.get("category", "unknown"))].append(c.get("session", 0))
    results = {}
    for t, sessions in by_type.items():
        count = len(sessions)
        mtbf = total_sessions / count if count > 0 else total_sessions
        sessions_sorted = sorted(sessions)
        if len(sessions_sorted) > 1:
            gaps = [sessions_sorted[i+1] - sessions_sorted[i] for i in range(len(sessions_sorted)-1)]
            mttr = sum(gaps) / len(gaps)
        else:
            mttr = None
        results[t] = {"corrections": count, "mtbf": round(mtbf, 1), "mttr": round(mttr, 1) if mttr else None}
    overall_mtbf = total_sessions / len(corrections) if corrections else total_sessions
    return {"by_type": results, "overall_mtbf": round(overall_mtbf, 1), "total_corrections": len(corrections)}


# ============================================================================
# 9-12: Fisher, Power, Logistic, Naive Bayes (unchanged logic)
