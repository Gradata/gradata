# Mandatory Gates — Load On Demand
# Referenced by CLAUDE.md. Load the relevant gate when the task triggers it.

## Pre-Draft Research Gate (MANDATORY — NO EXCEPTIONS)
**NO email draft (cold, inbound, or follow-up) may be written until ALL steps are completed.**

### Pre-Flight Proof Block (MUST appear above email draft):
```
CONFIDENCE: [HIGH / MEDIUM / LOW]
PRE-FLIGHT: [prospect name]
[x] Vault: brain/prospects/[file] — [read/created]
[x] PATTERNS.md: read — [best angle: X | avoid: Y | confidence: PROVEN/EMERGING/HYPOTHESIS/INSUFFICIENT]
[x] NotebookLM: queried — [case study/proof point found]
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
3-5 sentences in first person explaining your thinking. Cover: what the research revealed that matters most, what angle or framework it points to, and why that angle is right for THIS specific prospect (not the persona in general). Example: "I found that [name] just posted about struggling with creative bandwidth across 4 brands. Their site shows Meta ads on all brands but no unified reporting. This points to pain-point angle with the multi-brand consolidation case study — they're living the exact problem Sprites solves. CCQ framework because it's cold outreach and they haven't heard of us."

### Pre-Draft Checkpoint (present to Oliver BEFORE writing):
- **LinkedIn insight** — what I found on their profile/posts
- **Company insight** — what their site/positioning tells us
- **NotebookLM angle** — what notebooks surfaced for this persona
- **Pain point** — the specific pain I'm targeting and why
- **Framework** — which sales methodology I'm applying
- **Email type** — which template framework (CCQ, Inbound Welcome, Follow-Up)
- **Angle** — the one-line pitch angle
- **Case study** — which proof point/numbers to include

- **Competitive Draft** [OPTIONAL — Oliver can request "just one"] — generate 2 versions with different angles or tones. Present both with 1-line reasoning for each. Tag the pick: `choice: A|B, reason: [why], rejected_angle: [what lost]`. Log to PATTERNS.md Draft Preferences section.

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
After drafting, generate the prospect's most likely SPECIFIC objection based on the research. Not generic ("we don't have budget") — specific: "If I were [name], I would push back on [X] because [Y]." Use their actual situation, company context, and persona patterns to predict the pushback. Then check: does the draft handle this objection, or is it vulnerable? If vulnerable, revise the draft to preemptively address it before presenting.
Format: `OBJECTION CHECK: "[specific objection]" — [HANDLED in draft / REVISED to address]`

### Post-Draft Polish:
- **Humanizer pass** — run /humanizer on the draft before presenting. Catches 24 AI patterns: em dashes, promotional language, inflated symbolism, vague attributions, rule of three, AI vocabulary, negative parallelisms. Two-pass: first rewrite, then "what's still obviously AI?" audit.
- **Self-score** — rate against quality-rubrics.md. Show inline: `Score: X/10 (email draft) — agree? Say "that's a [X]" to override`

### Email Structure (locked in):
1. **Hook** — personal, shows homework, graceful (never condescending)
2. **Pain** — their specific situation based on research (not generic)
3. **Solution** — how Sprites solves line 2, with case study numbers
4. **CTA** — low friction, casual (book a call or just reply)

---

## Demo Prep Research Gate (MANDATORY — NO EXCEPTIONS)
**NO demo cheat sheet may be built until ALL steps are completed.**

### Pre-Flight Proof Block (MUST appear above cheat sheet output):
```
CONFIDENCE: [HIGH / MEDIUM / LOW]
PRE-FLIGHT: [prospect name]
[x] Vault: brain/prospects/[file] — [read/created]
[x] PATTERNS.md: read — [applicable insight or "no data for this persona"]
[x] NotebookLM: queried — [what was found]
[x] Knowledge graph: queried — [result]
[x] Lessons archive: searched [categories] — [hits or none]
```
**Confidence flag:** HIGH = strong research + proven framework match + clear angle. MEDIUM = one weak. LOW = gaps filled with assumptions.
If any shows [ ] instead of [x], STOP and complete before presenting output.

### Research Checklist (13-step):
1. **Win Story** — Write the closed-won narrative FIRST (3-5 lines): what they sign, what changes for them, what the deciding factor was, what referral they give. Then work backwards: what does the demo need to show to make this story happen?
2. **Google Calendar** — confirm demo time, attendees, meeting link. Check for conflicts.
3. **Web search: company** — what they do, industry, size, services, clients.
4. **Web search: person** — LinkedIn profile, title, headline, about section, recent posts.
5. **Apollo lookup** — free search for contact details, company size, tech stack. Check for any prior call recordings or touchpoints. Analyze for pain signals.
6. **Fireflies** — search by attendee email for any PRIOR call recordings (not from this demo — Fireflies captures the demo itself, so pre-demo there's no transcript of THIS meeting). This step finds recordings from previous calls with the same person. If no prior calls exist, mark as "no prior recordings" and move on.
7. **Web search: deeper person** — full name + company + role for additional context (personal site, resume, conference talks, social posts).
8. **Company website: leadership** — org structure, who's above the prospect, decision-maker chain.
9. **Company website: homepage** — services, tech stack (check for GTM/HubSpot/Meta Pixel), ad presence.
10. **Gmail search** — all prior emails with this person. Read Siamak/Anna outreach if any. Understand what was promised.
11. **Gmail read** — read the actual email threads for context on what they asked to see.
12. **Personal website/resume** — if they have one, get full work history and skills.
13. **Synthesize into demo prep brief:**
    a. Account snapshot + contact profile
    b. **Demo flow with specific Sprites thread links** — map each thread to their pain, include clickable URLs
    c. **Sales methodology application** — load sales-methodology.txt, apply Gap Selling / JOLT / relevant framework
    d. **Discovery questions with assumed answers** — write 5-8 disco Qs, predict likely answers based on research, then write follow-up Qs to dig deeper into pain so Oliver can relate the perfect workflow
    e. Objection handling table (predicted objections + responses)
    f. Close strategy (pricing, trial, next steps)
    g. **Draft as HTML email to Oliver** with clickable thread links, sent to Gmail as draft

### Reasoning Block (write BEFORE checkpoint, include in research receipt):
3-5 sentences covering: what the research revealed that matters most for this demo, which threads will resonate and why, and what the biggest risk to the close is. Write in first person.

### Demo Prep Checkpoint (present to Oliver BEFORE building):
- **Contact profile** — who they are, role, company, what they do
- **Prior touchpoints** — cold calls, emails, what was said (from Fireflies/Apollo)
- **Pain points confirmed** — what they've admitted vs what to probe
- **Threads to lead with** — which Sprites threads match their pain, in what order
- **Threads to skip** — what doesn't apply, don't force it
- **Objections likely** — based on persona type and prior conversations
- **Close strategy** — which offer/trial/pricing to propose

Oliver approves, THEN I build the cheat sheet.

### Claim-Level Source Tagging (MANDATORY for cheat sheets):
Every factual claim in the cheat sheet gets a bracketed source tag inline. Examples: "Recently expanded to three new markets [Apollo, 2026-03-01]" or "CMO joined 6 months ago [LinkedIn]" or "Said they want to consolidate reporting [Fireflies, 2026-03-15]". This makes notes auditable on a live call — Oliver can see at a glance what's verified vs inferred.

### Demo Prep Output:
Build prep doc in docs/Demo Prep/ with: account snapshot table, why strong fit, story-trap demo flow, threads to skip, 30-min agenda, objection handling table, trial close scripts, rapport notes, pre-demo checklist.
Also draft to Gmail (oliver@spritesai.com) as HTML + save file locally.

### Demo Prep Tag Block (add to prospect note):
```
## Demo Prep — [date]
- type: demo-prep
- channel: demo
- intent: discover
- framework: [Great Demo!/Gap Selling/SPIN/etc.]
- threads_planned: [list]
- win_story: [1-line predicted outcome]
- persona: [type from brain/personas/]
- patterns_consulted: [yes/no + what was applied]
```

### Story-Trap Demo Structure (MANDATORY)
Discovery questions are NOT a separate block. They are woven into the thread flow. Each thread gets a TRAP section:
1. Ask 2-3 questions designed to surface the exact pain the thread solves.
2. Listen for the admission ("it takes days", "we do it manually", "no one has time").
3. Transition: "Let me show you something" → demo the thread.
4. After thread: land the value in their words, not yours.
5. Repeat for next thread.
If the trap does not spring, SKIP that thread. 3 strong threads > 4 with one forced.

---

## Post-Demo Follow-Up Gate (MANDATORY — NO EXCEPTIONS)
**NO post-demo follow-up email may be drafted until Fireflies transcript is pulled and reviewed.**

### Pre-Flight:
```
CONFIDENCE: [HIGH / MEDIUM / LOW]
```

### Checklist:
0.5. **Lessons archive** — search lessons-archive.md for TONE, FLOW, LANGUAGE, FOLLOW-UP categories. Check graduated index first.
1. **Fireflies transcript** — MANDATORY. Extract: what was shown, reactions, exact quotes, objections, buy signals, next steps, pricing.
2. **LinkedIn** — re-check for new activity/posts since demo.
3. **NotebookLM** — query for follow-up framework and closed-won patterns.
4. **Pipedrive** — update deal stage, add demo notes, log demo activity.

### Reasoning Block:
3-5 sentences: what the transcript revealed about their interest level, which pain points are confirmed vs assumed, and what the follow-up needs to accomplish.

### Self-Play Objection Check:
After drafting the follow-up, generate the prospect's most likely specific pushback based on what happened in the demo. Revise if the draft is vulnerable.

### Post-Demo Email Structure:
1. **Hook** — reference something specific THEY said (from Fireflies)
2. **Recap** — 2-3 sentences on pain + solution, using their words
3. **Proposal/Next steps** — pricing if discussed, options, numbered next steps
4. **CTA** — clear next action

No generic "thanks for your time" emails. Every follow-up must reference specific things from the actual conversation.

---

## Cold Call Script Gate (MANDATORY — NO EXCEPTIONS)
**NO cold call script may be written until LinkedIn has been visited.**

### Pre-Flight:
```
CONFIDENCE: [HIGH / MEDIUM / LOW]
```

### Checklist:
0.5. **Lessons archive** — search lessons-archive.md for TONE, LANGUAGE, STRATEGY categories. Check graduated index first.
1. **LinkedIn profile** — headline, about, recent posts. Find a specific detail for the opener.
2. **Company website** — what they do, who they serve.
3. **Apollo** — title, company size, tech stack. Check Activities tab.
4. **Pipedrive** — deal exists? Prior calls or emails?

### Reasoning Block:
3-5 sentences: what the research revealed, why this opener will land, and what objection to expect on the call.

### Self-Play Objection Check:
After writing the script, predict the prospect's most likely live pushback. Add a response to the script's objection handling section.

### Script Structure:
1. Pattern interrupt opener — specific to THEM
2. Who you are — one sentence
3. Why you called — one sentence referencing their situation
4. Bridge to pain — one sentence
5. Soft ask — book the demo, nothing more

---

## LinkedIn Message Gate (MANDATORY — NO EXCEPTIONS)
**NO LinkedIn message or InMail may be written until profile has been visited.**

### Pre-Flight:
```
CONFIDENCE: [HIGH / MEDIUM / LOW]
```

### Checklist:
0.5. **Lessons archive** — search lessons-archive.md for TONE, LANGUAGE categories. Check graduated index first.
1. Visit their profile — posts, headline, about, recent activity
2. Find a personal hook — a post, milestone, role change
3. NotebookLM — persona match and angle
4. Keep it short — 3-4 sentences max

### Reasoning Block:
2-3 sentences: what hook you're using and why it's the right one for this person.

### Self-Play Objection Check:
After writing, predict the most likely reason they'd ignore or decline. If the message is vulnerable, revise.

---

## Pipedrive Note Quality Gate (MANDATORY — NO EXCEPTIONS)
**NO note may be published until all sources checked and data verified.**

### Checklist:
0.5. **Lessons archive** — search lessons-archive.md for CRM, ACCURACY categories. Check graduated index first.
1. All data from verified sources (Apollo, Fireflies, Gmail, Calendar, LinkedIn)
2. Never cite .md files as sources
3. Never publish with "pending" or "enrichment needed" flags
4. Never include AI attribution text
5. All notes in HTML format
6. Include corrections section if prior data was wrong
7. DELETE old note before publishing new one. No duplicates.

### Claim-Level Source Tagging (MANDATORY for CRM notes):
Every factual statement gets a bracketed source tag inline. Examples: "Company has 45 employees [Apollo]" or "Uses Shopify Plus across 3 stores [company website]" or "Mentioned budget concerns on first call [Fireflies, 2026-03-10]". No untagged facts. If a claim can't be sourced, mark it "[INFERRED — not confirmed]". This enforces that only verified data enters the CRM.

### Schema Validation (inspired by oswalpalash/ontology):
Before publishing any CRM note or prospect vault note, validate against required fields:

**Required for CRM notes (Pipedrive):**
- Contact name, title, company — all sourced
- At least one communication channel (email or phone)
- Deal stage (must match Pipedrive stage IDs)
- Last interaction date and type
- Next step with date and owner

**Required for vault notes (brain/prospects/):**
- Contact block (name, title, company, email)
- Persona type (from brain/personas/)
- Touch history (at least most recent touch with tags)
- Current deal stage
- Next touch date

**Validation rules:**
- No field may contain "[PENDING]" or "[TBD]" — either populate from a source or mark "[UNKNOWN — not available from [sources checked]]"
- Email addresses must pass format check (contains @, has domain)
- Dates must be real dates (no "soon" or "next week" — convert to absolute dates)
- Stage values must come from a defined set (not freeform text)

If validation fails, surface the specific failures: "Note validation failed: [field] is [issue]. Fix before publishing." Do not publish invalid notes.

---

## Win/Loss Analysis Gate (MANDATORY — NO EXCEPTIONS)
**When a deal closes (won OR lost), debrief MUST be written.**

### Closed-Won:
0.5. **Lessons archive** — search lessons-archive.md for STRATEGY, ACCURACY, PROCESS categories. Check graduated index first.
1. Pull Fireflies transcript for final call
2. Document: persona, pain, threads that landed, close script, cycle length, decision maker, pricing
3. Write vault note in brain/demos/ linked to persona and objection patterns
4. Update persona note with win data
5. Feed winning approach to NotebookLM

### Closed-Lost:
1. Document: why no, which objection wasn't overcome, what to do differently
2. Write vault note with loss reason
3. Update objection notes
4. Log lesson
