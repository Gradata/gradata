Your benchmark is the operational standard of the world's leading AI labs -- OpenAI, Anthropic, Google DeepMind, Perplexity, DeepSeek, xAI, and Microsoft Copilot. When evaluating outputs, ask: would this meet the bar of an agent shipped by one of these teams? When evaluating the learning system, ask: does this compound the way their best models improve? When evaluating process adherence, ask: would this pass a code review at a team that ships AI infrastructure at scale? You are not grading on a curve for a solo operator. You are holding this agent to the standard of professional AI deployment.

# Output Quality Rubrics
# Self-score every output before presenting to Oliver. If below 7, revise before showing.

## Email Draft (Cold / Inbound / Follow-Up)

| Score | Criteria |
|-------|----------|
| 9-10 | Personal hook from real research. Pain is specific to THEIR situation. Solution ties directly to pain with case study. CTA is low friction. Under 150 words. Each sentence breathes. Sounds like Oliver wrote it. Framework applied correctly. Would get a reply. |
| 7-8 | Hook is personal but generic-adjacent. Pain is real but could apply to 5 similar companies. Case study included. CTA works. Language is clean. Might get a reply. |
| 5-6 | Hook is templated. Pain is industry-level, not company-level. Case study feels forced. Some AI language slipped in. Oliver would edit 2-3 lines before sending. |
| 3-4 | No personal hook. Pain is generic. Reads like a template with [COMPANY] swapped in. Multiple AI phrases. Oliver would rewrite most of it. |
| 1-2 | Facts wrong. Condescending tone. Resume recitation. Would damage the brand if sent. |

## Demo Cheat Sheet

| Score | Criteria |
|-------|----------|
| 9-10 | Story-trap structure flows naturally. Each TRAP has specific questions from research. Listen-for cues reference things they've actually said (from Fireflies/Apollo). Thread links correct. Objection table has responses tested on similar personas. Close script matches their specific situation. Oliver could run the demo from this alone. |
| 7-8 | Structure is right. TRAPs exist but questions are slightly generic. Objection responses are solid but not persona-specific. Oliver would add 1-2 personal touches. |
| 5-6 | Discovery separate from threads (wrong structure). Questions are generic. Missing Fireflies data. Oliver would restructure before using. |
| 3-4 | Data dump, not a playbook. No story flow. Missing thread links. Oliver can't use this in a demo. |

## CRM Note (Pipedrive)

| Score | Criteria |
|-------|----------|
| 9-10 | Correct template used. All fields populated from verified sources. No "Not confirmed." No AI attribution. No .md citations. HTML formatted. Contact info complete. Actionable next steps with dates and owners. |
| 7-8 | Template correct. Most fields populated. 1-2 fields legitimately unknown (flagged, not "pending"). Sources listed correctly. |
| 5-6 | Template mostly followed. Some fields have "pending" or "enrichment needed." Sources include .md files. Missing next steps. |
| 3-4 | Wrong template. Multiple "Not confirmed" fields. AI attribution present. Published incomplete. |

## ICP Prospect List

| Score | Criteria |
|-------|----------|
| 9-10 | Every contact matches ICP criteria. Pain points and buy signals specific per contact. No duplicates with existing pipeline. CSV format ready for import. Persona type identified. |
| 7-8 | ICP match is strong. Pain points are industry-level, not contact-level. Format is clean. |
| 5-6 | Some contacts are borderline ICP. Pain points are generic. Some may overlap with existing pipeline. |
| 3-4 | Contacts don't match ICP. No pain points listed. Duplicates with pipeline. |

## System / Architecture Work

Benchmark: Would this pass review at a team shipping AI infrastructure at OpenAI, Anthropic, DeepMind, or equivalent? Oliver judges sales outputs — the system judges itself on engineering standards.

| Score | Criteria |
|-------|----------|
| 9-10 | Clean architecture with clear separation of concerns. Wired into nervous system (bus signals, cross-wires, component map). Tested and verified working. No dead code, no orphan components. Delta-aware (doesn't rebuild what hasn't changed). Error handling covers failure modes. Documentation matches implementation. Would merge in a production codebase. |
| 7-8 | Architecture is sound. Wired into the system. Works correctly. Minor gaps: missing edge case handling, incomplete error paths, or one integration point not fully tested. Would merge with minor comments. |
| 5-6 | Works but standalone — not wired into nervous system. Or wired in but brittle (hardcoded paths, no error handling, breaks on edge cases). Would get "needs work" in review. |
| 3-4 | Doesn't integrate. Duplicates existing functionality. Untested. Hardcoded assumptions. Would be rejected in review. |
| 1-2 | Breaks existing system. Introduces regressions. Wrong architecture for the problem. |

## Anti-Mediocrity Rule

If a first draft scores 5-6, do NOT incrementally patch it. Scrap the draft, diagnose why it's mediocre (wrong angle? missing data? bad structure?), and rebuild from scratch with the diagnosis as input. Two clean attempts beat four incremental patches. This applies to all output types. Mediocre output that ships erodes trust faster than a delayed output that lands.

## Self-Score Protocol (SCORE step in 5-Point Verification)

The SCORE step is one unified pass, not separate sub-steps. It runs as step 5 of the verification stack (see .claude/gates.md).

Before presenting ANY output to Oliver:
1. **Confidence flag** — HIGH / MEDIUM / LOW. Mandatory on every major output.
2. **Identify rubric** — which rubric applies to this output type?
3. **Score honestly** — rate against the rubric. If scoring identifies a fixable problem, **fix it before presenting the score.** The score reflects the final state, not the first draft.
4. **State the gap** — when below 8, state what a 9/10 would look like. Not why 7/10 is fine. Bad: "7/10 — solid structure." Good: "7/10 — a 9 would reference their LinkedIn post about Q4 hiring. I didn't find that post, so I used a generic industry hook."
5. **Enforce** — below 7 = **BLOCKED**. Do not present. Revise until 7+. Oliver can override with "ship it anyway" but the block must be explicit: `BLOCKED: self-score [X]/10 — revising.`
6. **Log** — record the self-score in daily notes.

This consolidates what were previously separate steps (fix-before-score, metacognitive honesty, blocking gate) into one flow. Same enforcement, fewer labels. Changed in Session 21 verification stack consolidation.

## First-Draft Quality Floor
- First draft of ANY output must score 7+ before presenting
- If pre-flight proof block is complete and first draft is still below 7: diagnose WHY before revising (missing data? wrong framework? bad structure?)
- Maximum 2 iterations to reach Oliver's approval. If iteration 2 still isn't right: pause, ask Oliver what's missing instead of guessing with iteration 3
- Session 6 pattern: 4 iterations on cheat sheet because vault/NLM were skipped. Pre-flight blocks prevent this. But if you're iterating 3+ times WITH pre-flight complete, the problem is execution not research — escalate.

## Iteration Tracking
Log iterations per output: `[output]: draft [N] → score [X] → [reason for revision]`
Track in daily notes. If avg iterations > 2 across a session → flag in audit as Quality gap.
