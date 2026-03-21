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

### Post-Draft Tag Block (add to prospect note after Oliver approves):
```
## Touch [N] — [date]
- type: [cold|warm|follow-up|re-engage|post-demo|proposal|breakup]
- channel: email
- intent: [book-call|get-reply|nurture|close|discover]
- tone: [direct|casual|consultative|curious|empathetic]
- angle: [from LOOP_RULE_5 closed set]
- framework: [CCQ|Gap|SPIN|JOLT|Challenger]
- subject: [subject line]
- outcome: pending
- next_touch: [date]
- patterns_applied: [what from PATTERNS.md informed this draft]
```

### Self-Play Objection Check (MANDATORY — runs before Oliver sees anything):
After drafting, generate the prospect's most likely SPECIFIC objection based on the research. Not generic — specific: "If I were [name], I would push back on [X] because [Y]." If vulnerable, revise the draft to preemptively address it before presenting.
Format: `OBJECTION CHECK: "[specific objection]" — [HANDLED in draft / REVISED to address]`

### Post-Draft Polish:
- **Humanizer pass** — run /humanizer on the draft before presenting.
- **Self-score** — rate against quality-rubrics.md. Show inline: `Score: X/10 (email draft) — agree? Say "that's a [X]" to override`

### Email Structure (locked in):
1. **Hook** — personal, shows homework, graceful (never condescending)
2. **Pain** — their specific situation based on research (not generic)
3. **Solution** — how Sprites solves line 2, with case study numbers
4. **CTA** — low friction, casual (book a call or just reply)
