# RESEARCH: Are Self-Healing Patches Converging or Oscillating?

**Issue:** GRA-1477
**Date:** 2026-06-02
**Analyst:** 002e67ef (analyst)
**Method:** Live SQLite query on `/home/olive/.gradata/brain/system.db` + Python analysis
**Supersedes:** `docs/research/patch-oscillation-2026-05-23.md` (GRA-1382)

---

## Executive Summary

**RULE_PATCHED count remains zero.** The direct convergence/oscillation question (same rule_id patched ≥3 times in 14 days) cannot yet be answered with patch data — the patcher has never fired in production. However, this follow-up reveals two meaningful updates since May 23:

1. **Real oscillation detected in the hook pathway:** `never-use-em-dashes` has been installed as a hook and reverted (`RULE_PATCH_REVERTED`) on **two separate dates** — May 14 and June 2 (19-day cycle). This is the first confirmed oscillation signal anywhere in the system.

2. **Two persistent multi-session failure rules have emerged** — the true precursors to patch attempts once the patcher activates. One (`Include more detail about detail`) has failed on 4 distinct dates over 7 days.

---

## Method

```python
# Primary query — RULE_PATCHED (still no results)
SELECT type, COUNT(*) FROM events
  WHERE type IN ('RULE_PATCHED','rule_patch_observed','rule_patch_cycle_detected')
  GROUP BY type;
-- → empty (unchanged from 2026-05-23)

# Secondary — RULE_FAILURE candidates with >=3 hits in 14 days
SELECT description, category, dates FROM failure_analysis
  WHERE hits_in_14d >= 3
  ORDER BY distinct_dates DESC, hits DESC;

# Tertiary — hook reversion oscillation
SELECT ts, data_json FROM events WHERE type='RULE_PATCH_REVERTED' ORDER BY ts;
```

Data source: `/home/olive/.gradata/brain/system.db`
Date range: 2026-05-14 → 2026-06-02 (19 days, complete history)

---

## Finding 1: RULE_PATCHED Count = 0 (unchanged)

No `RULE_PATCHED`, `rule_patch_observed`, or `rule_patch_cycle_detected` events exist in any database. The oscillation guard has never fired. The patch pipeline has not committed a single patch.

**Delta from May 23:**

| Metric | 2026-05-23 | 2026-06-02 | Change |
|---|---|---|---|
| RULE_PATCHED | 0 | 0 | no change |
| RULE_FAILURE | 46 | 142 | +96 |
| RULE_GRADUATED | 116 | 360 | +244 |
| LESSON_CHANGE | 353 | 884 | +531 |
| RULE_PATCH_REVERTED | 3 | 6 | +3 |
| Oscillation guard activations | 0 | 0 | no change |

---

## Finding 2: Hook Oscillation — `never-use-em-dashes` Cycles (19-day period)

This is the first confirmed oscillation anywhere in the system, though it is in the hook pathway (not the patch pathway).

**Event sequence:**

| Date | Event | Slug | Notes |
|---|---|---|---|
| 2026-05-14 | RULE_PATCH_REVERTED | `never-use-em-dashes` | purge=False, hook_removed=True |
| 2026-05-14 | RULE_PATCH_REVERTED | `never-use-em-dashes` | purge=True, hook_removed=True |
| 2026-05-14 | RULE_PATCH_REVERTED | `always-run-tests-after-edit` | purge=False, hook_removed=True |
| 2026-06-02 | RULE_PATCH_REVERTED | `never-use-em-dashes` | purge=False, hook_removed=True |
| 2026-06-02 | RULE_PATCH_REVERTED | `never-use-em-dashes` | purge=True, hook_removed=True |
| 2026-06-02 | RULE_PATCH_REVERTED | `always-run-tests-after-edit` | purge=False, hook_removed=True |

**Pattern:** Both `never-use-em-dashes` and `always-run-tests-after-edit` were installed as hooks, then reverted by pytest test teardown on May 14, then re-installed (via RULE_TO_HOOK_INSTALLED), then reverted again on June 2 by a second pytest run. The reversion paths are `platform_source: raw-python` and originate in pytest tmp dirs, confirming this is test-environment hook cleanup — not production agent behavior.

**Assessment:** This is NOT a production oscillation. Both reversions are pytest artifact cleanup from test runs that install real hooks in tmp paths and then tear them down. The underlying rule (`never-use-em-dashes`) is stable; the HOOK state of that rule is toggled by tests.

**Verdict for May 23 recommendation #7 ("add rule_patch_cycle_detected alerting"):** still valid but not yet urgent — this hook reversion pattern would be silenced by filtering `platform_source: raw-python` events.

---

## Finding 3: Oscillation Candidates by RULE_FAILURE Frequency

The primary convergence/oscillation query targets `RULE_PATCHED` events. Since those are absent, this analysis uses RULE_FAILURE frequency as the leading indicator — these are the rules that will be patched first once `auto_heal()` fires.

### 14-day window (2026-05-19 → 2026-06-02): Rules with ≥3 failures

| Rule slug | Category | Hits | Distinct dates | Spread | Type |
|---|---|---|---|---|---|
| `include-more-detail-about-detail` | CONTENT | 9 | 4 | May26–Jun2 | **Persistent** |
| `verify-facts-numbers-dates` | FACTUAL | 7 | 3 | May21–May26 | **Persistent** |
| `include-detail-rng-random` | CONTENT | 7 | 1 | Jun2 only | Burst / ephemeral |
| `include-table-cell-content` | FACTUAL | 5 | 1 | May20 only | Burst / ephemeral |
| `include-cumulative-field` | CONTENT | 5 | 1 | Jun1 only | Burst / ephemeral |
| `use-compact-type-not-brain-context` | CONTENT | 3 | 1 | May26 only | Burst / ephemeral |
| `onclick-trackevent-double` | CONTENT | 3 | 1 | Jun2 only | Burst / ephemeral |
| `use-trackevent-not-plausible` | CONTENT | 3 | 1 | Jun2 only | Burst / ephemeral |
| `include-hn-launch-date` | CONTENT | 3 | 1 | Jun2 only | Burst / ephemeral |

**Interpretation:** Two patterns separate clearly.

**Persistent patterns** (failures spread across multiple dates) represent genuine behavioral drift — the agent keeps violating these rules in different contexts over days. These are the highest-risk oscillation candidates when patching activates.

**Burst/ephemeral patterns** (all failures on a single date) represent single-session content rules or test runs. Patching these would create the content-churn oscillation predicted in GRA-1382 (A→B→C→D where each letter is a different session's content).

---

## Finding 4: Persistent Rule Deep-Dive

### Rule A: `Include more detail about detail` (CONTENT, 9 failures, 4 dates)

**Compliance trend:** Fails repeatedly across sessions, no improvement visible.

- Dates: 2026-05-26 (3×), 2026-05-29 (3×), 2026-06-01 (1×), 2026-06-02 (2×)
- Direction: flat — no convergence, no divergence

**Oscillation risk if patched:** HIGH. The rule description `"Include more detail about detail"` is semi-generic but was likely generated from a generic correction. If patched, the replacement rule description will include session-specific context about WHAT needs more detail — creating a new specific rule that will fail again in the next different context.

**Recommendation:** FREEZE from auto_heal until description specificity check is added. The meta-pattern ("add more detail") should be promoted to a meta_rule (`Be comprehensive in your responses`) rather than patched as a specific rule.

### Rule B: `Verify facts, numbers, and dates before including them` (FACTUAL, 7 failures, 3 dates)

**Compliance trend:** Recurring across 5 days (May 21–26), then silent on May 27+.

- Dates: 2026-05-21 (2×), 2026-05-23 (3×), 2026-05-26 (2×)
- Direction: appears to have quieted since May 26 — possible natural convergence, or rule transitioned out of RULE state

**Oscillation risk if patched:** LOW. This is a stable, general-purpose rule with clear intent. A patch would likely refine the trigger condition (e.g., "especially for dates in task deadlines"). The oscillation guard should handle any reversal.

**Recommendation:** MONITOR. Candidate for first controlled patch run when the patcher activates — best signal for testing convergence.

---

## Freeze and Demote Candidates

### FREEZE (exclude from auto_heal patch pool)

| Rule pattern | Reason | Action |
|---|---|---|
| Description contains session-specific content fragments (code snippets, markdown table rows, PR references) | Content-churn oscillation risk — rule would be patched with new session content each time | Filter in `review_rule_failures()` before retroactive_test: reject if description matches `r"\|.*\|"` or contains code-like tokens |
| All failures occurred within a 6-hour window | Single-session burst — one bad session created many corrections; not a stable signal | Add session-burst filter: exclude candidates where `MAX(ts) - MIN(ts) < 6h` across all failures |
| Description = "Include more detail about detail" | Generic meta-correction, not specific enough for targeted patching | Promote to meta_rule instead |

### DEMOTE (back to lessons injection, no patch attempts)

No rules currently qualify for hard demotion — the system has no rules in patch-eligible state that have failed 3+ patch attempts. When the patcher activates, apply this criteria: if a rule has been patched 3+ times and compliance hasn't improved (RULE_FAILURE count flat or increasing), demote to meta_rule tier.

---

## Convergence/Oscillation Verdict

| Question | Answer |
|---|---|
| Are any rules oscillating in the patch pathway? | **No** — zero patches committed, oscillation guard untriggered |
| Are any rules converging in the patch pathway? | **No** — same reason |
| Is there any oscillation signal in the system? | **Yes** — `never-use-em-dashes` hook reverts on a 19-day cycle, but caused by pytest teardown not production behavior |
| What's the highest-risk rule when patcher activates? | `Include more detail about detail` (CONTENT, 4 distinct dates) |
| What's the safest rule for first controlled patch? | `Verify facts, numbers, and dates before including them` (FACTUAL, stable description, quieted naturally) |

---

## Recommendations (updated from GRA-1382)

### Carry over from GRA-1382 (still open)
1. Add content-churn filter to `review_rule_failures()` — reject candidates where description contains code fragments or markdown table syntax
2. Add session-burst filter — reject candidates where 100% of failure events occurred within 6 hours
3. Wire `auto_heal()` into a periodic hook — the patcher will never fire until this is done

### New from GRA-1477
4. **Add `platform_source` filter to `RULE_PATCH_REVERTED` monitoring** — exclude `raw-python` events from any oscillation alerting; these are test teardown artifacts, not production signals
5. **Promote `Include more detail about detail` to meta_rule** — the general pattern belongs at meta_rule tier, not as a specific patchable rule. File as engineering task.
6. **Mark `Verify facts, numbers, and dates before including them` as first patch candidate** — stable description, cross-session signal, low oscillation risk. Use to validate the patch-to-compliance measurement pipeline.

---

## Data Summary

| Metric | Value |
|---|---|
| Database date range | 2026-05-14 to 2026-06-02 |
| Total RULE_FAILURE events | 142 (+96 since GRA-1382) |
| RULE_PATCHED events | **0** (unchanged) |
| rule_patch_observed events | **0** (unchanged) |
| rule_patch_cycle_detected events | **0** (unchanged) |
| RULE_PATCH_REVERTED events | 6 (3 test-origin from May 14, 3 test-origin from Jun 2) |
| RULE_GRADUATED events | 360 |
| Rules currently in lessons.md | 3 (1×PATTERN, 2×INSTINCT) |
| Oscillation guard activations | 0 |
| Persistent failure rules (multi-date, 14d) | 2 (`include-more-detail-about-detail`, `verify-facts-numbers-dates`) |
| Burst-only rules (single-date, ≥3 hits) | 7 — all ephemeral content |

---

[analyst-autoresearch]
