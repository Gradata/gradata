# Feature Logic Audit — Dashboard Loop & Defensibility Review

**Date:** 2026-05-21  
**Author:** analyst (GRA-1326)  
**Method:** Per-tile review against four loop-risk questions  
**Scope:** All top-level dashboard tiles in Gradata Cloud

---

## Audit Method

For each dashboard tile, four questions were asked:

1. **Does this feature have a feedback loop with itself?** (e.g., self-heal patches its own patches)
2. **Does this feature claim measurable improvement without enough data?** (e.g., "100% reduction" on 0 post-observations)
3. **Does this feature show meaningful change when nothing changed?** (e.g., graduation count goes up because we re-clustered the same observations)
4. **Is the math being shown actually defensible to a YC/Bayesian reviewer?**

---

## Summary Table

| Feature | Loop risk | Fake-metric risk | Defensibility | Rating | Issue |
|---------|-----------|-----------------|---------------|--------|-------|
| Activity Feed — graduation events | HIGH | HIGH | INDEFENSIBLE | **RED** | [GRA-1331](/GRA/issues/GRA-1331) |
| Activity Feed — self-healing events | HIGH | HIGH | INDEFENSIBLE | **RED** | [GRA-1332](/GRA/issues/GRA-1332) |
| Lift Report — rule_contributions | LOW | CRITICAL | INDEFENSIBLE | **RED** | [GRA-1330](/GRA/issues/GRA-1330) |
| Self-Healing — healing_trend | HIGH | HIGH | INDEFENSIBLE | **RED** | [GRA-1333](/GRA/issues/GRA-1333) |
| Meta Rules — uniqueness + tier | MEDIUM | MEDIUM | QUESTIONABLE | **YELLOW-RED** | [GRA-1334](/GRA/issues/GRA-1334) |
| Time Saved — Tier-3 fallback | LOW | MEDIUM | MARGINAL | **YELLOW** | — |
| Corrections per Rule — CI bands | LOW | LOW | MARGINAL | **YELLOW** | — |
| Corrections tab | NONE | NONE | DEFENSIBLE | **GREEN** | — |
| Latest Rules panel | NONE | NONE | DEFENSIBLE | **GREEN** | — |
| Mistakes Caught WoW delta | NONE | NONE | DEFENSIBLE | **GREEN** | — |
| Self-Healing (loop itself) | KNOWN | KNOWN | — | tracked separately | — |
| Convergence chart | KNOWN | KNOWN | — | tracked separately | — |

---

## Detailed Findings

### RED — Activity Feed: Graduation Event Duplicates

**Issue:** [GRA-1331](/GRA/issues/GRA-1331)

**Reproduction:** Any graduation event surfaces twice in the Activity Feed.

**Root cause:** The feed backend builds its event list from two sources simultaneously:
- `lessons` table: synthetic `graduation` rows inserted by the graduation pipeline
- `events` table: rows of `type='graduation'` written by the SDK at graduation time

When the SDK writes both tables for the same graduation, the feed query emits **two entries** for a single rule promotion. Users see the same rule "Graduated to rule" twice within seconds.

**Defensibility:** None. This is a data deduplication bug, not a design choice.

**Fix:** Pick one canonical source per event type. Drop `graduation` and `self_heal_patch`/`RULE_PATCHED` event types from the raw events query; use only the lessons/rule_patches tables as sources of truth. See [GRA-1331](/GRA/issues/GRA-1331) for the exact query change.

---

### RED — Activity Feed: Self-Healing Event Duplicates

**Issue:** [GRA-1332](/GRA/issues/GRA-1332)

**Reproduction:** Any self-healing patch surfaces twice in the Activity Feed.

**Root cause:** Same dual-source pattern as graduation duplicates:
- `rule_patches` table: rows written by the self-healing pipeline
- `events` table: rows of `type='RULE_PATCHED'` written by the SDK at patch time

A single patch = count 2 in the feed (version-dependent on whether SDK emits both).

**Defensibility:** None. Same bug as graduation duplicates.

**Fix:** Remove `RULE_PATCHED` from the events query; use `rule_patches` as the sole source for self-healing feed entries. See [GRA-1332](/GRA/issues/GRA-1332).

---

### RED — Lift Report: Fabricated `estimated_corrections_prevented`

**Issue:** [GRA-1330](/GRA/issues/GRA-1330)

**Reproduction:** Any rule in the Lift Report shows `estimated_corrections_prevented = fire_count × 0.7`.

**Root cause:** The column is computed as `fire_count * 0.7` with no empirical basis for the 0.7 coefficient. A rule that fired 100 times shows "70 corrections prevented" regardless of actual recurrence-blocking behavior.

**Defensibility:** Zero. This is a fabricated number that would fail any technical due-diligence review. It implies causation (prevented corrections) when the data only shows correlation (fires). The 0.7 multiplier has no statistical derivation.

**Fix:** Remove the `estimated_corrections_prevented` column from the Lift Report query and UI. Replace with raw `fire_count` labeled "times applied" — an honest, defensible metric. See [GRA-1330](/GRA/issues/GRA-1330).

---

### RED — Self-Healing: `healing_trend` Double-Count

**Issue:** [GRA-1333](/GRA/issues/GRA-1333)

**Reproduction:** The `healing_trend` chart counts a single patch twice on SDK versions that write both `rule_patches` and `events`.

**Root cause:** The trend query adds:
- Days from `rule_patches` (primary store)
- Days from `events` (secondary write)

When both are emitted for the same patch event, the trend counter increments by 2 for a single actual patch.

**Defensibility:** None. The trend is double-counting patches on affected SDK versions.

**Fix:** Use `rule_patches` as the sole source for the healing_trend calculation; remove the `events` JOIN from the trend query. See [GRA-1333](/GRA/issues/GRA-1333).

---

### YELLOW-RED — Meta Rules: No Unique Constraint + Stale Tier Badges

**Issue:** [GRA-1334](/GRA/issues/GRA-1334)

**Reproduction:** Running synthesis multiple times accumulates duplicate meta-rules; tier badges (universal/strong/minority) become stale when source lessons are killed.

**Root cause:**
- `meta_rules` table has no `UNIQUE` constraint — repeated syncs insert duplicate rows rather than upsert
- `tier` (universal/strong/minority) is computed from `source_lesson_count` at synthesis time but **never updated** when source lessons are subsequently killed or demoted
- A meta-rule can show `tier: universal` long after enough of its sources were killed to demote it to `minority`

**Defensibility:** Questionable. Duplicate meta-rules overstate the pattern count. Stale tiers are misleading but not fabricated.

**Fix:** Add `UNIQUE` constraint on `(pattern_hash, tenant_id)` or equivalent; add `source_lesson_count` to the meta-rules API response; recompute tier at read time or on source-lesson status change. See [GRA-1334](/GRA/issues/GRA-1334).

---

### YELLOW — Time Saved: Tier-3 Fallback Overcounts

**No issue filed** (label says "Est." everywhere — honest but still misleading).

**Root cause:** The Tier-3 fallback fires on all lessons with any positive `fire_count`, including raw INSTINCT observations that never proved recurrence blocking. This inflates the "Est." time-saved number for immature rules.

**Defensibility:** Marginal. The "Est." label is honest, but showing a non-zero estimate for rules with no confirmed recurrence is misleading.

**Recommendation:** Show `—` (dash) for Tier-3 rules rather than an inflated estimate. Alternatively, gate Tier-3 on a minimum `fire_count` threshold with confirmed recurrence.

---

### YELLOW — Corrections per Rule: Hardcoded ±15% CI Bands

**No issue filed** (labeled "est. range" — honest but implies real statistics).

**Root cause:** The upper and lower CI band for corrections-per-rule is computed as `value * 1.15` and `value * 0.85` — a constant ±15% regardless of sample size.

**Defensibility:** Marginal. Labeled "est. range" (honest), but a reader familiar with statistics will infer this is a Bayesian or frequentist CI — it is neither.

**Recommendation:** Remove the sub-range bands entirely, or relabel as "approx. range (not a CI)" to prevent misinterpretation.

---

### GREEN — Corrections Tab

**No issues.** Direct database read with a `UNIQUE` constraint enforced in migration 014. No recursive math, no double-counting.

---

### GREEN — Latest Rules Panel

**No issues.** Uses real timestamps. Recurrence detection is conservative (requires confirmed recurrence, not just any fire). Graduation status reflects actual pipeline state.

---

### GREEN — Mistakes Caught WoW Delta

**No issues.** Sign math is correct. `floor=5` guard prevents spurious deltas on low-volume sessions. The week-over-week comparison is a simple subtraction — no recursive amplification.

---

## Out of Scope (Already Tracked)

- **Self-Healing loop** (rule created → patched → patched back): tracked separately, known bad.
- **Convergence chart** math: tracked separately, known bad.

---

## Verification Checklist

- [x] Audit doc filed (`docs/audit/feature-logic-audit-2026-05-21.md`)
- [x] Engineering issues filed for every RED-rated feature: [GRA-1330](/GRA/issues/GRA-1330), [GRA-1331](/GRA/issues/GRA-1331), [GRA-1332](/GRA/issues/GRA-1332), [GRA-1333](/GRA/issues/GRA-1333), [GRA-1334](/GRA/issues/GRA-1334)
- [ ] Oliver re-screenshots dashboard 1 week after fixes land — confirms no more visible nonsense
