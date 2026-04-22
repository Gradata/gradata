# Merge Semantics for Graduated Rules (Council Decision 9)

**Status:** SPEC v1 (2026-04-21)
**Ship-gate for:** `/events/pull` (Phase 2)
**Blocks:** Multi-device sync, team brains, cross-session rule reconciliation.

---

## 1. Problem

Two devices diverge on the same graduated rule and later sync:

- Device A: user confirms "never use passive voice" 4×. Lesson graduates to PATTERN (0.62).
- Device B: user overrides on a legal draft — "passive voice is acceptable in legal docs." The same underlying pattern hash emits `RULE_GRADUATED` with a contradictory scope and lands at PATTERN (0.58).

`content_hash` deduplicates identical events. It does not reconcile contradictory ones. Without a merge grammar, `/events/pull` produces "multi-device chaos with a nice API" (Innovator).

---

## 2. Scope of this spec

- Applies only to `RULE_GRADUATED`, `RULE_DEMOTED`, and `META_RULE_SYNTHESIZED` events that share a `(category, pattern_hash)` key.
- Does not apply to raw `CORRECTION` events — those are append-only facts and never conflict.
- Does not apply to `IMPLICIT_FEEDBACK`, `OUTPUT_ACCEPTED`, or other telemetry — those aggregate, never merge.

---

## 3. Resolution strategy — three tiers

### Tier 1 — Automatic: last-write-wins by `(ts, device_id)`

When two graduation events share `(category, pattern_hash)` and disagree on `new_state` or `confidence`:

1. Compare `ts`. Later wins.
2. Tie on `ts` → compare `device_id` lexicographically. Higher wins.

Rationale: graduation is monotonic in the user's experience. The later correction reflects the user's most recent judgment. `device_id` tiebreak is arbitrary but deterministic — critical for convergence.

**Applies when:** `|Δconfidence| < conflict_threshold` (default `0.15`) AND `new_state` agrees (both PATTERN or both RULE). The boundary is strict-less-than: a delta of exactly `conflict_threshold` routes to Tier 2.

### Tier 2 — Conflict queue: surface to user

When `|Δconfidence| ≥ 0.15` OR `new_state` disagrees (one promotes, one demotes):

1. Neither version graduates. Both events stored, neither materialized to `lessons.state`.
2. A `RULE_CONFLICT` event is emitted locally with both source events' IDs.
3. Dashboard surfaces the conflict: "Device A says X, Device B says Y. Which applies?"
4. User's resolution emits `RULE_CONFLICT_RESOLVED` pointing at the winning `event_id`.
5. Materializer reads the resolved event and updates `lessons.state` accordingly.

Rationale: contradictions that large are not noise — they're genuine disagreement about the rule's scope. The user must adjudicate. Silent resolution would erase the signal.

### Tier 3 — Source-authority override

A future `team:admin`-scoped key can emit a `RULE_OVERRIDE` event that trumps any Tier 1/2 resolution for a `(team_id, category, pattern_hash)` scope. This is the path for organizations where the senior editor's call always wins.

**Not in Phase 2.** Documented so the envelope doesn't close.

---

## 4. Meta-rule conflicts

`META_RULE_SYNTHESIZED` events reference `source_lesson_ids`. If any source lesson is in Tier 2 conflict, the meta-rule does **not** materialize until the underlying conflict resolves. A `META_RULE_BLOCKED` event surfaces this in the dashboard.

---

## 5. Convergence guarantee

Given any two devices A and B that have applied the same ordered event stream (including resolutions), their materialized `lessons` table must be bit-identical:

```
for all (A, B) devices, event_stream:
  apply(A, event_stream) == apply(B, event_stream)
```

This is the property test that ships with the materializer (Phase 2).

---

## 6. Implementation checklist (Phase 2)

- [ ] `Δconfidence` threshold configurable via `cloud-config.json` (`conflict_threshold: 0.15`)
- [ ] `RULE_CONFLICT` event type added to `_tag_taxonomy`
- [ ] `RULE_CONFLICT_RESOLVED` event type added
- [ ] Materializer treats Tier 2 conflicts as "hold"
- [ ] Dashboard conflict-queue UI
- [ ] Property test: `apply(device_A, stream) == apply(device_B, stream)` across shuffled orderings (Phase 2 ships 200+ orderings in CI; 10k orderings remains the stretch target once the corpus grows large enough to stay under the ~90s CI budget)
- [ ] Ship-gate: zero materializer divergence across 30 days of simulated sync

---

## 7. Open questions (flag for Phase 3)

- **Temporal staleness:** if Device A's "later" write is 6 months after Device B's and the user's style evolved, is LWW still right? Maybe decay + re-confirmation required.
- **Cross-brain conflicts:** when marketplace ships, one brain's graduated rule could contradict another brain the user also subscribes to. Scope inheritance rules needed.
- **Rollback:** if a resolved conflict turns out wrong, is there an undo? Current answer: emit a new `RULE_OVERRIDE` event. No destructive rollback.
