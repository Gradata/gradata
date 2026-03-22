# Action Waterfall v2.0 — Universal Output Pipeline

Every output flows through 5 layers. No bypass. No routing sublayers.

```
L1: CONTEXT  → Load the right rules for this action type
L2: MEMORY   → Check what we already know (vault, patterns, history)
L3: EXECUTE  → Do the work with full context loaded
L4: QUALITY  → Polish, score, surface weaknesses
L5: VERIFY   → 5-point check, present with proof
```

## Layer 1: CONTEXT (always runs)

| Step | What |
|------|------|
| 1.1 | Identify action type (email, demo-prep, crm-note, call-script, lead-filter, system-work, strategy) |
| 1.2 | Load CARL rules by priority (CRITICAL always, HIGH at startup, NORMAL if triggered) |
| 1.3 | Scan lessons.md for applicable [INSTINCT] and [PATTERN] entries |
| 1.4 | Check if action is part of a running experiment |

Output: "Context loaded: [type] | [X] rules | [Y] lessons | Experiment: [name/none]"

## Layer 2: MEMORY (runs for prospect/research/strategy work)

| Step | What | Applies To |
|------|------|-----------|
| 2.1 | Vault check: brain/prospects/[Name].md | Prospect work |
| 2.2 | Persona MOC: brain/personas/[type].md | Prospect work |
| 2.3 | PATTERNS.md: angles/tones working or failing | Any drafting |
| 2.4 | NotebookLM: query relevant notebook | ALL research (mandatory) |
| 2.5 | Gmail history: prior threads | Email drafting |
| 2.6 | Lessons archive: search graduated lessons | ALL actions |
| 2.7 | **Simulate** (prospect/strategy only): evaluate approach options against PATTERNS.md, pick best, show one line to Oliver | Prospect-facing |

Output: "Memory loaded: vault [Y/N] | patterns [insight] | NLM [result] | approach: [chosen]"

## Layer 3: EXECUTE (always runs)

Do the work with all context and memory loaded.

**Checkpoint protocol (STANDARD and DEEP tasks):** After each major subtask: (1) what changed and why, (2) unexpected findings, (3) confirm alignment or flag replan needed. If blocked, STOP — replan before continuing.

## Layer 4: QUALITY (always runs)

| Step | What | Applies To |
|------|------|-----------|
| 4.1 | Writing rules check (banned words, tone, length, format, signature) | Text output |
| 4.2 | Humanizer pass | Email, follow-up, LinkedIn |
| 4.3 | Lesson compliance: any applicable lesson violated? | ALL |
| 4.4 | Self-score against quality-rubrics.md | ALL major outputs |
| 4.5 | **Brutal honesty**: what's weak? what's risky? what am I unsure about? should we even be doing this? | ALL |

Output: "Quality: humanizer [PASS] | lessons [X/Y] | self-score [X/10] | weakness: [stated]"

## Layer 5: VERIFY (always runs)

| Step | Check | Question |
|------|-------|----------|
| 5.1 | INPUT | Did I have the right inputs? Show pre-flight proof. |
| 5.2 | GOAL | Does this deliver what was asked for? |
| 5.3 | ADVERSARIAL | Would the prospect/user reject this? |
| 5.4 | VOICE | Does it sound human? |
| 5.5 | SCORE | Good enough to ship? Block <7. State gap to 9. |

Output:
```
INPUT: [PASS/FAIL] — [proof]
GOAL: [PASS/PARTIAL/FAIL]
ADVERSARIAL: [HANDLED/REVISED]
VOICE: [PASS]
Score: X/10 (type) — [gap to 9] — agree?
```

GOAL = FAIL → stop and realign before polishing.
