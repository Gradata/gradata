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
