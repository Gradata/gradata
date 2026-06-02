# GRA-1300: Convergence Curve Math — Model Comparison

**Date:** 2026-05-21  
**Branch:** GRA-1291-prompt-injection-survey (filed under convergence research)  
**Bench:** `bench/curve_fitting.py`  
**Charts:** `bench/results/curve_fitting_charts/`

---

## Problem Statement

The current "convergence curve" in `gradata prove` (cli.py:777) is an OLS linear regression of raw `(session_n, corrections)` points. Three problems:

1. A straight line through a decaying signal is systematically wrong — it undershoots early sessions and overshoots later ones
2. Sparse session data makes the sparkline jagged; no visual sense of "converging"
3. The slope value (e.g. `-0.08 corrections/session`) is unitless and gives users no intuition

This doc compares four candidate replacement models and makes a shipping recommendation.

---

## Models Tested

| # | Model | Formula | Free params | Use case |
|---|-------|---------|-------------|----------|
| 1 | Exponential decay | `y = a · e^(−kn)` | 2 (a, k) | "Learning to zero" — natural for skill acquisition |
| 2 | Power law | `y = a · (n+1)^(−k)` | 2 (a, k) | Anderson-style: fast early gain, long slow tail |
| 3 | Smoothed MA | rolling mean, window=5 | 1 (window) | Visual smoother only — no parametric form |
| 4 | Cumulative plateau | `C(n) = C∞ · n / (n + n½)` | 2 (C∞, n½) | Michaelis-Menten: total-lifetime-corrections budget |

**Fit method:**
- Exponential: log-linear OLS on `log(y) ~ n`  
- Power law: log-log OLS on `log(y) ~ log(n+1)`  
- Smoothed MA: centred rolling mean (no fitting)  
- Cumulative plateau: OLS on linearised form `n/C(n) = n½/C∞ + (1/C∞)·n`

**Quality metrics:**
- R² on original per-session scale (except cumulative plateau: on cumulative scale)
- AIC = `n · ln(RSS/n) + 2k` (Gaussian log-likelihood; lower = better)

---

## Results

### Profile 1 — Clean exponential decay (synthetic, 80 sessions)

Data generated as `y = 6·exp(−0.045·n) + N(0, 0.5)`. Ground truth is exponential.

| Model | R² | AIC | Params |
|-------|----|-----|--------|
| Exponential decay | **0.929** | **−138.4** | a=6.17, k=0.048 |
| Power law | −2.236 | +166.9 | (diverges) |
| Smoothed MA | **0.948** | −165.7 | window=5 |
| Cumul plateau | 0.996 (cumul) | +137.6 | C∞=180, n½=26 |

**Insight:** Power law performs _catastrophically_ on exponential data (R²=−2.24). The two models are genuinely incompatible in the long tail: exponential decay tends to zero, power law decays slower. Smoothed MA edges out exponential on R² because it adapts locally — but it provides no extractable number.

---

### Profile 2 — Power-law decay (synthetic, 80 sessions)

Data generated as `y = 7·(n)^(−0.55) + N(0, 0.4)`. Anderson-style skill acquisition.

| Model | R² | AIC | Params |
|-------|----|-----|--------|
| Exponential decay | 0.384 | −15.4 | a=2.04, k=0.024 |
| Power law | **0.846** | **−126.6** | a=10.57, k=0.755 |
| Smoothed MA | 0.835 | −122.9 | window=5 |
| Cumul plateau | 0.983 (cumul) | +168.0 | C∞=114, n½=27 |

**Insight:** Power law is the correct fit here; exponential is substantially worse (0.384 vs 0.846). The MA ties with the power law, which shows the MA is a near-universal smoother for monotone-decreasing series but can't distinguish the functional form.

---

### Profile 3 — Fast early decay then stable floor (synthetic, 80 sessions)

Decays from ~5 to ~1 in first 20 sessions, then stable noise floor around 1.

| Model | R² | AIC | Params |
|-------|----|-----|--------|
| Exponential decay | 0.193 | −7.3 | a=1.61, k=0.014 |
| Power law | 0.650 | −74.2 | a=6.07, k=0.541 |
| Smoothed MA | **0.897** | **−174.1** | window=5 |
| Cumul plateau | 0.953 (cumul) | +262.8 | C∞=128, n½=32 |

**Insight:** Both exponential and power law assume corrections → 0 monotonically but never truly level off at a non-zero floor. The plateau profile defeats both. The MA wins cleanly because it fits the step-function shape that no two-parameter smooth model can. Power law's concavity gives it a slight edge over exponential.

---

### Profile 4 — Noisy real-world (synthetic, 100 sessions)

Slow exponential trend + Gaussian noise (σ=1.2) + occasional spikes (8% chance, 2–5 extra corrections). Models a brain with occasional new-domain sessions.

| Model | R² | AIC | Params |
|-------|----|-----|--------|
| Exponential decay | 0.159 | +128.1 | a=5.90, k=0.013 |
| Power law | 0.093 | +135.6 | a=14.47, k=0.421 |
| Smoothed MA | **0.373** | **+96.7** | window=5 |
| Cumul plateau | 0.997 (cumul) | +348.5 | C∞=879, n½=139 |

**Insight:** All parametric models are poor on noisy real-world data. This is expected: no smooth two-parameter curve can fit a signal where 8% of sessions have exogenous spikes. The MA wins R² by adapting locally, but at 0.37 it's still not a great fit. The cumulative plateau's R²=0.997 is misleading — cumulative curves are intrinsically smooth and this C∞=879 value (total lifetime corrections) is unreliable from noisy data.

---

## Cross-Profile Summary

| Profile | Exp R² | Power R² | MA R² | Winner (R²) |
|---------|--------|----------|-------|-------------|
| Exponential ground truth | 0.929 | −2.24 | **0.948** | MA (visual) |
| Power law ground truth | 0.384 | **0.846** | 0.835 | Power law |
| Plateau | 0.193 | 0.650 | **0.897** | MA |
| Noisy real-world | 0.159 | 0.093 | **0.373** | MA (weak) |

The smoothed MA wins on R² in 3 of 4 profiles, but this is a red herring: **the MA has no extractable metric**. It cannot answer "is the brain converging?" or "what's the half-life?". It's a visual tool only.

Among parametric models:
- **Exponential is the better default assumption** (most learning-to-zero processes are exponential)
- **Power law wins when the tail is heavy** (Anderson-style cognitive skill acquisition)
- When data is sparse and noisy, both parametric models fail — which is exactly where Mann-Kendall (already implemented) is the right statistical test

---

## Recommendation

### SHIP exponential decay as the parametric model

**Decision: SHIP exponential, use smoothed MA as the visual sparkline layer.**

Rationale:

1. **Half-life is user-legible.** From `k`, compute `half_life = ln(2) / k`. "Your correction rate halves every 15 sessions" is something users understand. "Slope = −0.08 corrections/session" is not.

2. **Exponential is the correct asymptotic form for learning-to-zero.** Power law tails decay too slowly (errors never truly reach zero). Exponential aligns with neuroscience forgetting curves (Ebbinghaus, ACT-R) and with the existing `correction_tracking.py:_half_life_sessions()` helper (which already uses log-linear OLS on the decay constant).

3. **Power law is not universally better.** It wins on synthetic power-law data but catastrophically fails on exponential data (R²=−2.24). We don't know the true functional form of real user brains. Exponential is the safer prior.

4. **Smoothed MA as the visual layer, not the model.** The MA's higher R² is a local-fitting advantage — it cannot report a half-life, trend direction, or statistical significance. Use it purely to draw the sparkline so the visual doesn't look jagged. Report the exponential parameters (or slope verdict) as the headline metric.

5. **Cumulative plateau is a promising dashboard metric, not a CLI metric.** C∞ (total expected corrections) and n½ (session at which the brain hits 50% of its learning) are genuinely interesting for a dashboard but too abstract for `gradata prove` output. File as follow-on.

### What NOT to ship

- **KEEP OLS slope:** The current implementation. Should be replaced. Linear fit on a decaying signal is systematically wrong and the slope value has no user-intuition.
- **SHIP power law only:** Wins on power-law data but fails hard on exponential, which is the more common shape. A mixture or model-selection step (AIC comparison) would help but adds complexity without clear user value.
- **SHIP smoothed MA as the model:** It has no extractable trend metric. The trend verdict (converging/stable/diverging) still needs a parametric or non-parametric test.

---

## Suggested Implementation

In `cli.py cmd_prove()`, replace the OLS slope block (lines 777–797) with:

```python
# 1. Fit exponential decay: log_y = log(a) - k*n
import math, numpy as np

n_arr = np.arange(len(counts), dtype=float)
c_arr = np.array(counts, dtype=float)
mask = c_arr > 0
if mask.sum() >= 3:
    log_c = np.log(c_arr[mask])
    A = np.column_stack([np.ones(mask.sum()), n_arr[mask]])
    coeffs, *_ = np.linalg.lstsq(A, log_c, rcond=None)
    beta0, beta1 = coeffs
    a = math.exp(beta0)
    k = -beta1
    half_life = math.log(2) / k if k > 0 else float("inf")
else:
    k, half_life = 0.0, float("inf")

if k > 0.01:
    print(f"  Verdict: CONVERGING  (half-life ≈ {half_life:.0f} sessions)")
elif k > -0.01:
    print(f"  Verdict: STABLE / CONVERGED  (k ≈ 0)")
else:
    print(f"  Verdict: DIVERGING  (corrections rising)")
```

The smoothed MA is purely visual — use it for the chart sparkline if a web dashboard is added.

---

## Caveats and Limits

1. **No real 100-session brain exists yet.** All analysis is on synthetic data. The noisy-real profile (Profile 4) is the closest approximation. Fit quality on real data may differ.

2. **Spikes invalidate parametric fits.** When a user starts a new domain or has a bad week, corrections spike. Neither exponential nor power law is robust to this. The Mann-Kendall test (already in `brain_convergence()`) handles outlier-resistance correctly — the exponential fit is a display supplement, not a replacement.

3. **Cumulative plateau is inflated.** The R²=0.99 on cumulative data is inherent to cumulative summation, not model quality. Don't compare it directly to per-session R².

4. **AIC penalises large-n poorly for MA.** Treating k=1 for the MA is conservative. A proper information-theoretic comparison would use leave-one-out CV, which is outside scope here.

---

## Files

| Path | Description |
|------|-------------|
| `bench/curve_fitting.py` | Reference implementation — all 4 models, synthetic + real-brain support |
| `bench/results/curve_fitting_*.json` | Raw fit results (R², AIC, params per profile) |
| `bench/results/curve_fitting_charts/*.png` | One annotated 4-panel chart per profile |
| `docs/research/convergence-curve-math.md` | This doc |

---

[analyst-autoresearch] GRA-1300 research complete. Decision: **SHIP exponential decay** + smoothed MA as visual layer.
