# Gradata Autoresearch

Adapted from Karpathy's autoresearch. You are an autonomous researcher
testing Gradata's learning pipeline. Your goal: find the correction
strategy that produces the fastest graduation (INSTINCT → PATTERN → RULE)
with the lowest correction density.

## Setup

1. Read `sdk/scripts/autoresearch_harness.py` for full context
2. Create branch: `git checkout -b autoresearch/<tag>`
3. Initialize `results.tsv` with header row
4. Run baseline: `python sdk/scripts/autoresearch_harness.py --sessions 15`
5. Record baseline metrics

## What you CAN modify

Only the CORRECTION STRATEGY section at the top of `autoresearch_harness.py`:
- `CATEGORIES` — which correction categories to use
- `CORRECTIONS_PER_SESSION` — how many corrections per session
- `CATEGORY_STRATEGY` — "sparse" vs "dense"
- `CATEGORIES_PER_SESSION` — how many categories per session (if sparse)
- `CORRECTION_TEMPLATES` — the draft/final pairs per category

## What you CANNOT modify

Everything below the "HARNESS" comment. That is the fixed evaluation
(like prepare.py in Karpathy's version).

## The goal

Get the lowest `correction_density` AND the earliest `first_pattern` session.
Secondary: get `rules_applied: true` as early as possible.

Since the harness runs in ~10 seconds, you can run ~6 experiments per minute.

## Metric extraction

```bash
grep "^correction_density:\|^first_pattern:\|^rules_applied:" run.log
```

## Logging results

Log to `results.tsv` (tab-separated):

```
commit	density	first_pattern	rules_applied	status	description
```

## The experiment loop

LOOP FOREVER:
1. Look at current results — what worked, what didn't
2. Modify the CORRECTION STRATEGY in `autoresearch_harness.py`
3. `git commit -m "experiment: <description>"`
4. Run: `python sdk/scripts/autoresearch_harness.py > run.log 2>&1`
5. Extract: `grep "^correction_density:\|^first_pattern:\|^rules_applied:" run.log`
6. If density improved OR first_pattern is earlier: KEEP (advance branch)
7. If worse: DISCARD (`git reset --hard HEAD~1`)
8. Record in results.tsv
9. Repeat

## Key hypotheses to test

- Does sparse correction (1-2 categories/session) graduate faster than dense?
- What's the minimum corrections_per_session for graduation to work?
- Do some categories graduate faster than others?
- Does template variety affect lesson quality?
- What happens with 3 corrections in the SAME category? (should create meta-rules)

## NEVER STOP

Once the loop begins, do NOT pause to ask. Run experiments autonomously
until manually stopped. You are a researcher. If you run out of ideas,
re-read the graduation math in `sdk/src/gradata/enhancements/self_improvement.py`.
