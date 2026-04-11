---
name: S102 Handoff
description: S102 complete — 9 algo features shipped, PR #24 open, autoresearch installed, 3 sims designed, Innocean analyzed
type: project
---

## S102 Summary
- PR #23 merged (brain.scope, rule-to-hook, formula v3, integration tests)
- 9 MiroFish P0-P2 features implemented across 3 parallel worktrees:
  - P0.1 Semantic severity (embeddings.py + diff_engine.py)
  - P0.2 Rule suppression tracking (rule_tracker.py + rule_engine.py)
  - P0.3 Rosch 6-category taxonomy (_tag_taxonomy.py)
  - P1.1 Bayesian confidence (beta posterior integrated into self_improvement.py)
  - P1.2 Implicit approval (positive signals + OUTPUT_ACCEPTED in implicit_feedback.py)
  - P1.3 Intent classifier (new detection/intent_classifier.py)
  - P2.1 Recurring patterns (behavioral_extractor.py)
  - P2.2 Temporal scope (decay curves on _scope.py)
  - P2.3 Cognitive load tag (_tag_taxonomy.py)
- PR #24 open: feat/s102-mirofish-p0-p2 (1,921 tests, CI green after _p shadowing fix)
- Karpathy autoresearch-win-rtx installed at .tmp/autoresearch-win-rtx, baselined val_bpb 0.908355
- Innocean demo analyzed (Fireflies transcript pulled, follow-up strategy written, email drafted)

## Critical Bug Found + Fixed
`for _p in ROSCH_PARENTS` shadowed `import gradata._paths as _p` — broke taxonomy reload silently. Fixed by renaming loop var to `_rp`.

## What's Next (S103)

### Wave 1 — Research (worktree, background)
Read the 5 synthesis files that inform experiment design:
- brain/stress_test_results/SIM103_EXHAUSTIVE_SYNTHESIS.md
- brain/stress_test_results/SIM102_EXHAUSTIVE_SYNTHESIS.md
- brain/stress_test_results/SIM_DESIGN_RESEARCH.md
- brain/stress_test_results/WAVE2_SYNTHESIS.md
- brain/stress_test_results/PUBLISHED_MARKETING_RESEARCH.md

### Wave 2 — Build brain_benchmark.py
The autoresearch harness for Gradata. Replays corrections from events.jsonl into a fresh brain, outputs a quality score. Equivalent of Shopify's rendering benchmark.

### Wave 3 — Run 3 Sims (1 hour each, sequential, in own terminal)
Each sim = autoresearch loop modifying pipeline code + measuring via brain_benchmark.py

**Sim 1: Conciseness** — agent modifies rule_engine.py (apply_rules scoring/filtering). Metric: quality - length_penalty. Find which rules bloat output.

**Sim 2: Cold Start** — agent modifies self_improvement.py (graduation constants, FSRS curves, Bayesian blend). Metric: sessions to first useful RULE from real events.jsonl replay.

**Sim 3: Preference Reversal** — agent modifies self_improvement.py (decay rates, PREFERENCE_DECAY_DAMPER). Metric: sessions to adapt when user changes preference.

### Wave 4 — Experiments (background, independent)
- Exp 4: JTBD language validation
- Exp 6: Published stat validation (using Duolingo HLR, Copilot RCT template)
- Use Gemma4:e4b (localhost:11434) as free local judge

### Wave 5 — Marketing Numbers
Unblocked now that algo is fixed. Generate claims using published methodology.

### Parallel — PR #24
Address CodeRabbit review comments when they come in.

### Parallel — Innocean
Send follow-up email (draft ready). Track response.

### Wave 6 — MiroFish Sim: BLIND Architecture Design
**The question (give NO context about Gradata's current approach):**

"You are an AI/ML researcher. A user interacts with an LLM assistant daily. The user corrects the assistant's outputs — fixing tone, facts, structure, process. Today, every session starts from zero. The corrections are lost. The user repeats themselves forever.

Design a system where corrections compound over time so the user corrects less and less. The user should feel the AI getting better. Constraints: you cannot fine-tune the base model. You only control what happens around it — context, memory, retrieval, prompting, middleware, whatever you want. The base LLM is a black box API.

What architecture would you build? What does the research literature say about this problem? What are the failure modes? How do you prove it works?"

**WHY BLIND:** Do NOT mention Gradata, graduation pipelines, rules, lessons, FSRS, confidence scores, or any of our current approach. Let the experts design from scratch. If they independently converge on correction→rule graduation, we're validated. If they propose something fundamentally different, we need to evaluate whether to pivot.

**Personas:** Mix of ML researchers (in-context learning, RLHF, memory systems), HCI researchers (user adaptation, cognitive load), production engineers (Duolingo, Grammarly, Copilot — systems that learn user preferences).

Run on Gemma4:e4b or DeepSeek. 750+ posts. Full exhaustive synthesis after.

**After sim:** Compare their architecture to ours. Three possible outcomes:
1. They converge on our approach → strong validation, cite the sim
2. They propose something better → implement it, autoresearch-optimize it
3. Mixed — some ideas we have, some we don't → cherry-pick the novel parts

**Then:** Take whatever architecture wins and point Karpathy autoresearch at it with brain_benchmark.py as metric. Optimize overnight.

### Wave 6B — MiroFish Sim: BLIND Distribution/Meta-Rule Architecture
**Second blind sim. Separate question. Different expert domain.**

"You have a cloud platform. Thousands of users independently teach their AI assistants through corrections. Some users discover the same lessons independently (e.g. 'never use passive voice in sales emails'). Design a system that:
1. Detects when independent users converge on the same lesson
2. Synthesizes individual lessons into universal principles
3. Pushes principles back to users — both offline (local CLI tool) and online (cloud dashboard)
4. Does this without leaking private corrections between users
5. Lets users opt in/out of shared wisdom
6. Proves shared principles help individual users (not hurt them)

What architecture? What does federated learning say? Recommendation systems? How do you handle conflicting principles across users? How do you deliver this through a dashboard UX?"

**WHY SEPARATE:** Sim A = single user learning loop. Sim B = network effect + distribution. Different research domains. Don't mix.

**Personas:** Federated learning researchers, recommendation system engineers, privacy/security experts, product designers (dashboard UX), platform architects (local↔cloud sync).

**After:** Compare to our meta-rule pipeline + cloud sync architecture. Same three outcomes: validated, pivot, or cherry-pick.

### Tool Routing (IMPORTANT — read this)

| Tool | What it is | When to use | How to run |
|---|---|---|---|
| **MiroFish** | 10-persona expert panel simulation | Research questions, design decisions, consensus-building | Gemma4:e4b (localhost:11434) or DeepSeek or Claude. Run as sim with 750+ posts |
| **Karpathy autoresearch** | Autonomous code optimization loop | Optimize code/model against a metric overnight | Separate terminal: `cd .tmp/autoresearch-win-rtx && claude` |
| **/autoresearch** (ours) | Code iteration loop in Claude Code | Optimize pipeline code, fix loops, scenario testing | In main session: `/autoresearch` or `/autoresearch:fix` etc |
| **Gemma4:e4b** | Free local LLM judge | Evaluation, scoring, classification without API costs | localhost:11434 via ollama |

**MiroFish is NOT autoresearch. Autoresearch is NOT MiroFish.**
- MiroFish = crowd simulation for research/consensus (WHAT to build)
- Autoresearch = autonomous optimization loop (HOW to make it better)
- Pipeline: MiroFish first (design) → autoresearch second (optimize)

## How to Run
Sims run in separate terminal: `cd .tmp/autoresearch-win-rtx && claude`
Only 1 sim at a time (GPU constraint).
Main session stays OODA on pipeline work.
MiroFish sims run in main session or background agent (no GPU needed).
