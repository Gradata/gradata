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
LAYER 5: VERIFY     → Did we follow process? Show proof. Present.
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
| 2.5 | NotebookLM (tier system: .claude/skills/notebooklm/SKILL.md) | Query relevant notebook for case studies, proof points, objection counters | Prospect + demo + strategy |
| 2.6 | Gmail history | Prior threads with this person? Last email sent? | Email drafting |
| 2.7 | Lessons archive | Search graduated lessons for this category | ALL actions |

**Output:** "Memory loaded: vault [Y/N] | persona [Y/N] | KG [insight] | patterns [insight] | NLM [case study] | gmail [thread status]"

For non-prospect work (system changes, lead filtering, strategy), only 2.4 and 2.7 apply.

## Layer 3: EXECUTE (always runs)

**Purpose:** Do the actual work with all context and memory loaded.

This is where the email gets drafted, the demo prep gets built, the CRM note gets written, the lead list gets filtered, the system change gets made.

Rules from Layer 1 are active. Memory from Layer 2 informs decisions. Lessons from 1.3 prevent known mistakes.

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

**Purpose:** Prove process was followed. Present with proof.

| Step | What | Applies To |
|------|------|-----------|
| 5.1 | Pre-flight block | Show the verification checklist above prospect output | Prospect work |
| 5.2 | Truth protocol | Every claim backed by evidence? Sources cited? | ALL outputs |
| 5.3 | Score surfacing | "Score: X/10 (type) — agree? Say 'that's a [X]' to override" | ALL major outputs |
| 5.4 | Canonical log | Log the action to system.db with full context | ALL actions |
| 5.5 | Chaos test | Once per session, silently test one rule | Random (silent) |

**Output:** The final output presented to Oliver, with pre-flight block (if prospect) and score surfacing.

## Which Layers Apply to Which Action Type

| Action Type | L1 Context | L2 Memory | L3 Execute | L4 Quality | L5 Verify |
|------------|-----------|-----------|-----------|-----------|----------|
| Email draft | FULL | FULL (all 7 steps) | YES | FULL + humanizer | Pre-flight + score |
| Demo prep | FULL | FULL | YES | FULL | Pre-flight + score |
| CRM note | FULL | 2.1, 2.7 | YES | 4.3, 4.4 | 5.2, 5.4 |
| Call script | FULL | FULL | YES | FULL + humanizer | Pre-flight + score |
| Lead filtering | FULL | 2.4, 2.7 | YES | 4.3, 4.4 | 5.2, 5.4 |
| System work | 1.2, 1.3 | 2.7 | YES | 4.3 | 5.2, 5.4 |
| Strategy/analysis | FULL | 2.4, 2.5, 2.7 | YES | 4.3, 4.4 | 5.2, 5.3, 5.4 |
| Follow-up | FULL | FULL | YES | FULL + humanizer + competitive | Pre-flight + score |

## Why Waterfall > Flat Rules

**Before (flat):** 64 CARL rules sit in a file. Some fire, some don't. No guarantee the right ones load for this action. Lessons checked if agent remembers. Memory used if agent remembers. Quality checked if agent remembers.

**After (waterfall):** Every action type has a defined pipeline. Rules load automatically based on type. Memory checks are mandatory steps, not optional afterthoughts. Quality runs as a layer, not a hope. Verification proves it happened.

The waterfall ensures nothing gets skipped because each layer is a required stage, not a rule to remember.
