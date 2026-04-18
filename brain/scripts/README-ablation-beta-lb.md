# Beta LB Gate Ablation — Pilot Harness

## What the gate does

`GRADATA_BETA_LB_GATE` (shipped in PR #86, `self_improvement._passes_beta_lb_gate`) adds a **Beta posterior lower-bound check** to PATTERN → RULE promotion. When enabled, a PATTERN lesson only graduates if the 5th-percentile of its `Beta(α, β)` posterior meets `GRADATA_BETA_LB_THRESHOLD` (default 0.70) **and** it has at least `GRADATA_BETA_LB_MIN_FIRES` observations (default 5). This catches the ~15–20% of current RULE-tier graduations that the v4 min2022 random-label control showed are calibrated by format rather than content. Default is OFF pending in-band measurement — this harness is that measurement.

Source: `.tmp/autoresearch-synthesis.md` §2 (#Compound opportunity: _core.py:555), §5 item 1 (scipy Beta PPF prerequisite), §6 item 2 (execution plan).

## How to run the pilot

Safety gate: the script runs a **dry-run only** unless `GRADATA_ABLATION_CONFIRM=1` is set in env. Dry-run prints trial count, token estimate, and dollar estimate, then exits without calling the API.

```bash
# Dry run (safe, no API calls):
python brain/scripts/ablation_beta_lb_gate.py --tasks 10 --iterations 2

# Actually run (paid API calls):
GRADATA_ABLATION_CONFIRM=1 python brain/scripts/ablation_beta_lb_gate.py --tasks 10 --iterations 2
```

## What it measures

Per task × iteration, two conditions are run on the same seeded synthetic brain:

| Condition | `GRADATA_BETA_LB_GATE` | Rules injected into generation |
|---|---|---|
| A (baseline) | `0` | All PATTERN lessons that pass mean-threshold graduate |
| B (gate on) | `1` | Only lessons with `Beta.ppf(0.05, α, β) >= 0.70` graduate |

Metrics:

- **Graduation-rate delta** — how many PATTERN → RULE promotions the gate blocks.
- **Preference lift** — Sonnet output scored by Haiku (1–10 overall quality). A/B position is randomized per iteration.
- **Per-lesson decision trace** — which specific lessons promoted/blocked under each condition.

Output: `.tmp/ablation_beta_lb_<timestamp>.json` with aggregates + per-task + per-lesson traces, plus a human-readable summary on stdout.

## Estimated runtime & cost

Per trial = 2 Sonnet generations (~800 in / 400 out tokens each) + 1 Haiku judge call (~1500 in / 150 out).

| Tasks | Iterations | Trials | Est. cost | Est. runtime |
|---|---|---|---|---|
| 5 | 2 | 10 | ~$0.50 | ~2 min |
| 10 | 2 | 20 | ~$1.00 | ~4 min |
| 10 | 3 | 30 | ~$1.50 | ~6 min |

Dry-run prints a precise estimate for the exact `--tasks` / `--iterations` you pass.

## Decision criteria — when to default the gate ON

Ship the gate ON (default) when **both** hold on the pilot:

1. `preference_lift_pct >= +1.0%` — generation quality improves (not just neutral)
2. `graduation_drop_pct <= 50%` — rule stream doesn't collapse

If lift is positive but graduation drop > 50%, tune `GRADATA_BETA_LB_THRESHOLD` down (try 0.60) and re-run. If lift is flat or negative, leave the gate opt-in and revisit once HLR time-decay (synthesis §5 item 5) lands — the double-blend fix may change the Beta posteriors enough to move the signal.

## Scaling up

The pilot is intentionally small (~10 tasks × 2 iters, ~20 synthetic lessons). For a rigorous replication, mirror `brain/scripts/ab_test_constitutional.py` — 4 models × multiple conditions × 16+ tasks × 3 iterations, using a real brain fixture (`--brain-fixture "$GRADATA_BRAIN"`). The v4 closer ran 432 trials; this pilot is 10–30. Treat pilot results as a direction signal, not a ship gate.

## Files

- `brain/scripts/ablation_beta_lb_gate.py` — the harness
- `tests/test_ablation_beta_lb_gate.py` — dry-run safety test, schema test, gate-delta test
- `.tmp/autoresearch-synthesis.md` — context this harness operationalises
- `src/gradata/enhancements/self_improvement.py:_passes_beta_lb_gate` — gate under test
