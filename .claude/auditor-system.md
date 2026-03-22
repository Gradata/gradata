# Post-Session Auditor System

## Purpose
After every wrap-up, the primary agent adopts an auditor persona — scores the session, identifies gaps, proposes file changes. Self-improvement loop that doesn't rely on Oliver catching every mistake.

## Trigger
Runs automatically as the final wrap-up step. Cannot be skipped.

## Oliver's Summary (runs BEFORE audit — wrap-up step 0.5)

The very first section written in every session note. This is Oliver's plain-English debrief — no system jargon, no scores, no architecture terminology. Written as if explaining the day to someone who wasn't there and doesn't know how the system works.

**Format (place at top of docs/Session Notes/[YYYY-MM-DD].md, before Self-Assessment):**

```
## OLIVER'S SUMMARY

**What you asked / What I did:**
[One sentence on what Oliver requested. One sentence on what was actually delivered.]

**Where I was confident / Where I was guessing:**
[Be specific. Name the sources that were strong and the gaps. Examples: "LinkedIn had almost nothing on this person so the hook is generic." "I picked the case-study angle but your persona data is thin — it might not land." "CRM data was solid, I'm confident in the deal status."]

**Best work today:**
[One thing done well, and why it was good. Not "I followed the process" — something substantive.]

**Not sure about:**
[One thing that might not be good enough, and why. Be honest. If an email draft felt forced, say so. If a research gate was thin, say so.]
```

**Rules:**
- Under 200 words total. Aim for 120-150.
- No technical terms: no "gates," "CARL," "events.jsonl," "hooks," "PATTERNS.md," "confidence tiers," "Loop," "pre-flight." Describe what happened in plain language.
- Runs on EVERY session — full, standard, compressed, abbreviated. No exceptions. Even a 10-minute session gets a summary.
- Runs BEFORE the audit (step 8). The audit can reference the summary but the summary is written independently of audit scores.
- This is not a self-assessment for the system — it's a report for Oliver. Write it for him, not for the auditor.
- The auditor checks that this section exists in the session note. Missing summary = automatic process violation flag.

**Oliver's Pushback Protocol:**
If Oliver reads the summary and disagrees — says "that's not right" or corrects any claim about confidence, quality, or self-assessment — treat it as an immediate correction. Do NOT wait for wrap-up. The moment Oliver pushes back:
1. Write the lesson to lessons.md immediately with root cause analysis
2. Update the relevant self-assessment in the session note
3. Log a calibration event in audit-log.md

Oliver's disagreement with a self-assessment is the highest quality signal in the entire system. It outweighs audit scores, rubric scores, and every other scoring mechanism. A self-score of 9.0 that Oliver disputes is worth less than a self-score of 7.0 that Oliver confirms as accurate. Calibration is more valuable than confidence. This signal feeds directly into the calibration accumulation system — summary pushbacks count as calibration overrides with the same weight as output-level score corrections.

## Session Weight (Auto-Select)
Determines audit depth based on session output volume. Select the tier that matches, then run that audit format.

| Tier | Trigger | Format | Dimensions | Est. Tokens |
|------|---------|--------|------------|-------------|
| FULL | 5+ major outputs (heavy build or full sales day) | Full ping-pong: 2 rounds, 2 gaps, upgrade proposals | All 5 auditor + all 6 loop | ~3k |
| STANDARD | 2-4 major outputs (mixed session) | Abbreviated ping-pong: score all dimensions, top 2 gaps only, 1 fix max | All 5 auditor + applicable loop | ~1.5k |
| COMPRESSED | 1 major output (focused task) | Score + 1 gap + 1 fix. No ping-pong rounds. | All 5 auditor (loop only if prospect work) | ~500 |
| ABBREVIATED | Systems-only (no prospect outputs) | Score auditor only. Skip loop audit. 1 gap max. | 5 auditor dimensions | ~300 |

**Auto-selection rules:**
- Count major outputs: email drafts, cheat sheets, CRM notes, lead lists, architecture docs, prospect research
- If unsure, round UP (use heavier tier)
- Session 6 was FULL tier (17 SDK improvements + demo prep = 5+ outputs) but was scored as COMPRESSED — that's why gaps were missed
- The 8.0 hard gate applies to ALL tiers. Lighter audit doesn't mean lower bar.

## Self-Assessment Bias
Self-assessment bias exists. Mitigated by Oliver's calibration overrides tracked in audit-log.md. Divergences logged but mechanical separation not enforced.

## Hard Gate: 8.0 Minimum
The combined audit score (auditor-system.md + loop-audit.md) must average 8.0+ to close the session.

### Audit Fix Loop (keep cycling — never log FAIL and stop):
1. Score all dimensions (agent self-score)
2. If below 8.0: identify lowest dimensions
3. Fix them (max 3 file changes per cycle)
4. Re-score with fixes applied
5. If still below 8.0: fix again (cycle 2, max 3 more changes)
6. If still below 8.0 after 2 fix cycles: surface to Oliver with specific asks — "I'm stuck at [X] because [reason]. I need your input on [specific thing]."
7. Oliver rates the session independently: `Score: X/10 — agree? Say "that's a [X]"`
8. Only after combined score (agent + Oliver average) reaches 8.0+ → write loop-state.md and close
9. **MANDATORY: Write audit score to system.db** — every session, after scoring is finalized, insert a row into the `audit_scores` table: `INSERT INTO audit_scores (session, date, research, quality, process, learning, outcomes, auditor_avg, loop_avg, combined_avg, lowest_dim, created_at) VALUES (...)`. This feeds the statusline's Audit indicator. If this step is skipped, the statusline shows stale data.

**NEVER log a session as "FAIL (accepted)" and move on.** That defeats the entire purpose. If the loop can't self-correct, escalate — don't accept failure.

### Oliver's Rating (calibration layer)
Oliver rates the session on a parallel scale. His score captures what the agent score misses:
- Did the agent self-correct, or did Oliver have to intervene?
- Did the system actually improve, or just add more rules?
- Would Oliver trust the agent to run this session unsupervised?

Track: `CALIBRATION: session=[N] | agent=[X] | oliver=[Y] | delta=[diff]`
- Oliver had to fix things the agent should have caught → score drops
- Agent self-corrected without intervention → score holds or rises
- Oliver's rating IS the ground truth. Agent score is the prediction. Delta = how well the agent understands its own quality.

This is non-negotiable. A session that ships below 8 is shipping broken work.

## Unified Scoring Rubric (0-10 each)

**Core dimensions (ALL sessions):**

### 1. Research Depth
Did every output have a completed research gate? Was research actually used in the output or just collected? Were the right sources used (vault, LinkedIn, NotebookLM, Apollo, Fireflies)?

### 2. Output Quality
Was the self-score rubric applied (quality-rubrics.md)? Would a senior AE send this email without editing? Does the cheat sheet contain insight, not just data? Are CRM notes standardized and complete? Is the language human, not AI? Were any outputs below 7/10 presented without revision? For system work: minimal blast radius, no regressions, behavior verified.

### 3. Process Adherence
Were any mandatory gates skipped or abbreviated? Were approval checkpoints followed? Were any CLAUDE.md rules violated? Did the self-check catch issues before presenting to Oliver? Were fallback chains followed when tools failed?

### 4. Learning Capture
Were corrections generalized beyond the specific instance? Were persona/objection patterns updated in the vault? Were lessons written immediately, not deferred? Were PATTERNS.md tables updated? Were quality self-scores logged in daily notes?

### 5. Outcome Linkage
Did the session's actions move pipeline? Are outputs traceable to business outcomes? Were reply/conversion rates checked and updated? Did the weekly pulse run (if Monday)?

**Loop dimensions (PROSPECT-WORK sessions only — skip for systems-only):**

### 6. Pattern Application
Did Claude read PATTERNS.md before drafting? Were insights actually used? Was approach chosen based on data, not default?

### 7. Angle Rotation
Was angle repetition avoided? Was the 70/30 exploration ratio followed? Were failed angles never repeated on the same prospect?

### 8. Confidence Accuracy
Were confidence levels cited correctly? Were [HYPOTHESIS] patterns presented differently from [PROVEN]? Did every recommendation include sample size?

**Scoring:** Core dimensions (1-5) always scored. Loop dimensions (6-8) scored when session includes prospect work. Final score = average of all scored dimensions. **HARD GATE: 8.0+ to close. Single enforcement point — no other file defines a separate gate.**

## Ping-Pong Protocol (2 Rounds)

### Round 1 — AUDITOR scores
Score all dimensions. Identify top 2 gaps (quality over volume).
Format each gap as:
- OBSERVATION: what happened
- IMPACT: why it matters to pipeline or quality
- STANDARD: what enterprise-level looks like

### Round 2 — PRIMARY responds + resolves
For each gap, choose one:
- CONCEDE: "Correct. Root cause is [X]. Proposed fix is [Y]." → Draft exact file change.
- DEFEND: "Context was [X]. This was correct because [Y]." → Gap closed.
- PARTIAL: "Valid on [X]. Not valid on [Y] because [Z]." → Fix the valid part.

Produce UPGRADE PROPOSAL for all conceded/partial gaps:
- FILE: [filename] | CURRENT: [text or NONE] | PROPOSED: [new text] | RATIONALE: [one sentence] | CONFIDENCE: High/Medium/Low

## Change Execution Rules
- **High confidence** → write immediately, log to audit-log.md
- **Medium confidence** → append to .claude/review-queue.md for Oliver to approve
- **Low confidence** → append to lessons.md as [HYPOTHESIS] tag
- **Maximum 3 changes per session. No exceptions.**
- Never change a rule added in the last 7 days without flagging it explicitly
- Never remove or weaken a mandatory gate without escalating to Oliver
- Never touch deal values, pricing logic, or sending permissions

## Cross-Session Pattern Detection (Meta-Learning)
Every 5 sessions, the auditor runs a meta-analysis:

1. **Scan audit-log.md** for all scores across the last 5 sessions
2. **Identify recurring gaps** — same dimension below 7 three or more times = structural issue
3. **Scan lessons.md** for correction patterns — same CATEGORY appearing 3+ times = the rule isn't working
4. **Cross-reference email-tracking.md** — which persona/framework combos are getting replies vs not
5. **Produce META-LEARNING REPORT:** structural issues, ineffective rules, winning patterns, recommended systemic changes
6. Save report to brain/learnings/[date] — Meta-Analysis.md

### Lesson Effectiveness Verification
Every session, scan lessons.md for [TRACK:N/3] entries. If scenario occurred AND lesson prevented mistake: increment hit (Y). If mistake happened anyway: increment hit (N). Update tag through [TRACK:3/3:YYY] = [EFFECTIVE]. After 3 hits with 2+ N: mark [REWRITE NEEDED], surface to Oliver. Lessons with [TRACK:0/3] for 20+ sessions: mark [UNTESTABLE].

### Shadow Mode Protocol
New rules tagged [SHADOW:0/3] run passively. Each relevant scenario: note what output WOULD have been, compare with actual (+/-/=). After 3 occurrences: 2+ positive = PROMOTE to ACTIVE, 2+ negative = KILL, mixed = extend 3 more. Use for calibration-derived rules, contradicting rules, or uncertain-impact experiments.

### Pattern Escalation
- Pattern appears 3x → flag in audit as "recurring"
- Pattern appears 5x → escalate to Oliver with proposed structural fix
- Pattern appears 7x → the rule addressing it is fundamentally broken, needs redesign

## Session Context Feed
Read events.jsonl for session signal history before scoring.

## Quality Self-Assessment in Daily Notes
Every session note MUST include a Self-Assessment section: best output, weakest output, gates skipped, uncertainties, what I'd do differently, self-scores. This feeds cross-session pattern detection.

## Weekly Performance Pulse
Every Monday, generate weekly pulse using .claude/weekly-pulse-template.md. Draft to Oliver's Gmail + save to brain/pipeline/.

## Audit Log Entry Format
Append to .claude/audit-log.md after every audit:
```
---
DATE: [date]
SESSION: [session number]
SCORES: Research [X] | Quality [X] | Process [X] | Learning [X] | Outcomes [X]
AVERAGE: [X]
SELF-SCORES: [list of output self-scores from quality rubrics]
GAPS IDENTIFIED: [list]
CHANGES WRITTEN: [list or NONE]
CHANGES QUEUED: [list or NONE]
META-ANALYSIS DUE: [Yes if session % 5 == 0, else No]
---
```

## Calibration System

### How Oliver Knows When to Override (Score Surfacing)
The agent shows its self-score **inline after every major output**. Format:
> `Score: 7/10 (email draft) — agree? Just say "that's a [X]" to override`

This appears after: email drafts, demo prep docs, CRM notes, cheat sheets, lead filtering results.
- **Oliver agrees:** Silence = agreement. No action needed.
- **Oliver disagrees:** Say "that's a 5" or "more like a 4" — one number is enough.
- **Oliver wants detail:** Say "why 7?" and the agent explains which rubric dimensions scored what.

### Real-Time Override Processing
Override logged immediately: `[CALIBRATION] [date] [output_type]: self=[X], oliver=[Y], delta=[diff]`
Logged to .claude/audit-log.md under CALIBRATION EVENTS section.

### Calibration Accumulation
After 5+ overrides for the SAME output type:
1. Calculate avg_delta = mean of all deltas for that type
2. If avg_delta > +1.5 (consistently overestimates): apply permanent correction factor
3. If avg_delta < -1.5 (consistently underestimates): loosen rubric for that type
4. Log: `[RUBRIC ADJUSTMENT] [output_type]: correction_factor = [value]`
5. Update quality-rubrics.md with the correction factor

### Drift Detection (Automated)
Track rolling 5-session calibration trend:
- 3+ consecutive overrides with delta > +2: CALIBRATION DRIFT alert → auto-tighten ALL rubrics by 1 point
- Oliver overrides 3+ times with delta < -1: REVERSE DRIFT → loosen by 0.5
- Surface drift to Oliver with specifics

### Weekly Calibration Prompt
Monday session: present one random self-scored output for Oliver to rate. Within 1 point = healthy. Delta > 1 = calibration event.

### Anti-Gaming
- Calibration overrides persist across sessions (stored in audit-log.md)
- The agent cannot self-correct a calibration event — only Oliver's scores count
- Correction factors compound: if email drafting has a -2 factor and Oliver adds another -1 override, factor becomes -2.2 (weighted toward recent)
- Maximum correction factor: +/-4. Beyond that, the rubric itself needs redesign, not just adjustment

## Audit Flag SLA
Flags in review-queue.md unreviewed for 3+ sessions trigger a [HOLD] on the affected CLAUDE.md rule. Surface hold at startup. When Oliver resolves, remove hold and log resolution. Prevents silent behavior drift from unreviewed changes.

## Trend Tracking
Query events table for 5-session audit score trend. Flag regressions.
