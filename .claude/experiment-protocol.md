# Experiment Protocol (Spotify Confidence Platform)

> Spotify's key insight: win rate is 12%. Learning rate is 64%. Most value comes from
> understanding what doesn't work. We track both.

## Experiment Format
```
EXPERIMENT: [short-name]
HYPOTHESIS: [specific, testable prediction]
VARIANT A: [control — current approach]
VARIANT B: [test — the change]
SAMPLE: [how many, which prospects]
METRIC: [what we measure]
STATUS: DESIGN | RUNNING | CONCLUDED | APPLIED | ARCHIVED
```

## Lifecycle
1. **DESIGN** — write hypothesis before executing. "I think X will outperform Y because Z."
2. **RUNNING** — execute both variants, tag each touch with experiment name
3. **CONCLUDED** — enough data to decide (minimum 5 per variant for pipeline tier)
4. **APPLIED** — winner becomes default in PATTERNS.md
5. **ARCHIVED** — no winner, but learning captured

## Learning Rate Tracking
Every concluded experiment produces a LEARNING, even if neither variant wins:
- "Referral ask didn't increase replies but generated 2 actual referrals" = LEARNING
- "Both variants got 0 replies — timing was the issue, not angle" = LEARNING
- "Variant B won 3:1 — case-study beats pain-point for agency owners" = WIN + LEARNING

Track: total_experiments, win_rate (% with clear winner), learning_rate (% that taught something)

## Active Experiment Slots
Maximum 3 experiments running simultaneously (prevent interaction effects — per Spotify's methodology).
When an experiment concludes, a slot opens for the next one.

## Experiment Ideas Queue
Keep a backlog of hypotheses to test. Priority by: expected impact × ease of testing.

## Integration with Loop
- Each experiment variant gets standard Loop tags PLUS `experiment: [name], variant: [A|B]`
- At wrap-up, check running experiments for new data points
- Concluded experiments feed PATTERNS.md with `[EXPERIMENT]` confidence tag
- Learning rate tracked in system-patterns.md alongside audit scores

## Starter Experiments (run these first)
1. **breakup-referral**: Do breakup emails with referral ask outperform breakup-only?
2. **subject-length**: Do 3-word subjects outperform 6+ word subjects for cold pipeline?
3. **quantification-first**: Does leading with a number ("260 hrs/year") outperform leading with pain?
