---
name: win-loss
description: Run win/loss analysis when deals close, documenting patterns and feeding notebooks. Use when the user mentions "win loss", "win/loss", "deal closed", "closed won", "closed lost", "lost deal", "we won", "we lost", "deal debrief", "why did we lose", or references a deal that just closed.
---

# Win/Loss Analysis

## Gate
Load and enforce domain/gates/win-loss.md before writing any debrief.

## What This Does
When a deal closes (won or lost), runs a structured debrief: pulls the final transcript, documents the full pattern (persona, pain, close script, objections, cycle length), writes vault notes, updates persona data, and feeds learnings back into NotebookLM so the system gets smarter.

## Inputs
- Deal/prospect name (required)
- Outcome: won or lost (required)

## Steps

### Closed-Won
1. Pull Fireflies transcript for final call
2. Document: persona, pain, threads that landed, close script, cycle length, decision maker, pricing
3. Write vault note in brain/demos/ linked to persona and objection patterns
4. Update persona note with win data
5. Feed winning approach to NotebookLM

### Closed-Lost
1. Document: why no, which objection was not overcome, what to do differently
2. Write vault note with loss reason
3. Update objection notes
4. Log lesson

## Output
Structured debrief note saved to vault, with persona and notebook updates.
