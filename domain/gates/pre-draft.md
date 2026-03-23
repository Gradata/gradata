---
name: pre-draft
description: Pre-flight checklist for email drafts (cold, inbound, follow-up). Ensures vault, PATTERNS, NotebookLM, LinkedIn, and Apollo research are complete before writing.
---

# Pre-Draft Research Gate (MANDATORY — NO EXCEPTIONS)
**NO email draft (cold, inbound, or follow-up) may be written until ALL steps are completed.**

### Pre-Flight Proof Block (MUST appear above email draft):
```
CONFIDENCE: [HIGH / MEDIUM / LOW]
PRE-FLIGHT: [prospect name]
[x] Vault: brain/prospects/[file] — [read/created]
[x] PATTERNS.md: read — [best angle: X | avoid: Y | confidence: PROVEN/EMERGING/HYPOTHESIS/INSUFFICIENT]
[x] NotebookLM (tier system: .claude/skills/notebooklm/SKILL.md): queried — [case study/proof point found]
[x] Lessons archive: searched [categories] — [hits or none]
[x] Persona MOC: [type] — [what works for this persona]
```
**Confidence flag (first line, mandatory):** HIGH = strong research + proven framework match + clear angle. MEDIUM = one of those was weak. LOW = gaps filled with assumptions. Oliver treats LOW outputs with more scrutiny.
If any shows [ ] instead of [x], STOP and complete before presenting draft.

### Research Checklist:
**Auto-depth:** After step 0 (vault check), use .claude/skills/research/SKILL.md Phase 0 to measure the gap. If vault has rich data (3+ prior touches, known pain, angle history), steps 1-2 can be abbreviated. If vault is empty (new prospect), run all steps fully. The gate sources below are MANDATORY — auto-depth controls how deep, not whether to check.

0. **Obsidian vault** [MANDATORY — CANNOT SKIP] — query brain/ with specific questions, not whole-file reads. Ask: "What do I already know about [person/company]?" "What angles have been tried?" "What objections came up with similar personas?" "What worked for this persona type?" Check persona MOC page (brain/personas/[type].md) with: "What patterns work for [persona type]?" Check knowledge graph: `python knowledge_graph.py query-playbook [persona]`. This is FREE institutional memory — skipping it means repeating mistakes.
0.5. **Lessons archive** — search lessons-archive.md for categories matching this task (TONE, FLOW, LANGUAGE, DRAFTING, STRATEGY). Check graduated index in lessons.md first for quick scan.
1. **LinkedIn profile** — visit via browser (not Apollo). Read recent posts, activity, headline, about section. Find a personal insight to reference.
2. **Company website** — visit their actual site. Understand positioning, services, clients, language.
3. **NotebookLM** [MANDATORY — CANNOT SKIP] (tier system: .claude/skills/notebooklm/SKILL.md) — query Sprites Sales notebook (ID: 1e9d15ed) for: case studies matching this persona, proof points for this industry, objection counters. Query Demo Prep notebook (ID: 6bdf40a0) if demo-related. NotebookLM has 6 sessions of accumulated intelligence — not using it is like having a playbook and not reading it.
4. **Apollo enrichment** — title, company size, tech stack, employment history. Don't double-dip.
5. **Sales methodology fit** — which framework? (Gap Selling for current→future state, SPIN for discovery, JOLT for indecision, CCQ for cold)
6. **Fireflies/Pipedrive** — any prior touchpoints? Existing deal? Past calls?

### Reasoning Block (write BEFORE checkpoint, include in research receipt):
3-5 sentences in first person explaining your thinking. Cover: what the research revealed that matters most, what angle or framework it points to, and why that angle is right for THIS specific prospect (not the persona in general).

### Pre-Draft Checkpoint (present to Oliver BEFORE writing):
- **LinkedIn insight** — what I found on their profile/posts
- **Company insight** — what their site/positioning tells us
- **NotebookLM angle** — what notebooks surfaced for this persona
- **Pain point** — the specific pain I'm targeting and why
- **Framework** — which sales methodology I'm applying
- **Email type** — which template framework (CCQ, Inbound Welcome, Follow-Up)
- **Angle** — the one-line pitch angle
- **Case study** — which proof point/numbers to include
- **Competitive Draft** [OPTIONAL — Oliver can request "just one"] — generate 2 versions with different angles or tones.

Oliver approves the angle, THEN I draft. No skipping. No exceptions. Ever.

Post-draft steps (tag block, objection check, humanizer, self-score, email structure) are inherited from .claude/gates.md gate protocol. Do not redefine here.
