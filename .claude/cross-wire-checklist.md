# Cross-Wire Execution Checklist
# Run at wrap-up step 9 AFTER scoring audit dimensions.
# Each cross-wire has a trigger condition and action. Check every one. No skipping.

## Instructions
For each cross-wire below:
1. Check the TRIGGER condition
2. If triggered: execute the ACTION and increment the "fires" counter
3. If the action produces a useful change: increment "value_produced" counter
4. Log results to brain/system-patterns.md Cross-Wire Performance table
5. If not triggered: skip silently (don't log non-events)
6. Write summary to brain/sessions/neural-bus.md: `[HH:MM] [cross-wire] [FIRED/CLEAN] CW=[list of fired] value=[Y/N]`

## Output Format (show to Oliver at wrap-up step 9)

### Cross-Wire Status (mandatory interpretation — never just "skipped" or "none fired")

**If any cross-wires fired:**
```
CROSS-WIRES: [N] fired
- CW-[X]: [trigger] → [action taken] → [what changed]
- CW-[Y]: [trigger] → [action taken] → [what changed]
```

**If zero cross-wires fired, choose one interpretation:**
```
CROSS-WIRES: 0 fired — HEALTHY CLEAN SESSION
(Existing rules worked. No new signals required system changes.)
```
OR
```
CROSS-WIRES: 0 fired — POTENTIAL THRESHOLD DRIFT ⚠
(3+ consecutive sessions with zero fires. Cross-wire thresholds may need recalibration.
Last fire: Session [N], CW-[X]. Review whether trigger conditions are too strict.)
```

**If any cross-wires are dormant:**
```
DORMANT: CW-[X] ([N] sessions dormant) — [wake check: recent CLAUDE.md change? new tool? new CW?]
```
Check each dormant connection against the dormancy re-evaluation trigger (LOOP_RULE_69). If a recent structural change should wake it, say so.

### Compound Brain Status (one line, always shown after cross-wire status)
```
COMPOUND BRAIN: [X/5] active. [Status sentence from brain/system-patterns.md]
```

**Indicators:**
1. Tasks completed this week >= 3
2. Corrections applied automatically >= 1 this week
3. Workflows saved >= 1 lifetime
4. Quality score trend = UP or FLAT (not DOWN, not "building baseline")
5. Days since last working session <= 7

**Read current values from brain/system-patterns.md Compound Brain Status table.**

---

## CW-1: Auditor → Gates (LOOP_RULE_28)
**TRIGGER:** Any audit dimension scored below 7 this session
**CHECK:** Does a gate in .claude/gates.md cover that dimension?
**ACTION YES:** Tighten the relevant gate step (add specificity or raise bar)
**ACTION NO:** Flag for new gate step creation in review-queue.md
**TRACK:** auditor_to_gate_fires, improvements_made

## CW-2: Gates → Lessons (LOOP_RULE_29)
**TRIGGER:** Any gate caught a real problem this session (not rubber-stamped)
**CHECK:** Is this problem pattern already in lessons.md?
**ACTION YES:** Skip (already captured)
**ACTION NO:** Auto-generate lesson: "[DATE] GATE-GENERATED: [gate] caught [problem] → [rule]"
**TRACK:** gate_to_lesson_fires, lessons_generated

## CW-3: Lessons → CARL (LOOP_RULE_30)
**TRIGGER:** Any lesson has prevented the same mistake 3+ times (check system-patterns.md Lesson Effectiveness)
**CHECK:** Is this lesson already a CARL rule?
**ACTION YES:** Graduate lesson to archive
**ACTION NO:** Promote to CARL rule in appropriate domain. Remove from lessons.md.
**TRACK:** lesson_to_carl_fires, rules_created

## CW-4: Smoke → Lessons (LOOP_RULE_31)
**TRIGGER:** Any smoke check failed this session
**CHECK:** Is there already a lesson for this failure mode?
**ACTION YES:** Skip
**ACTION NO:** Auto-generate lesson with the fix included
**TRACK:** smoke_to_lesson_fires, lessons_generated

## CW-5: Rubric Drift → Tighten (LOOP_RULE_32)
**TRIGGER:** Oliver corrected a self-score by 2+ points on same output type 3 times (check audit-log.md)
**CHECK:** Has this output type been corrected 3+ times?
**ACTION:** Tighten that rubric dimension by 1 point in quality-rubrics.md
**TRACK:** drift_corrections, rubrics_tightened

## CW-6: Fallback → Reorder (LOOP_RULE_33)
**TRIGGER:** A fallback tool worked on first try 5+ times while primary failed (check system-patterns.md Fallback Chain table)
**CHECK:** Has the fallback outperformed the primary 5+ times?
**ACTION:** Swap primary and fallback in fallback-chains.md
**TRACK:** reorder_fires, swaps_made

## CW-7: PATTERNS → Gates (LOOP_RULE_34)
**TRIGGER:** PATTERNS.md shows an angle with [PROVEN] failure rate >80% for a persona
**CHECK:** Is this angle already blocked in gates.md Pre-Draft gate?
**ACTION YES:** Skip
**ACTION NO:** Add blocked angle for that persona to Pre-Draft gate
**TRACK:** pattern_to_gate_fires, angles_blocked
