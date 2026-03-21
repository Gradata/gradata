# Cross-Wire Execution Checklist
# Run at wrap-up step 9 AFTER scoring audit dimensions.
# Three trigger classes: EVENT (this session), TREND (across sessions), DANGER (anomaly).
# Check every one. No skipping.

## Instructions
For each cross-wire below:
1. Check the TRIGGER condition (event, trend, or danger)
2. If triggered: execute the ACTION and update utility score: `score += value_produced ? +1 : -1`
3. Log results to brain/system-patterns.md Cross-Wire Performance table
4. If not triggered: skip silently (don't log non-events)
5. Write summary to brain/sessions/neural-bus.md: `[HH:MM] [cross-wire] [FIRED/CLEAN] CW=[list of fired] value=[Y/N]`

## Trigger Classes
- **EVENT** — fires on this-session activity (original cross-wires). Requires specific session output.
- **TREND** — fires on patterns across N sessions (integral/derivative). Always evaluable regardless of session type.
- **DANGER** — fires on contextual anomalies (immune system pattern). Session-type agnostic stress indicators.

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

### Compound Intelligence (always shown after cross-wire status)
```
CQ: [score] ([+/-N] from last session) | Trajectory: [label]
  Strongest: [dimension] ([value]%) | Weakest: [dimension] ([value]%)
```
Or if fewer than 5 metrics files exist:
```
CQ: building baseline ([N]/5 data points) | Next: [what's needed]
```

**Compute from brain/system-patterns.md CQ section.** Read metrics/ files for rolling averages. Log CQ in current session's metrics file.

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

## CW-8: Skill Miss → Description Fix
**TRIGGER:** Neural bus has SKILL_MISS signal this session (Oliver manually invoked a skill that should have auto-triggered from his message)
**CHECK:** Does the skill's description include the phrases Oliver actually used?
**ACTION YES:** Trigger condition may need loosening — add Oliver's phrasing as alternate keywords
**ACTION NO:** Add Oliver's exact phrasing to the skill description field
**TRACK:** skill_miss_fires, descriptions_fixed
**SOURCE:** Skills article pattern — description richness determines trigger reliability

## CW-9: Safety Block → Audit Trail
**TRIGGER:** Neural bus has SAFETY_BLOCK or TOOL_NOTABLE signal this session
**CHECK:** Was the block legitimate (real threat) or false positive (normal operation flagged)?
**ACTION LEGITIMATE:** Log to session note as security event. No further action.
**ACTION FALSE POSITIVE:** Loosen the specific rule or add an exception. Log which rule and why.
**TRACK:** safety_block_fires, false_positives
**SOURCE:** Nova-tracer pattern — every safety event gets a verdict, not just a log line

## CW-10: Tool Violation → Manifest Fix (DORMANT — wakes on first TOOL_DENIED signal)
**TRIGGER:** Neural bus has TOOL_DENIED signal this session
**CHECK:** Was the agent's manifest too restrictive (legitimate tool need) or did the agent overstep?
**ACTION TOO RESTRICTIVE:** Update the agent's manifest tools_allowed list. Log the addition.
**ACTION OVERSTEPPED:** Log the violation. If repeated, tighten trust_level.
**TRACK:** tool_denied_fires, manifest_updates
**SOURCE:** Genus OS — agent tool registry with allow/deny filtering

## CW-11: Correction Rate → Autonomy Scope
**TRIGGER:** Agent's correction_rate updated at wrap-up (from CORRECTION signals)
**CHECK:** Compare correction_rate against thresholds: <0.10 = eligible for trust promotion, >0.25 = trust demotion
**ACTION PROMOTE:** Flag for Oliver: "[agent] correction rate [X] over 5 sessions — eligible for trust_level increase from [current] to [next]"
**ACTION DEMOTE:** Auto-demote trust_level by one tier. Emit SYSTEM_PAUSE if consecutive_rejections >= auto_pause_threshold.
**TRACK:** trust_promotions, trust_demotions, pause_events
**SOURCE:** Genus OS Nightwatch — graduated trust based on merge rate

## CW-12: Escalation → Lessons
**TRIGGER:** Neural bus has ESCALATION_TRIGGERED signal at REDUCE_SCOPE or STOP level
**CHECK:** What broke? What was the root cause?
**ACTION:** Auto-generate lesson: "[DATE] ESCALATION-GENERATED: [level] on [task] — [root cause] → [what to avoid]"
**TRACK:** escalation_to_lesson_fires, lessons_generated
**SOURCE:** Genus OS — escalation as a learning signal, not just a safety valve

---

## TREND TRIGGERS (Integral + Derivative — Cross-Session Patterns)
> These fire on accumulated patterns across sessions, not single-session events.
> Always evaluable regardless of session type (prospect, systems, architecture).
> Source: PID control theory (integral = accumulated drift, derivative = rate of change).

## CW-13: Audit Score Drift (Integral)
**CLASS:** TREND
**TRIGGER:** Average audit score across last 5 sessions has declined by 0.5+ points compared to the 5 sessions before that. Read from brain/system-patterns.md Audit Score Trends table.
**CHECK:** Is the decline in a specific dimension or system-wide?
**ACTION SPECIFIC:** Tighten the relevant gate or rubric for that dimension.
**ACTION SYSTEM-WIDE:** Flag for Oliver: "System-wide quality trending down. [X] → [Y] over 5 sessions. Recommend diagnostic session."
**TRACK:** drift_fires, dimension_targeted
**SOURCE:** PID integral — catches slow drift that no single session triggers

## CW-14: Correction Rate Acceleration (Derivative)
**CLASS:** TREND
**TRIGGER:** Corrections per session increased for 3 consecutive sessions (rate of change is positive and accelerating). Read from brain/metrics/ files.
**CHECK:** Are corrections clustering in one category or spread across many?
**ACTION CLUSTERED:** The category's rules aren't working — flag for rule rewrite, not just new lesson.
**ACTION SPREAD:** System is regressing broadly — flag for Oliver: "Correction rate accelerating. [N1] → [N2] → [N3] over 3 sessions. Something is drifting."
**TRACK:** acceleration_fires, category_flagged
**SOURCE:** PID derivative — catches deterioration before it compounds

## CW-15: Rule Accumulation Check (Integral)
**CLASS:** TREND
**TRIGGER:** Every 5 sessions. Count: active lessons + active CARL rules + active cross-wires. Compare to previous 5-session checkpoint.
**CHECK:** Did the system get more complex (net positive rules) with no measurable quality improvement?
**ACTION YES:** Flag top 3 lowest-value rules for pruning. Rules with zero fires and zero prevented-repeats in 10+ sessions are candidates.
**ACTION NO:** System is growing efficiently. Log and continue.
**TRACK:** accumulation_checks, rules_pruned
**SOURCE:** Argyris double-loop learning — question the rules, not just apply them

## CW-16: Session Type Imbalance (Integral)
**CLASS:** TREND
**TRIGGER:** 5+ consecutive sessions of the same type (all systems, all prospect, all architecture) with no sessions of the other type.
**CHECK:** Is the imbalance intentional (Oliver directed it) or drift?
**ACTION DRIFT:** Surface to Oliver: "[N] consecutive [type] sessions. Pipeline/system work may be accumulating debt. Prospect lessons are untested for [N] sessions."
**ACTION INTENTIONAL:** Log and continue — don't nag about deliberate focus periods.
**TRACK:** imbalance_fires, type_streak
**SOURCE:** Controls variety (Ashby) — the system needs diverse inputs to stay calibrated

---

## DANGER SIGNALS (Contextual Anomaly Triggers)
> Fire on stress indicators regardless of session type or specific cross-wire conditions.
> These catch blind spots that event-based triggers miss entirely.
> Source: Biological immune system danger theory — respond to stress, not just patterns.

## DS-1: Rapid Correction Burst
**CLASS:** DANGER
**TRIGGER:** 3+ corrections from Oliver before the first major task completes this session.
**CHECK:** Are corrections about the current task or about accumulated system issues?
**ACTION CURRENT TASK:** Stop, re-read the relevant gate/CARL rules, restart the task. Something wasn't loaded.
**ACTION SYSTEM ISSUES:** Flag: "Multiple system corrections early in session. Context may not have loaded correctly. Run startup health check."
**TRACK:** burst_fires, root_cause
**NOTE:** This fires MID-SESSION, not at wrap-up. Check after every correction.

## DS-2: Session Duration Anomaly
**CLASS:** DANGER
**TRIGGER:** Session has consumed 2x the average context window usage compared to similar session types. (Estimate: if this session's tool calls exceed 2x the 5-session average for this session type.)
**CHECK:** Is the session legitimately complex or is the agent spinning?
**ACTION SPINNING:** Compact context, re-read loop-state, refocus on the core task. Log what caused the spiral.
**ACTION LEGITIMATE:** Note the complexity and continue — some sessions are genuinely big.
**TRACK:** duration_anomaly_fires, cause

## DS-3: Orphan Signal Detection
**CLASS:** DANGER
**TRIGGER:** At wrap-up, check if any significant session event (correction, tool failure, gate catch, Oliver override) was NOT matched by any cross-wire trigger.
**CHECK:** List all session events. For each, verify at least one CW/DS trigger covers it.
**ACTION ORPHAN FOUND:** Log the orphan signal type. If it recurs across 2+ sessions, propose a new cross-wire to catch it.
**ACTION ALL COVERED:** System has sufficient variety. Log clean.
**TRACK:** orphan_signals_found, new_wires_proposed
**SOURCE:** Ashby's Law of Requisite Variety — the regulator must match the complexity of what it regulates

## DS-4: Score-Correction Mismatch
**CLASS:** DANGER
**TRIGGER:** Session self-scored 8+ but Oliver gave 2+ corrections this session. Or: session self-scored below 7 but Oliver gave zero corrections.
**CHECK:** Is the scoring miscalibrated or was the session genuinely unusual?
**ACTION OVERCONFIDENT (high score, many corrections):** Flag rubric calibration issue. The self-assessment is blind to something Oliver sees. Check which corrections the rubric missed.
**ACTION UNDERCONFIDENT (low score, zero corrections):** The rubric may be too harsh for this session type. Check if systems-only sessions are being scored against prospect rubrics.
**TRACK:** mismatch_fires, direction (over/under)
**SOURCE:** Biological homeostatic plasticity — adjust sensitivity based on actual outcomes

## DS-5: Post-Failure Hardening (Antifragility)
**CLASS:** DANGER
**TRIGGER:** Any ESCALATION_TRIGGERED signal at REDUCE_SCOPE or STOP level, OR any session that fails the 8.0 hard gate on first attempt.
**CHECK:** Identify the 3 components closest to the failure point (use component-map.md neighborhood scan).
**ACTION:**
1. Run a targeted stress test on each of the 3 neighboring components within the same session.
2. For each stress test: does the component handle the failure scenario correctly?
3. If any neighbor fails: create a hardening lesson immediately and tighten that component.
4. Increase chaos test frequency for the failure category from 1/session to 1/task for the next 3 sessions.
**OUTPUT:** `ANTIFRAGILE: [failure] → [3 components tested] → [N/3 passed] → [hardening: Y/N]`
**TRACK:** hardening_fires, neighbors_tested, neighbors_hardened
**SOURCE:** Nassim Taleb (Antifragile) — failure should strengthen the neighborhood, not just log a lesson
