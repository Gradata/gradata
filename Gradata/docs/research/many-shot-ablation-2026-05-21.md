# GRA-1310: Many-Shot Ablation — Does k=50 Outperform k=10?

**Status:** ✅ COMPLETE  
**Date:** 2026-05-21  
**Author:** analyst (claude_local)  
**Harness:** `bench/many_shot_ablation.py`

---

## Executive Summary

Agarwal 2024 shows monotonic compliance gains to ~1000 shots when shots are relevant.
We currently inject k=5 rules per prompt. This study tests whether raising the budget
to k=10, k=20, or k=50 is worth the context tax at our current corpus size.

**Verdict: Keep k=5. Do not raise default to 10, 20, or 50 at the current corpus size.**

The surprising finding: **k=10 is fractionally *worse* than k=5** (compliance_est 0.655
vs 0.660). The noise penalty from 4 extra irrelevant rules outweighs the small coverage
gain. k=50 technically achieves the highest estimated compliance (0.688), but at 93%
corpus injection it is no longer targeted JIT — it is a global rule dump.

Schedule a re-evaluation when real graduated rules exceed 200.

---

## Method

| Parameter | Value |
|-----------|-------|
| Corpus | 54 rules (4 real RULE_GRADUATED + 50 synthetic) |
| Probes | 40 labeled queries, 4 per category × 10 categories |
| Scorer | BM25 (established default from GRA-1292) |
| k sweep | [5, 10, 20, 50] — 5 is the current `DEFAULT_MAX_RULES` |
| Noise factor | 0.30 (Agarwal 2024: irrelevant shots degrade attention ~30%) |
| Tokens/rule | ~15 (estimated; prefix [R85] + ~12-word description) |

**Analytical compliance model (no LLM calls):**

```
compliance_est(k) = coverage(k) × (1 − 0.30 × fp_rate(k))
```

Where:
- `coverage(k)` = fraction of probes with ≥1 relevant rule in top-k
- `fp_rate(k)` = 1 − precision@k = fraction of injected rules that are noise
- 0.30 = noise degradation factor from Agarwal 2024

This is an analytical upper bound. Actual LLM compliance depends on model, rule
phrasing, and task context. Precision for ±15pp calibration is documented in
Model Caveats below.

---

## Results

| k | Coverage@k | Precision@k | FP count | FP rate | **Compliance est** | Context tok | Lat (ms) |
|---|-----------|-------------|----------|---------|-------------------|-------------|----------|
| **5** (current) | 0.875 | 0.180 | 4.1 | 0.820 | **0.660** | 75 | 0.18 |
| **10** | 0.900 | 0.092 | 9.1 | 0.907 | **0.655** | 150 | 0.18 |
| **20** | 0.925 | 0.048 | 19.1 | 0.953 | **0.661** | 300 | 0.20 |
| **50** | 0.975 | 0.020 | 49.0 | 0.980 | **0.688** | 750 | 0.19 |

### Marginal gains

| k jump | Δ coverage | Δ compliance | Δ context tokens | Compliance / 100 extra tokens |
|--------|-----------|-------------|-----------------|-------------------------------|
| 5→10 | +0.025 | **−0.005** | +75 | −0.007 |
| 10→20 | +0.025 | +0.006 | +150 | +0.004 |
| 20→50 | +0.050 | +0.027 | +450 | +0.006 |

---

## Key Findings

### Finding 1: k=10 is worse than k=5 at this corpus size

Raising from k=5 to k=10 **decreases** estimated compliance by 0.005 (0.655 vs 0.660).
The mechanism: at a 54-rule corpus, each additional slot in the top-k budget absorbs a
nearly-always-irrelevant rule (precision@10 = 0.092 vs 0.180 at k=5). The noise penalty
`0.30 × fp_rate` grows faster than the coverage benefit.

This directly contradicts the naive reading of Agarwal 2024: raising k helps *only when
the added shots are relevant*. At corpus size 54, BM25 has already placed the most
relevant rules in the top-5 slots. Slots 6-10 are largely noise.

### Finding 2: k=50 technically "wins" but it is not JIT injection

At k=50 with a 54-rule corpus, we inject 50/54 = **93% of all rules**. This is
equivalent to injecting the entire rule book regardless of draft content — the
targeted, per-draft relevance signal that is the whole point of JIT is lost.
Coverage@50 = 0.975 is nearly trivially achieved; precision@50 = 0.020 means
1 rule in 50 is actually relevant. The BM25 ranker is contributing almost nothing
to selectivity.

### Finding 3: Compliance gains are nearly flat from k=5 to k=20

Compliance estimates:
- k=5: 0.660
- k=10: 0.655 (−0.005)
- k=20: 0.661 (+0.001)
- k=50: 0.688 (+0.028)

The entire range k=5 to k=20 spans only 0.001 compliance difference. No budget
increase in this range clears a 2 percentage-point materiality threshold.
Only k=50 clears that bar, but only because it becomes a global dump.

### Finding 4: Category-specific gaps reveal where higher k matters

The categories where k=5 misses coverage are:
- **CODE_REVIEW**: 0.50 at k=5, 0.75 at k=10, 1.00 at k=50
- **SALES**: 0.75 at k=5, 0.75 at k=10, 1.00 at k=20
- **SECURITY**: 0.75 at k=5, 0.75 at k=10, 0.75 at k=20, 1.00 at k=50
- **TONE**: 0.75 across k=5 through k=20, still 0.75 at k=50

TONE's persistent 0.75 cap at all budgets reveals a corpus gap, not a k problem.
The two TONE probes that miss at k=50 are stylistically distinct from the TONE rules
in the corpus — this is a coverage/diversity issue. Adding more varied TONE rules
matters more than raising k.

---

## Corpus-Size Sensitivity

At what corpus size does k=50 become worth it?

The efficiency crossover: k=50 needs precision@50 > 0.05 (current 0.020) to
contribute meaningfully over k=5. That requires a corpus where at least 5 rules
per average probe are relevant.

| Corpus size | k=50 / N | Estimated precision@50 |
|-------------|----------|------------------------|
| 54 (current) | 93% | 0.020 (almost random) |
| 200 rules | 25% | ~0.06–0.10 |
| 500 rules | 10% | ~0.15–0.20 |
| 1000 rules | 5% | ~0.20–0.30 |

**At 200+ real rules, k=20 becomes the obvious default.** At 500+ rules, k=50
starts to exploit Agarwal 2024's monotonic gain property: the model gets many
shots of relevant guidance at high precision, not a global rule dump.

---

## Recommendation

### For now (corpus < 200 rules): Keep `GRADATA_JIT_MAX_RULES=5`

No budget increase from 5 produces a compliance gain that clears the 2pp materiality
threshold. k=10 is counterproductive on this corpus. k=20 breaks even. k=50 is
near-global injection rather than targeted JIT.

**Do not change the default.**

### Set a re-evaluation trigger: 100+ real RULE_GRADUATED events

The synthetic corpus gives clean benchmark results but not production signal.
When `events.jsonl` shows ≥100 RULE_GRADUATED events, re-run this harness with:

```bash
python3 -m bench.many_shot_ablation
```

At that point, precision@k estimates will be based on real corpus diversity, and
the right k may shift materially upward.

### Document k=50 for large-corpus operators

Add a note in `GRADATA_JIT_MAX_RULES` docs:

> Default: 5. At corpus sizes ≥500 rules, consider 20–50 for improved coverage.
> k=50 is counterproductive below ~200 rules (noise exceeds coverage benefit).

### Deferred: TONE coverage gap requires new rules, not higher k

The 0.75 TONE cap at all k values is a corpus problem. Add 3–5 more TONE rules
covering register switching and negative instruction patterns to close this gap
independently of k tuning.

---

## Answer to the Question

**Does k=50 outperform k=10?**

Technically yes on this benchmark: 0.688 vs 0.655 estimated compliance. But for
the wrong reasons. At a 54-rule corpus, k=50 is near-exhaustive injection and k=10
is already noise-dominated. Neither number reflects what these k values would
produce on a real 500-rule corpus.

**Practically, no.** k=10 is *worse* than the current k=5. k=50 is not JIT injection
at this corpus size. The Agarwal 2024 monotonic-gain result applies to relevant shots;
at 93% corpus coverage, nearly all injected rules are irrelevant to any given draft.

**The right question** is not "10 vs 50" but "when does raising k become safe?" —
and the answer is at 200+ real rules for k=20, 500+ for k=50.

---

## Model Caveats

1. **Compliance_est is analytical, not measured.** No LLM calls were made. The
   noise_factor=0.30 is drawn from Agarwal 2024 and has not been calibrated against
   Gradata's specific models (claude-sonnet-4-6). Real compliance may vary ±15pp.

2. **Corpus is 93% synthetic.** 4 of 54 rules are real. Real rules have different
   length, vocabulary, and domain distribution. Precision/coverage estimates may
   shift when the real corpus grows.

3. **BM25 selectivity degrades at high k/N.** The results at k=50 / N=54 would not
   reproduce at k=50 / N=500. The harness models what happens today, not the target state.

4. **LLM inference cost of extra tokens is not captured.** Retrieval is sub-ms at
   all k values. The real cost of k=50 is prompt-token overhead slowing model
   inference — a second-order effect not modeled here.

5. **tokens/rule estimate (15) is approximate.** Actual rule length varies. SECURITY
   rules average ~18 tokens; FORMAT rules ~12. Total context cost estimates are ±30%.

---

## A/B Test Plan (for future validation)

When corpus reaches 100+ real rules, run a live A/B test:
- **Control**: `GRADATA_JIT_MAX_RULES=5`
- **Treatment A**: `GRADATA_JIT_MAX_RULES=10`
- **Treatment B**: `GRADATA_JIT_MAX_RULES=20`
- **Metric**: rule-adherence rate (measured via correction events per session)
- **Guardrail**: no increase in session corrections vs control
- **Window**: 2 weeks × 50+ sessions per arm

This will ground-truth the analytical model against real model behavior.

---

## References

- Agarwal et al. 2024: *Many-Shot In-Context Learning* — monotonic gains to ~1000 relevant shots
- GRA-1292: `docs/research/gra-1292-injection-scorer-benchmark.md` — BM25 vs embedding
- `bench/many_shot_ablation.py` — benchmark harness (this study)
- `bench/results/many-shot-ablation-20260521T125337.md` — raw benchmark output
- `src/gradata/hooks/jit_inject.py` — JIT injection implementation
- `DEFAULT_MAX_RULES = 5` in `jit_inject.py` — current production default

[analyst-wiki] GRA-1310 research complete.
