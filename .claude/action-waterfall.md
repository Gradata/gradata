# Action Waterfall — Universal Pipeline for ALL Outputs

> Every action flows through 5 layers. Each layer enriches the next.
> This isn't just for prospect work — it covers EVERY output the agent produces.
> Think of it like a data enrichment pipeline: raw intent → context → memory → quality → verified output.

## The 5 Layers

```
LAYER 1: CONTEXT    → What are we doing? Load the right rules.
    ↓
LAYER 2: MEMORY     → What do we already know? Check institutional memory.
    ↓
LAYER 3: EXECUTE    → Do the work with full context loaded.
    ↓
LAYER 4: QUALITY    → Is this good enough? Polish and score.
    ↓
LAYER 5: VERIFY     → 5-point check: INPUT → GOAL → ADVERSARIAL → VOICE → SCORE. Present.
```

## Layer 1: CONTEXT (always runs)

**Purpose:** Identify the action type, load the right rules and lessons.

| Step | What | How |
|------|------|-----|
| 1.1 | Identify action type | email, demo-prep, crm-note, call-script, lead-filter, system-work, strategy, analysis |
| 1.2 | Load CARL rules by priority | CRITICAL always loaded. HIGH loaded at session start. NORMAL loaded if action type triggers recall keywords. |
| 1.3 | Scan lessons.md | Match action type to lesson categories. Pull applicable [CONFIRMED] and [PROVISIONAL] lessons. |
| 1.4 | Check experiments | Is this action part of a running experiment? If yes, which variant? |

**Output:** "Context loaded: [action type] | [X] CARL rules active | [Y] lessons applicable | Experiment: [name/none]"

## Layer 2: MEMORY (runs for prospect/research/strategy work)

**Purpose:** Check what we already know before doing new work.

| Step | What | Applies To |
|------|------|-----------|
| 2.1 | Vault check | brain/prospects/[Name].md — read if exists, create from template if not | Prospect work |
| 2.2 | Persona MOC | brain/personas/[type].md — what works for this persona? | Prospect work |
| 2.3 | Knowledge graph | `query-playbook [persona]` — ranked angles, objections, frameworks | Prospect work |
| 2.4 | PATTERNS.md | What angles/tones are working? What's failing? Confidence levels? | Any drafting |
| 2.5 | NotebookLM (tier system: .claude/skills/notebooklm/SKILL.md) | Query relevant notebook for case studies, proof points, objection counters, domain knowledge | **ALL research flows** — prospect, competitor, architecture, domain. MANDATORY. Never skip, never require a reminder. |
| 2.6 | Gmail history | Prior threads with this person? Last email sent? | Email drafting |
| 2.7 | Lessons archive | Search graduated lessons for this category | ALL actions |

**Output:** "Memory loaded: vault [Y/N] | persona [Y/N] | KG [insight] | patterns [insight] | NLM [case study] | gmail [thread status]"

For non-prospect work (system changes, lead filtering, strategy): 2.4, 2.5, and 2.7 apply. NotebookLM is mandatory for ALL research regardless of type.

## Layer 2.5: SIMULATE (runs for prospect/strategy work — skip for SIMPLE tasks)

**Purpose:** Predict outcomes before committing. Generate candidates, score against historical data, select the best path. Log the prediction for calibration.

> Source: Friston (Free Energy Principle), LeCun (World Models), DeepMind (MuZero). The system should minimize surprise by predicting before acting.

| Step | What | How |
|------|------|-----|
| 2.5.1 | Evaluate approaches | Consider angle/framework/tone options based on Layer 2 memory |
| 2.5.2 | Score against history | Check PATTERNS.md reply rates for angle+persona combo. Check persona MOC. Check lessons for known failures. Check decision journal for past decisions with this persona/stage. |
| 2.5.3 | Pick the best | Select highest predicted effectiveness. If past decision exists for similar situation, factor in whether it worked. |
| 2.5.4 | Log choice | One line shown to Oliver: `Approach: [framework] + [angle] — [why] (past: [result if any])` |

**Output (shown to Oliver):** One line explaining the choice. e.g., "Approach: Gap Selling + direct angle — 8.8% reply rate for agency owners. Last time this converted with Hassan."
**Oliver has final say.** If he redirects, log the override and use his choice.
**Do NOT show 3 candidates.** Pick the best, explain it, let Oliver override.

**Calibration:** At wrap-up, compare prediction to actual outcome. Prediction error feeds CW-5 (rubric drift) and self-model reliability scores.

**Skip condition:** SIMPLE tasks (Layer 1.1 classification) and system work bypass simulation — no forward model needed for deterministic operations.

## Layer 2.7: ROUTE (System 1 / System 2 — always runs)

**Purpose:** Decide execution track based on task complexity and proven reliability.

> Source: Kahneman (Thinking, Fast and Slow). Not everything needs the full pipeline.

| Condition | Track | What happens |
|-----------|-------|-------------|
| Self-model reliability > 0.9 AND task is SIMPLE AND no [PROVISIONAL] lessons in this category | **FAST (System 1)** | Skip Layer 2.5, compress Layer 4 to 4.3+4.4 only, compress Layer 5 to 5.2+5.5 only. One-line verification. |
| All other cases | **DELIBERATE (System 2)** | Full waterfall as defined. All layers, all steps. |

**Safeguard:** If a fast-track output gets corrected by Oliver, that task type loses fast-track eligibility for 5 sessions. Log the demotion.

**Output (shown to Oliver — one line only):** `Confidence: [task type] [X] [FAST/DELIBERATE] — [reason if HIGH-RISK]`
e.g., "Confidence: demo prep 0.62 (HIGH-RISK) — loading extra rules" or "Confidence: CRM note 0.92 — fast track"
Do NOT show the full self-model table. One line. Oliver sees the signal, not the machinery.

## Layer 3: EXECUTE (always runs)

**Purpose:** Do the actual work with all context and memory loaded.

This is where the email gets drafted, the demo prep gets built, the CRM note gets written, the lead list gets filtered, the system change gets made.

Rules from Layer 1 are active. Memory from Layer 2 informs decisions. Simulation from 2.5 selected the approach. Lessons from 1.3 prevent known mistakes.

## Layer 4: QUALITY (always runs)

**Purpose:** Polish the output before presenting.

| Step | What | Applies To |
|------|------|-----------|
| 4.1 | Writing rules check | Banned words, tone, length, format, signature | Any text output |
| 4.2 | Humanizer pass | /humanizer to strip AI patterns | Email, follow-up, LinkedIn |
| 4.3 | Lesson compliance | Did any applicable lesson get violated? | ALL actions |
| 4.4 | Self-score | Rate against quality-rubrics.md with correction factors | ALL major outputs |
| 4.5 | Competitive draft | Generate version B if follow-up email | Follow-up emails |
| 4.6 | Experiment tagging | Tag with experiment name/variant if part of running experiment | Experiment touches |

**Output:** "Quality: humanizer [PASS] | lessons [X/Y compliant] | self-score [X/10]"

## Layer 4.5: BRUTAL HONESTY (always runs)

**Purpose:** Before presenting, ask: what's wrong with this? What am I not saying?

| Step | What |
|------|------|
| 4.5.1 | **What's weak?** Identify the weakest part of this output and say it. Don't wait for Oliver to find it. |
| 4.5.2 | **What's the risk?** If this output has a downside, flag it. "This angle might backfire because..." |
| 4.5.3 | **What am I unsure about?** If any part is a guess or assumption, label it explicitly. |
| 4.5.4 | **Should we even be doing this?** If the task itself seems wrong (wrong priority, wrong timing, over-engineering), say so before executing. |

This is not optional politeness. This is the difference between an assistant that agrees with everything and a partner that tells you what you need to hear. Oliver has asked for this explicitly. Silence on concerns = failure.

## Layer 5: VERIFY (always runs)

**Purpose:** 5-point verification. Each step asks a different question. No overlap. See .claude/gates.md for full spec.

| Step | Check | Question | Applies To |
|------|-------|----------|-----------|
| 5.1 | **INPUT** | Did I have the right inputs? Show pre-flight proof block. | All gated outputs |
| 5.2 | **GOAL** | Does this deliver what was specifically asked for? | ALL outputs |
| 5.3 | **ADVERSARIAL** | Would the prospect/user reject this? | Prospect-facing |
| 5.4 | **VOICE** | Does it sound human? Humanizer pass. | Emails, LinkedIn, calls |
| 5.5 | **SCORE** | Good enough to ship? Score, fix if broken, state gap, block <7. | ALL major outputs |
| 5.6 | Canonical log | Log the action to system.db with full context | ALL actions |
| 5.7 | Chaos test | Once per session, silently test one rule | Random (silent) |

**Output:** Final output with inline verification block:
```
INPUT: [PASS/FAIL] — [proof summary]
GOAL: [PASS/PARTIAL/FAIL] — asked=[X], delivered=[Y]
ADVERSARIAL: [HANDLED/REVISED] — "[objection]"
VOICE: [PASS] — humanizer clean
Score: X/10 (type) — [gap to 9] — agree?
```

**GOAL = FAIL → stop and realign before polishing.** Don't humanize the wrong output.

## Which Layers Apply to Which Action Type

| Action Type | L1 Context | L2 Memory | L2.5 Simulate | L2.7 Route | L3 Execute | L4 Quality | L5 Verify |
|------------|-----------|-----------|-------------|-----------|-----------|-----------|----------|
| Email draft | FULL | FULL | YES (angle+tone) | DELIBERATE | YES | FULL + humanizer | Pre-flight + score |
| Demo prep | FULL | FULL | YES (framework) | DELIBERATE | YES | FULL | Pre-flight + score |
| CRM note | FULL | 2.1, 2.7 | SKIP | FAST eligible | YES | 4.3, 4.4 | 5.2, 5.5 |
| Call script | FULL | FULL | YES (opening) | DELIBERATE | YES | FULL + humanizer | Pre-flight + score |
| Lead filtering | FULL | 2.4, 2.7 | SKIP | FAST eligible | YES | 4.3, 4.4 | 5.2, 5.5 |
| System work | 1.2, 1.3 | 2.7 | SKIP | FAST eligible | YES | 4.3 | 5.2, 5.5 |
| Strategy/analysis | FULL | 2.4, 2.5, 2.7 | YES (approach) | DELIBERATE | YES | 4.3, 4.4 | 5.2, 5.3, 5.5 |
| Follow-up | FULL | FULL | YES (angle+tone) | DELIBERATE | YES | FULL + humanizer + competitive | Pre-flight + score |

## Why Waterfall > Flat Rules

**Before (flat):** 64 CARL rules sit in a file. Some fire, some don't. No guarantee the right ones load for this action. Lessons checked if agent remembers. Memory used if agent remembers. Quality checked if agent remembers.

**After (waterfall):** Every action type has a defined pipeline. Rules load automatically based on type. Memory checks are mandatory steps, not optional afterthoughts. Quality runs as a layer, not a hope. Verification proves it happened.

The waterfall ensures nothing gets skipped because each layer is a required stage, not a rule to remember.
