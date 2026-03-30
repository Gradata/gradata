# Mandatory Gates — Gradata Gate Protocol
# Gate content lives in domain/gates/. This file defines the universal gate execution framework.

## Gate Execution Protocol

Every gate follows this sequence:
1. **Research** — complete all checklist steps
2. **Reasoning block** — 3-5 sentences explaining your thinking before checkpoint
3. **Checkpoint** — present findings to user BEFORE drafting
4. **User approval** — user approves the approach
5. **Execute** — draft/build the output
6. **5-Point Verification** — run the verification stack (see below)
7. **Present** — show output with pre-flight proof block + verification line

### 5-Point Verification Stack

After executing, every output passes through 5 checks. Each asks a different question. No overlap.

| # | Check | Question | Applies to |
|---|-------|----------|-----------|
| 1 | **INPUT** | Did I have the right inputs? Show the pre-flight proof block. | All gated outputs |
| 2 | **GOAL** | Does this deliver what was specifically asked for? Not "is it good" — "is it right?" | All outputs |
| 3 | **ADVERSARIAL** | Would the prospect/user reject this? Self-play objection check. | Prospect-facing outputs |
| 4 | **VOICE** | Does it sound human? Humanizer pass. | Emails, LinkedIn, call scripts |
| 5 | **SCORE** | Is this good enough to ship? Self-score (quality-rubrics.md). If score identifies a fixable problem, fix it before presenting. State what a 9/10 would look like. Block if <7. | All major outputs |

**Format — show inline after every major output:**
```
INPUT: [PASS] vault read, PATTERNS checked, NLM queried
GOAL: [PASS/PARTIAL/FAIL] asked=[what Oliver requested], delivered=[what was built]
ADVERSARIAL: [HANDLED/REVISED] "[specific objection]"
VOICE: [PASS] humanizer clean
Score: X/10 (type) — [what a 9 would look like] — agree?
```

If GOAL = FAIL → stop and realign before polishing. Don't humanize the wrong output.
If GOAL = PARTIAL → state what's missing and why. Oliver decides if it ships.

**What this replaced (Session 21 consolidation):**
- Merged: self-score + fix-before-score + metacognitive honesty + blocking gate → single SCORE step
- Killed: Layer 5 verify (duplicate of INPUT) and separate gate checklist verification
- Added: GOAL check (the question no previous step asked)

### Pre-Flight Proof Block (MUST appear above every prospect-facing output):
```
CONFIDENCE: [HIGH / MEDIUM / LOW]
PRE-FLIGHT: [prospect name]
[x] Vault: brain/prospects/[file] — [read/created]
[x] PATTERNS.md: read — [best angle: X | avoid: Y | confidence level]
[x] NotebookLM: queried — [case study/proof point found]
[x] Lessons archive: searched [categories] — [hits or none]
[x] Persona MOC: [type] — [what works for this persona]
```
If any shows [ ] instead of [x], STOP and complete before presenting.

### Post-Draft Tag Block (add to prospect note after approval):
```
## Touch [N] — [date]
- type: [cold|warm|follow-up|re-engage|post-demo|proposal|breakup]
- channel: [email|call|linkedin|demo|meeting|proposal]
- intent: [book-call|get-reply|nurture|close|discover]
- tone: [direct|casual|consultative|curious|empathetic]
- angle: [from closed set in PATTERNS.md]
- framework: [CCQ|Gap|SPIN|JOLT|Challenger]
- subject: [subject line]
- outcome: pending
- next_touch: [date]
- patterns_applied: [what from PATTERNS.md informed this draft]
```

### Self-Play Objection Check (MANDATORY):
After drafting, generate the prospect's most likely SPECIFIC objection based on the research. If vulnerable, revise before presenting.
Format: `OBJECTION CHECK: "[specific objection]" — [HANDLED in draft / REVISED to address]`

## Event Emission (after every gate)
After any gate completes, emit via events.py:
`emit("GATE_RESULT", "gate:[name]", {"result": "PASS/FAIL", "prospect": "[name]", "confidence": "HIGH/MEDIUM/LOW"})`

## System Integration Gate (MANDATORY for every system addition)

Fires when: adding any new component, script, rule, hook, signal, tool, or pattern to the system.

| Step | Check | Pass criteria |
|------|-------|---------------|
| 0 | **Purpose statement** | State in 2-3 sentences: (1) what this component does in plain English, (2) why the system needs it, (3) how the system behaves differently with it. If you can't articulate the "why," stop and ask Oliver. |
| 1 | Check events.py integration | Does this component emit or consume events? If yes, which types? |
| 2 | Check hook integration | Does this need a hook for enforcement? If so, which hook point? |
| 3 | Define event connection | Addition emits OR consumes at least ONE event type via events.py. No orphans. |
| 4 | Update `.claude/component-map.md` | Addition listed with correct layer, file path, and event connections |

**HARD GATE: If step 3 fails (no event connection), the addition does not ship.** Ask Oliver: "This doesn't wire into the event system — should I rethink the approach or skip it?"

## Domain Gates
Gate content is domain-specific. Domain gates inherit this protocol — they define task-specific research checklists but do NOT redefine the universal steps (tag block, objection check, humanizer, self-score). Those always come from this file.
Load the relevant gate file when the task triggers:
- Pre-Draft Research: domain/gates/pre-draft.md
- Demo Prep: domain/gates/demo-prep.md
- Post-Demo Follow-Up: domain/gates/post-demo.md
- Cold Call Script: domain/gates/cold-call.md
- LinkedIn Message: domain/gates/linkedin.md
- CRM Note Quality: domain/gates/pipedrive-note.md
- Win/Loss Analysis: domain/gates/win-loss.md
