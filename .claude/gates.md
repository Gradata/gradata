# Mandatory Gates — AIOS Gate Protocol
# Gate content lives in domain/gates/. This file defines the universal gate execution framework.

## Gate Execution Protocol

Every gate follows this sequence:
1. **Research** — complete all checklist steps
2. **Reasoning block** — 3-5 sentences explaining your thinking before checkpoint
3. **Checkpoint** — present findings to user BEFORE drafting
4. **User approval** — user approves the approach
5. **Execute** — draft/build the output
6. **Self-play objection check** — predict the most likely specific pushback, revise if vulnerable
7. **Quality pass** — humanizer + self-score against quality-rubrics.md
8. **Present** — show output with pre-flight proof block

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

## Neural Bus Signal (write after every gate)
After any gate completes, write one line to brain/sessions/neural-bus.md:
`[HH:MM] [gate:gate-name] [PASSED/FAILED] prospect=[name] confidence=[HIGH/MEDIUM/LOW]`

## System Integration Gate (MANDATORY for every system addition)

Fires when: adding any new component, script, rule, cross-wire, signal, tool, or pattern to the system.

| Step | Check | Pass criteria |
|------|-------|---------------|
| 1 | Read `brain/sessions/neural-bus.md` signal taxonomy | Identified which signals the addition writes or reads |
| 2 | Read `.claude/cross-wire-checklist.md` | Identified which cross-wire(s) the addition feeds or consumes |
| 3 | Define bus connection | Addition has at least ONE signal it emits OR consumes. No orphans. |
| 4 | Update signal taxonomy | New signal type added to neural-bus.md if needed |
| 5 | Update or add cross-wire | New CW added or existing CW updated to include the addition |
| 6 | Update `.claude/component-map.md` | Addition listed with correct layer, file path, and bus connections |

**HARD GATE: If step 3 fails (no bus connection), the addition does not ship.** Ask Oliver: "This doesn't wire into the nervous system — should I rethink the approach or skip it?"

**Neural Bus Signal:**
`[HH:MM] [gate:integration] [PASSED/FAILED] component=[name] signals=[list] cross-wires=[list]`

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
