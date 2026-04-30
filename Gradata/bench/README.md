# PMR-100 — Procedural Memory Retention Benchmark

The single benchmark Gradata needs before launch.

## What it measures

100 scripted sessions. Each session:
1. Inject a correction (draft → final) into a fresh Brain
2. Add N distractor turns
3. Probe with a task that should fire the rule learned from the correction
4. Score: did `apply_brain_rules()` return the right rule? recall@1, recall@3

## Why it matters

Memory systems remember what you said. **Gradata claims to learn how you think.**
The PMR-100 number is the only thing that proves this claim. Without it, the
SDK is just a SQLite logger with FSRS scoring on top.

## Run

```bash
python -m bench.pmr_100              # full run (100 sessions)
python -m bench.pmr_100 --quick      # 10 sessions for fast feedback
python -m bench.pmr_100 -n 3         # custom session count
```

## Initial baseline (2026-04-30)

First run: 3 sessions, all BEHAVIORAL class.
- Rules extracted: **0%**
- Recall@1: **0%**
- Recall@3: **0%**
- Median session: 0.186s

Interpretation: `Brain.correct()` does not synchronously extract rules that
are returned by `apply_brain_rules()` on the first probe. Either the
extraction is async/queued (daemon-only), graduation thresholds prevent the
rule from being callable, or the matching path needs warm-up. **This is the
work.** Track this number on every PR. Ship when ≥70% recall@1 across all 6
correction classes — Anthropic-tier memory bench results.

## Adding scenarios

Edit `pmr_100.py:SCENARIOS`. Cover all `CorrectionType` enum values. Each
scenario needs:
- `draft`/`final` pair (a real correction)
- `probe` (a future task that should fire the rule)
- `expected_keywords` (substrings that should appear in the retrieved rule's text)
