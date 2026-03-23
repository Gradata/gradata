---
name: gates
description: Run the universal gate execution protocol — research, checkpoint, verify, present. Use when the user mentions "run the gate", "gate check", "gate protocol", "verification stack", "pre-flight check", "5-point verification", or references the gate system, quality gates, or mandatory checks.
---

# Gate Execution Protocol

## Source
Load .claude/gates.md for the universal gate framework. Load domain-specific gates from domain/gates/ based on task type.

## What This Does
Orchestrates the universal gate execution sequence that all domain gates inherit: research checklist, reasoning block, checkpoint, user approval, execution, 5-Point Verification Stack, and presentation with proof block. This is the meta-skill that enforces quality on every prospect-facing output.

## Gate Routing
| Task | Gate File |
|------|-----------|
| Email drafts (cold, inbound, follow-up) | domain/gates/pre-draft.md |
| Demo preparation | domain/gates/demo-prep.md |
| Post-demo follow-up | domain/gates/post-demo.md |
| Cold call scripts | domain/gates/cold-call.md |
| LinkedIn messages | domain/gates/linkedin.md |
| CRM/Pipedrive notes | domain/gates/pipedrive-note.md |
| Win/loss analysis | domain/gates/win-loss.md |

## 5-Point Verification Stack
1. INPUT — Did I have the right inputs? Show pre-flight proof block.
2. GOAL — Does this deliver what was specifically asked for?
3. ADVERSARIAL — Would the prospect reject this? Self-play objection check.
4. VOICE — Does it sound human? Humanizer pass.
5. SCORE — Self-score via quality-rubrics.md. Block if <7.

## Output
Verification line appended to every gated output. Event emitted via events.py on completion.
