---
name: demo-prep
description: Pre-flight checklist for demo preparation. Verifies all research sources (vault, NotebookLM, LinkedIn, Apollo, Fireflies) are checked and cheat sheet inputs are complete before building the demo brief.
---

# Demo Prep Research Gate (MANDATORY — NO EXCEPTIONS)
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
If any shows [ ] instead of [x], STOP and complete before presenting output.

### Research Checklist (15-step):
**Auto-depth:** After step 1 (win story) and vault check, use .claude/skills/research/SKILL.md Phase 0 to measure the gap. Returning prospect with Fireflies transcript + prior notes = abbreviated web research. New cold inbound = full 15-step deep dive. The gate sources below are MANDATORY — auto-depth controls depth, not whether to check.

1. **Win Story** — Write the closed-won narrative FIRST (3-5 lines): what they sign, what changes for them, what the deciding factor was, what referral they give. Then work backwards.
2. **Google Calendar** — confirm demo time, attendees, meeting link.
3. **Web search: company** — what they do, industry, size, services, clients.
4. **Web search: person** — LinkedIn profile, title, headline, about section, recent posts.
5. **Apollo lookup** — free search for contact details, company size, tech stack. Check for any prior call recordings.
6. **Fireflies** — search by attendee email for any PRIOR call recordings.
7. **Web search: deeper person** — full name + company + role for additional context.
8. **Company website: leadership** — org structure, decision-maker chain.
9. **Company website: homepage** — services, tech stack (check for GTM/HubSpot/Meta Pixel), ad presence.
9b. **Ad platform audit** — Using domain/reference/meta-api-patterns.md and domain/reference/google-ads-patterns.md, analyze what this prospect is likely running and where they're leaving ROAS on the table. Check for: Meta Pixel present? Google Ads tag? What campaign types would serve them best? What bidding strategy fits their budget and goals? What common mistakes are they probably making (wrong objective, no batch optimization, manual bidding on small budgets)? This analysis directly shapes which Sprites threads to demo and what ROAS/ROI improvement story to tell.
9c. **Thread flow design** — Based on the ad platform audit, select and sequence the demo threads that map to THIS prospect's biggest gaps. For each thread: (1) what platform gap it addresses, (2) what ROAS/ROI improvement it unlocks, (3) what the before/after looks like in their specific case. This makes the demo a consulting session, not a feature tour.
10. **Gmail search** — all prior emails with this person.
11. **Gmail read** — read the actual email threads.
12. **Personal website/resume** — full work history and skills.
13. **Synthesize into demo prep brief:**
    a. Account snapshot + contact profile
    b. Demo flow with specific Sprites thread links
    c. Sales methodology application
    d. Discovery questions with assumed answers
    e. Objection handling table
    f. Close strategy (pricing, trial, next steps)
    g. Draft as HTML email to Oliver

### Claim-Level Source Tagging (MANDATORY):
Every factual claim gets a bracketed source tag inline.

### Story-Trap Demo Structure (MANDATORY)
Discovery questions are NOT a separate block. They are woven into the thread flow. Each thread gets a TRAP section:
1. Ask 2-3 questions designed to surface the exact pain the thread solves.
2. Listen for the admission.
3. Transition: "Let me show you something" → demo the thread.
4. After thread: land the value in their words, not yours.
5. Repeat for next thread.
If the trap does not spring, SKIP that thread. 3 strong threads > 4 with one forced.
