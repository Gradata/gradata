# Autoresearch Loop Protocol

Operational guardrails for long-running autoresearch loops (`autoresearch/*` branches driven by agent iteration against a KEEP/DISCARD ledger).

## Why this exists

The `autoresearch/consolidation` branch ran for **325 iterations** without a rebase checkpoint. On arrival it had drifted **16 merge conflicts** from main, forcing PR #112 to be closed rather than merged. The final ~50 iterations produced only cosmetic docstring reflow (-1 LOC per file, no structural change) — the loop had exhausted its signal hundreds of iterations before it stopped.

See `Sprites/sessions/autoresearch-consolidation-wrapup-iter325.md` for the retrospective that motivated this protocol.

## The invariants

### 1. Maximum 50 iterations per loop

After 50 iterations, either open a PR and merge/rebase before continuing, or stop the loop and re-evaluate whether the strategy is still producing signal.

**Why 50:** empirically, consolidation loops plateau on signal after ~100-150 iters. Capping at 50 forces a review before the plateau sets in, and keeps branch drift below the point where rebase becomes expensive.

### 2. Mandatory rebase checkpoint at iteration 25 and pre-PR

At iteration 25, the loop runner must fetch origin/main, rebase, and abort if more than 3 conflicts surface. Repeat immediately before opening any PR from the loop branch.

**Why:** main moves during long loops. PR #112's 16 conflicts compounded because nobody rebased between iter-1 and iter-325. A 25-iter window keeps drift to 3-5 conflicts max.

### 3. One concern per PR

A loop may touch many files, but each PR it produces addresses exactly one of: dead code removal, module inlining, duplicate elimination, or public-surface trim. Multi-concern loops produced PRs that reviewers couldn't reason about. Split them before opening.

### 4. Minimum one-minor-version deprecation lead time

If a loop removes public API surface (exports, module paths, CLI flags), the previous minor version must have shipped a DeprecationWarning for it. Example: removing `gradata.patterns` shim in 0.8.0 requires that 0.7.x (or earlier) emit the warning. Internal APIs (`_`-prefixed, not in `__all__`) are exempt.

### 5. Signal-exhaustion test

Every 10 iterations, compute the composite metric delta vs. iter-0. If the last 10 iterations together moved the composite less than 0.1%, stop the loop — signal is exhausted. The consolidation loop violated this: the last 10 iters moved composite by 0.05% and the runner kept going.

## Enforcement

The `program.md` spec for each autoresearch loop must reference this protocol and encode the invariants as runner pre-conditions.

## History

- 2026-04-19 — Protocol drafted after `autoresearch/consolidation` wrap-up at iter-325. Derived from Pragmatist+Skeptic council review during S117.
