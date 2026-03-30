# Post-Session Auditor System v2.0

## Purpose
Objective session gate that blocks wrap-up close if quality checks fail. Replaces subjective 0-10 scoring with binary pass/fail checks computed from files and events. Zero self-assessment in the gate.

## Trigger
Runs automatically as the final wrap-up step via `wrap_up_validator.py`. Cannot be skipped.

## Oliver's Summary (runs BEFORE gate — wrap-up step 0.5)

The very first section written in every session note. Plain-English debrief — no system jargon.

**Format (place at top of docs/Session Notes/[YYYY-MM-DD]-S[N].md):**

```
## OLIVER'S SUMMARY

**What you asked / What I did:**
[One sentence on what Oliver requested. One sentence on what was actually delivered.]

**Where I was confident / Where I was guessing:**
[Be specific. Name the sources that were strong and the gaps.]

**Best work today:**
[One thing done well, and why it was good.]

**Not sure about:**
[One thing that might not be good enough, and why.]
```

**Rules:**
- Under 200 words total. Aim for 120-150.
- No technical terms: no "gates," "CARL," "events.jsonl," "hooks," "PATTERNS.md," "confidence tiers," "Loop," "pre-flight."
- Runs on EVERY session. No exceptions. Even a 10-minute session gets a summary.
- This is a report for Oliver, not a self-assessment for the system.

**Oliver's Pushback Protocol:**
If Oliver disagrees with the summary — treat it as an immediate correction:
1. Write the lesson to lessons.md immediately with root cause analysis
2. Update the relevant section in the session note
3. Emit a CALIBRATION event: `emit("CALIBRATION", "pushback", {"output_type": "summary", "delta": N})`

Oliver's disagreement is the highest quality signal in the system. It outweighs every other metric.

## Session Close Gate (Binary Checklist)

15 checks. 80% pass threshold. Computed by `wrap_up_validator.py`. Zero self-assessment.

Run: `python brain/scripts/wrap_up_validator.py --session N --date YYYY-MM-DD --session-type [full|systems]`

### Core Checks (all sessions):
1. Session note exists at `docs/Session Notes/[YYYY-MM-DD]-S[N].md`
2. Oliver's Summary section present and non-empty
3. All triggered gates completed (zero FAIL in GATE_RESULT events)
4. Zero hallucination flags (zero HALLUCINATION events)
5. All corrections logged as lessons (corrections > 0 implies new lessons > 0)
6. Startup brief updated (handoff references current session)
7. Loop-state updated (header references current session)
8. Brain git committed (latest commit mentions session or date)
9. First-draft acceptance >= 70% (outputs unedited / outputs produced)
10. Correction density < 0.20 (corrections / outputs)
11. VERSION.md updated

### Prospect-Work Checks (skip for systems-only):
12. All prospect outputs delta-tagged in activity_log
13. Events emitted for all wrap-up steps (3+ STEP_COMPLETE events)
14. No stale data presented (zero STALE_DATA events)
15. Confidence calibration holds (no Oliver overrides > 2 points)

### Supplementary (always run):
- Agent distillation files exist
- Lessons integrity (no stale formats)
- Deferred items captured in handoff

### Pass/Fail:
- **Full session:** 80% of scored checks must pass
- **Systems-only:** Checks 12-15 skipped, threshold still 80% of remaining
- **BLOCKED** if below threshold. Fix and re-run validator.
- No subjective fix loops. Either the check passes or it doesn't.

### Oliver's Override:
Oliver can bypass the gate with "ship it" if failures are cosmetic.
Override logged as event: `emit("GATE_OVERRIDE", "oliver", {"reason": "..."})`

## Per-Session Leading Indicators (computed, not gated)

These are computed from events.jsonl at wrap-up and stored in `session_metrics` table.
They are trend data, NOT gates. The binary checks above are the gate.

1. **First-draft acceptance rate:** outputs_unedited / outputs_produced
2. **Correction density:** corrections / outputs
3. **Source coverage:** gates with full sources / total gates
4. **Confidence calibration:** overrides within 2 points / total overrides

Displayed in wrap-up summary. Trend tracked across sessions in system.db.
Format in wrap-up output:
```
Gate: 13/14 checks (93%) — PASS
Indicators: acceptance=85% | corrections=0.10 | calibration=100%
```

## Calibration System (Per-Output)

Per-output self-scores (7+ floor from quality-rubrics.md) still use the /10 scale. The session gate is binary, but output quality scoring remains continuous.

### Inline Score Surfacing
After every major output:
> `Score: 7/10 (email draft) — agree? Just say "that's a [X]" to override`

### Override Processing
Override logged immediately as CALIBRATION event:
`emit("CALIBRATION", "oliver", {"output_type": "email", "self_score": 7, "oliver_score": 5, "delta": -2})`

### Calibration Accumulation
After 5+ overrides for the SAME output type:
1. Calculate avg_delta
2. If avg_delta > +1.5: apply permanent correction factor to rubric
3. If avg_delta < -1.5: loosen rubric for that type
4. Log: `[RUBRIC ADJUSTMENT] [output_type]: correction_factor = [value]`

### Anti-Gaming
- Correction factors persist across sessions (stored in events.jsonl)
- Maximum correction factor: +/-4. Beyond that, rubric needs redesign.
- Agent cannot self-correct calibration events — only Oliver's scores count.

## Change Execution Rules
- **High confidence** → write immediately
- **Medium confidence** → append to .claude/review-queue.md
- **Low confidence** → append to lessons.md as [INSTINCT:0.30]
- Maximum 3 changes per session
- Never change a rule added in the last 7 days without flagging
- Never remove a mandatory gate without escalating to Oliver

## Audit Log Entry Format
Append to .claude/audit-log.md after every session:
```
SESSION [N] | [date] | [type] | GATE: [X]/[Y] ([Z]%) [PASS/FAIL]
Failed: [list or none] | Indicators: acceptance=[X]% correction=[Y]% calibration=[Z]%
```

## Audit Flag SLA
Flags in review-queue.md unreviewed for 3+ sessions trigger a [HOLD] on the affected rule. Surface at startup. Prevents silent behavior drift.
