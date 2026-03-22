# SDK Onboarding Flow
# ============================================================================
# Drop-in executable for Claude Code. Runs on first launch when company.md
# does not exist. Produces: company.md, context-manifest.md, .agentignore,
# task-queue.md. Completable in under 15 minutes.
# ============================================================================

## Guard Clause

```
IF file_exists("company.md"):
    SKIP this entire flow.
    Load context-manifest.md and proceed to normal session startup.
ELSE:
    Run onboarding below.
```

Do NOT run this flow if company.md already exists. The presence of company.md means onboarding is complete.

---

## How This Flow Works (agent instructions, not shown to buyer)

You are onboarding a new buyer of the AI sales agent SDK. The buyer does not know how the system works internally. Your job is to ask conversational questions in 4 sections, wait for answers, then generate 4 output files from their responses. Never mention CARL, event hooks, meta-loops, audit systems, or internal architecture. The buyer should feel like they're setting up a smart assistant, not configuring enterprise infrastructure.

**Pacing rules:**
- Ask ONE section at a time. Wait for answers before moving to the next section.
- Within a section, ask all questions together (they're thematically grouped).
- If the buyer gives a short answer, follow up once to get specifics. Don't push beyond that.
- If the buyer skips a question, use a sensible default and note it in company.md as `[DEFAULT — buyer can override]`.
- Total time budget: 15 minutes. If a section is dragging, offer to use defaults and move on.

**Tone:** Direct, professional, zero jargon. Like a sharp ops person setting up a new hire's tools on day one.

---

## Section 1: Your Business (3 minutes)

Ask these questions conversationally. Group them naturally — don't fire them as a numbered list.

```
QUESTIONS:
1. What's your company name and what do you sell?
2. Who's your ideal customer? (Industry, company size, geography, any filters)
3. What does your sales process look like end to end? (How do deals start, what stages do they go through, how do they close?)
4. What CRM do you use? (Pipedrive, Salesforce, HubSpot, other)
5. What's your role? (AE, SDR, founder doing sales, sales manager, other)
6. How many people are on the sales team? (Just you, 2-5, 6+)
```

**Follow-up if answers are thin:**
- "When you say [X], what does that actually look like day to day?"
- "What's the typical deal size and cycle length?"
- "Who else is involved in the sale besides you?"

**Store answers for:** company.md (all), context-manifest.md (CRM type determines tool loading), .agentignore (company size affects archive patterns).

---

## Section 2: Your Tools and Integrations (3 minutes)

```
QUESTIONS:
1. Which of these do you use? Just say yes/no for each:
   - Email: Gmail or Outlook?
   - Calendar: Google Calendar, Outlook, Calendly?
   - Call recording: Fireflies, Gong, Chorus, none?
   - Lead enrichment: Apollo, ZoomInfo, Clay, none?
   - Cold outreach: Instantly, Mailchimp, Outreach, none?
   - Anything else I should know about? (Slack, Notion, Sheets, etc.)

2. Which of these does the agent have MCP access to right now?
   (If they don't know what MCP means: "Which tools can Claude already connect to? Check your Claude Code settings.")

3. Are there any tools with usage limits or costs I should know about?
   (e.g., Apollo credits, Composio API calls, enrichment budgets)
```

**Store answers for:** context-manifest.md (tool loading rules, fallback chains), company.md (tool inventory).

---

## Section 3: Your Work Style (3 minutes)

```
QUESTIONS:
1. How do you want emails to sound? Pick one or describe it:
   - Direct and short (5-6 sentences, get to the point)
   - Warm and consultative (builds rapport, asks questions)
   - Formal and polished (corporate tone)
   - Casual and conversational (like texting a colleague)

2. Any words or phrases you never want in your emails?
   (Common bans: "leverage", "synergy", "circle back", "game-changer")

3. What's your email signature? (Paste it or describe it)

4. What's your booking link? (Calendly, HubSpot meetings, etc.)

5. How do you want to approve things?
   - "Show me everything before it goes out" (full approval mode)
   - "Draft emails for my review, but handle CRM and notes yourself" (hybrid)
   - "Handle routine stuff, flag me on judgment calls" (autonomous)

6. When something goes wrong — a tool fails, data is missing — do you want to know immediately, or do you want me to handle it and tell you at the end of the session?
```

**Store answers for:** company.md (writing rules, approval level), context-manifest.md (approval gates), .agentignore (nothing).

---

## Section 4: Your Priorities and Boundaries (3 minutes)

```
QUESTIONS:
1. What are the 3-5 things you do most often that you want help with?
   (Examples: writing follow-up emails, prepping for demos, updating CRM, building prospect lists, researching companies)

2. What should the agent never touch or read?
   (Examples: personal files, archived deals, other team members' data, certain folders)

3. Is there anything from your past work — old sequences, closed deals, archived campaigns — that you want completely excluded?

4. What does "done well" look like for you? How will you know the agent is working?
```

**Store answers for:** company.md (priorities), .agentignore (exclusions), context-manifest.md (task-triggered loading based on priorities).

---

## Section 5: File Generation (agent executes silently — 3 minutes)

After all 4 question sections are answered, generate these files without asking more questions. Show the buyer a brief summary of what was created and where.

### File 1: company.md

Write to `company.md` in the project root. This is the buyer's identity file — loaded at every session startup.

```markdown
# Company Profile

## Company
- **Name:** [from Section 1]
- **Product:** [what they sell, from Section 1]
- **ICP:** [ideal customer profile, from Section 1]
- **Deal size:** [if mentioned]
- **Sales cycle:** [if mentioned]

## Seller
- **Name:** [from Section 1]
- **Role:** [from Section 1]
- **Team size:** [from Section 1]

## Sales Process
- **Stages:** [from Section 1, mapped to CRM stages if provided]
- **How deals start:** [from Section 1]
- **How deals close:** [from Section 1]

## Tools
| Tool | Provider | MCP Connected | Cost Limits |
|------|----------|---------------|-------------|
| CRM | [answer] | [yes/no] | [if any] |
| Email | [answer] | [yes/no] | — |
| Calendar | [answer] | [yes/no] | — |
| Call Recording | [answer] | [yes/no] | — |
| Enrichment | [answer] | [yes/no] | [if any] |
| Cold Outreach | [answer] | [yes/no] | — |
| [Other] | [answer] | [yes/no] | [if any] |

## Writing Rules
- **Tone:** [from Section 3]
- **Banned words:** [from Section 3]
- **Opening:** "Hi [First Name],"
- **CTA link:** [booking link from Section 3]
- **Signature:** [from Section 3]
- **Max length:** [derived from tone — direct=150 words, consultative=200, formal=200, casual=120]

## Approval Mode
[full / hybrid / autonomous — from Section 3]

## Error Handling
[immediate / end-of-session — from Section 3]

## Top Priorities
1. [from Section 4]
2. [from Section 4]
3. [from Section 4]
4. [from Section 4, if given]
5. [from Section 4, if given]

## Generated
- **Date:** [today]
- **Onboarding version:** 1.0
```

---

### File 2: context-manifest.md

Write to `context-manifest.md` in the project root. This is the lazy loading controller — it defines what loads when and replaces the startup sequence in CLAUDE.md.

#### Schema

```markdown
# Context Manifest
# ============================================================================
# Controls what the agent loads and when. Designed as a REPLACEMENT for the
# inline startup sequence — not an additive layer. If this file exists,
# the agent follows THIS loading order, not the CLAUDE.md startup steps.
# ============================================================================

## Loading Tiers

### TIER 0: Always Load (every session, no conditions)
# These files load before the agent responds to the first message.
# Budget: under 8k tokens total. If this tier exceeds 8k, something must
# move to Tier 1 or Tier 2.

| File | Purpose | Est. Tokens | Notes |
|------|---------|-------------|-------|
| company.md | Buyer identity, ICP, writing rules, tools | ~800 | — |
| CLAUDE.md | Master rules (framework only) | ~2500 | Domain sections load on demand |
| brain/loop-state.md | Session checkpoint — what's due, what changed | ~1000 | Source of truth for session priorities |
| .claude/lessons.md | Mistake log — scan every entry | ~1500 | Never repeat a logged mistake |
| .carl/manifest | Which CARL domains are active | ~300 | Determines keyword-triggered loading |
| .carl/global | Universal rules | ~600 | Always active |
| .carl/context | Context bracket rules | ~300 | Always active |

### TIER 1: Startup Checks (run once at session start, results cached)
# These are actions, not file reads. They run in parallel where possible.
# Results are surfaced in the startup status, then the data is discarded
# from active context (only the summary persists).

| Check | Tool | Condition | Skip If |
|-------|------|-----------|---------|
| Calendar scan | gcal_list_events | Always | — |
| Morning brief | file read | brain/morning-brief.md fresh (<4h) | Stale or missing — run Gmail/Fireflies inline |
| Gmail scan | gmail_search | Only prospects in loop-state.md "Gmail Check List" | Morning brief is fresh |
| Fireflies scan | fireflies_search | Search for new recordings by team emails | Morning brief is fresh |
| Prospect scan | file read | brain/prospects/* for next_touch <= today | — |
| Signal scan | file read | brain/signals.md for relevance >= 7 | — |
| System heartbeat | file check | brain/system.db, brain/.git, .carl/loop size, CLAUDE.md line count | — |

### TIER 2: Task-Triggered (load ONLY when a specific task begins)
# These files are pointers. The agent knows they exist but does NOT read
# them until the buyer's request matches the intent trigger.

| File | Intent Trigger | Est. Tokens |
|------|---------------|-------------|
| .claude/gates.md | Any output task (email, demo prep, CRM note, cold call, LinkedIn) | ~3000 |
| .claude/quality-rubrics.md | Any output requiring self-scoring | ~1000 |
| .claude/fallback-chains.md | Any tool failure | ~1500 |
| brain/emails/PATTERNS.md | Any prospect interaction (email, call, demo) | ~2000 |
| docs/sprites_context.md | Product knowledge, case studies, objection handling | ~3000 |
| docs/Email Templates/templates.txt | Email drafting (cold, inbound, follow-up) | ~1500 |
| docs/Sales Playbooks/sales-methodology.txt | Demo prep, discovery calls | ~2000 |
| docs/Sales Playbooks/prospecting-instructions.txt | List building, prospecting | ~1000 |
| docs/Sales Playbooks/my-role.txt | Email drafting | ~500 |
| docs/Demo Prep/Demo Threads.txt | Demo prep | ~1500 |
| .carl/prospect-email | Email drafting task detected | ~800 |
| .carl/demo-prep | Demo prep task detected | ~800 |
| .carl/coldcall | Cold call task detected | ~600 |
| .carl/listbuild | List building task detected | ~600 |
| .carl/linkedin | LinkedIn outreach task detected | ~600 |
| .carl/loop | Prospect interaction (always-on but heavy — defer full read to task) | ~4000 |
| .claude/auditor-system.md | Session wrap-up | ~3000 |
| brain/events.jsonl | Session wrap-up step 9 (event verification) | ~800 |
| .claude/health-audit.md | Session wrap-up step 6 | ~1000 |
| .claude/truth-protocol.md | Loaded via CARL global pointer, not file read | ~500 |
| brain/system-patterns.md | Session wrap-up step 9, meta-analysis | ~3000 |
| brain/forecasting.md | Deal health scoring, pipeline analytics | ~1000 |
| Leads/STATUS.md | Lead campaign management | ~500 |

### TIER 3: Never Load (managed by .agentignore)
# See .agentignore for the full exclusion list.
# These files exist in the project but are never read or indexed.

## Loading Rules

1. **Tier 0 loads before first response.** No exceptions. If any Tier 0 file is missing, surface it as a startup alert.
2. **Tier 1 runs in parallel after Tier 0.** Results cached in a startup status block. Raw data not retained in context.
3. **Tier 2 loads on first task match.** Once loaded for a task, stays in context for the session (don't re-read per output unless the file changed).
4. **Tier 3 never loads.** Agent must check .agentignore before reading any file not in Tiers 0-2.
5. **Token budget:** Tier 0 target is under 8k tokens. If startup consistently exceeds 10k, flag for manifest review.
6. **Override:** Buyer can say "load [file]" to force-load any Tier 2 file regardless of intent matching.
7. **Manifest is the authority.** If CLAUDE.md startup steps and context-manifest.md conflict, context-manifest.md wins. The CLAUDE.md startup section should contain only: "Read and execute context-manifest.md."

## Reconciliation Log
# This section is auto-generated during onboarding. It maps every file from
# the previous CLAUDE.md startup sequence to its new tier in this manifest.

| File | Previous Location | New Tier | Action |
|------|------------------|----------|--------|
| CLAUDE.md | Auto-loaded | Tier 0 | Stays at startup |
| docs/startup-brief.md | Phase 1 Core | REMOVED | Replaced by loop-state.md + company.md |
| .claude/lessons.md | Phase 1 Core | Tier 0 | Stays at startup |
| Google Calendar | Phase 1 Core | Tier 1 | Moved to startup check (action, not file read) |
| brain/morning-brief.md | Phase 0 | Tier 1 | Moved to startup check (conditional) |
| .carl/manifest | Phase 2 | Tier 0 | Promoted to always-load (lightweight) |
| .carl/global | Phase 2 | Tier 0 | Promoted to always-load (lightweight) |
| .carl/context | Phase 2 | Tier 0 | Promoted to always-load (lightweight) |
| brain/loop-state.md | Phase 1 (from CLAUDE.md) | Tier 0 | Stays at startup |
| brain/signals.md | Phase 1.6 | Tier 1 | Moved to startup check (scan only) |
| brain/prospects/* | Phase 1.5 scan | Tier 1 | Moved to startup check (scan only) |
| Gmail scan | Phase 1.5 | Tier 1 | Stays as startup check (conditional on morning brief) |
| Fireflies scan | Phase 1.5 | Tier 1 | Stays as startup check (conditional on morning brief) |
| brain/system.db | Phase 0.5 heartbeat | Tier 1 | Stays as startup check |
| docs/Email Templates/templates.txt | Phase 3 on-demand | Tier 2 | Stays on-demand — no change |
| .carl/prospect-email | Phase 3 on-demand | Tier 2 | Stays on-demand — no change |
| docs/Sales Playbooks/* | Phase 3 on-demand | Tier 2 | Stays on-demand — no change |
| docs/Demo Prep/Demo Threads.txt | Phase 3 on-demand | Tier 2 | Stays on-demand — no change |
| .carl/demo-prep | Phase 3 on-demand | Tier 2 | Stays on-demand — no change |
| docs/sprites_context.md | Phase 3 on-demand | Tier 2 | Stays on-demand — no change |
| Leads/STATUS.md | Phase 3 on-demand | Tier 2 | Stays on-demand — no change |
| .claude/gates.md | On-demand (gate fires) | Tier 2 | Stays on-demand — no change |
| .claude/quality-rubrics.md | On-demand (self-score) | Tier 2 | Stays on-demand — no change |
| .claude/fallback-chains.md | On-demand (tool failure) | Tier 2 | Stays on-demand — no change |
| .claude/auditor-system.md | Wrap-up only | Tier 2 | Stays on-demand — no change |
| brain/emails/PATTERNS.md | On-demand (prospect work) | Tier 2 | Stays on-demand — no change |

### Confirmed: Zero Double Loads
No file appears in more than one tier. startup-brief.md has been replaced (its
responsibilities split between company.md in Tier 0 and loop-state.md in Tier 0).
The CLAUDE.md startup section should be reduced to a single line pointing to this
manifest. All Phase references above refer to the old skills/session-start/SKILL.md
phases, which this manifest supersedes.
```

**Customization rules for the agent generating this file:**
- Populate Tier 0 with files that exist in the buyer's project. If a file doesn't exist yet (e.g., brain/loop-state.md on first run), note it as `[CREATED AT FIRST SESSION END]`.
- Populate Tier 1 checks based on which tools the buyer confirmed in Section 2. If no Fireflies → remove Fireflies scan. If no CRM → remove Pipedrive check.
- Populate Tier 2 based on the buyer's top priorities from Section 4. If they never do cold calls → cold call files can move to Tier 3.
- The Reconciliation Log only needs to be populated if the buyer is migrating from an existing setup. For fresh SDK installs, write: "Fresh install — no previous startup sequence to reconcile."

---

### File 3: .agentignore

Write to `.agentignore` in the project root.

#### Format

```
# .agentignore
# ============================================================================
# Files and directories the agent will never read, index, or load into context.
# Syntax: gitignore-compatible glob patterns.
# Lines starting with # are comments. Blank lines are ignored.
# To un-ignore a specific file inside an ignored directory, prefix with !
# ============================================================================

# --- Defaults (ship with every SDK install) ---

# Archives — closed deals, old sequences, retired campaigns
brain/archive/
archive/
**/archived/
**/*archived*

# Session history — agent reads loop-state.md, not old session notes
docs/Session Notes/*.md
!docs/Session Notes/[LATEST].md

# Git internals
.git/
brain/.git/

# OS and editor artifacts
.DS_Store
Thumbs.db
*.swp
*.swo
*~
.vscode/
.idea/

# Large binary files the agent can't meaningfully read
*.zip
*.tar.gz
*.mp4
*.mp3
*.wav
*.mov
*.avi

# Credentials and secrets
.env
.env.*
**/credentials*
**/secrets*
**/*token*
**/*key*.json

# --- Buyer-specific exclusions (populated from Section 4 answers) ---
# [Agent fills these based on buyer's answers to "what should the agent never touch?"]

```

**Application rules (for the agent at runtime):**
1. Before reading ANY file not already in context-manifest.md Tiers 0-2, check .agentignore.
2. If the file matches an ignore pattern, do NOT read it. Do not mention its contents. Do not index it for search.
3. If the buyer explicitly asks to read an ignored file ("read archive/old-deal.md"), warn once: "That file is in .agentignore. Want me to read it anyway?" If yes, read it but do not add it to context-manifest.md.
4. .agentignore is checked at: (a) session startup scans, (b) prospect note lookups, (c) any Glob/Grep/Read call, (d) task queue file access.
5. The agent NEVER modifies .agentignore without the buyer's explicit instruction.

---

### File 4: task-queue.md

Write to `task-queue.md` in the project root. Starts empty, ready for use.

```markdown
# Task Queue
# ============================================================================
# Fire-and-forget tasks. Add a task, the agent works it in the background.
# Completed tasks move to the Review section for your approval.
# ============================================================================

## How to Use
# Say "queue: [task description]" or "add to queue: [task]" to add a task.
# Say "check queue" or "what's in the queue" to see status.
# Say "approve [task ID]" or "reject [task ID]" to handle completed work.

## Active Tasks
<!-- No active tasks. Say "queue: [task]" to add one. -->

## Completed — Pending Review
<!-- Completed tasks appear here with their outputs for your approval. -->

## Approved
<!-- Approved tasks are logged here, then archived after 7 days. -->

## Rejected
<!-- Rejected tasks are logged here with rejection reason. -->
```

#### Task Queue Schema (for agent internals)

When the buyer adds a task, create an entry in Active Tasks:

```markdown
### TASK-[NNN]: [short title]
- **Added:** [date + time]
- **Priority:** [high / normal / low — inferred from context or buyer instruction]
- **Type:** [prospect-list / enrichment / demo-prep / email-batch / research / crm-sync / other]
- **Description:** [buyer's words, verbatim]
- **Estimated effort:** [small: <5 min / medium: 5-30 min / large: 30+ min]
- **Dependencies:** [tools needed, files needed, approvals needed]
- **Status:** QUEUED
```

When the agent completes a task, move it to Completed — Pending Review:

```markdown
### TASK-[NNN]: [short title]
- **Added:** [date + time]
- **Completed:** [date + time]
- **Status:** COMPLETE — PENDING REVIEW
- **Output location:** [file path or "inline below"]
- **Output summary:** [2-3 sentence summary of what was produced]
- **Research receipt:** [collapsed receipt — see Research Receipts section below]
- **Self-score:** [X/10 from quality-rubrics.md]
- **Review action needed:** [what the buyer needs to do — approve, edit, reject]
```

#### Queue Processing Rules

1. **Adding tasks:** Buyer says "queue: build a prospect list of 50 SaaS founders in Austin" → agent creates TASK entry, confirms: "Queued as TASK-001: Austin SaaS founders list. I'll work it and flag you when it's ready for review."
2. **Priority:** High-priority tasks run before normal. Multiple tasks at the same priority run in the order they were added.
3. **Background execution:** When the buyer gives the agent a task and doesn't need to wait, the agent works the queue. When the buyer is actively working with the agent on something else, queue tasks wait.
4. **Completion notification:** When a task finishes, the agent surfaces it at the next natural break: "TASK-001 complete — Austin SaaS founders list ready for review in task-queue.md."
5. **Approval flow:** Buyer reviews the output (at the file path listed, or inline). Says "approve TASK-001" → moves to Approved. Says "reject TASK-001: need more companies" → moves to Rejected with reason, agent can re-queue a revised version.
6. **Stale tasks:** Any task in Active for more than 3 sessions without progress gets flagged: "TASK-[NNN] has been queued for [X] sessions. Still want this done?"
7. **Size limits:** Max 10 active tasks. If the buyer tries to add an 11th, surface: "Queue is full (10 active). Approve, reject, or remove a task first."

---

## Research Receipts

Every output the agent produces — email draft, demo cheat sheet, cold call script, CRM note, prospect list — includes a research receipt appended below the output. The receipt is the agent's proof of work.

### Receipt Format

```
---
RESEARCH RECEIPT: [output type] for [prospect/company name]
Gate: [which gate ran — Pre-Draft / Demo Prep / Post-Demo / Cold Call / LinkedIn / CRM Note]
Time: [timestamp]

Sources consulted:
  [x] Vault: brain/prospects/[file] — [what was found or "no existing note"]
  [x] PATTERNS.md — [best angle, avoid angle, confidence tier]
  [x] NotebookLM — [notebook queried, what was returned]
  [x] LinkedIn — [profile visited, key detail extracted]
  [x] Company website — [URL visited, what was learned]
  [x] Apollo — [data points returned or "skipped — vault had data"]
  [x] Fireflies — [transcript found/not found, key quotes if found]
  [x] Gmail — [prior threads found/not found]
  [x] Lessons archive — [categories searched, hits or none]
  [ ] [Any source NOT consulted — with reason: "not applicable" or "tool failed — see fallback"]

Used in output:
  - [Source]: [specific data point that made it into the draft]
  - [Source]: [specific data point that made it into the draft]

Ignored (consulted but not used):
  - [Source]: [what was found but not relevant — and why]

Confidence: [PROVEN / EMERGING / HYPOTHESIS / INSUFFICIENT — from PATTERNS.md for this persona]
Self-score: [X/10] — [rubric type from quality-rubrics.md]
---
```

### Receipt Rules

1. **Every output gets a receipt.** No exceptions. If the agent produces an output without a receipt, the audit system flags it as a process violation.
2. **Collapsed by default.** Present the receipt after the output, visually separated. The buyer can read it in 10 seconds (scan the checkmarks) or dig into details if they want to audit.
3. **Feeds the audit system.** The receipt IS the evidence of gate completion. During wrap-up, the auditor checks receipts instead of trusting self-reported compliance. A receipt with unchecked boxes that aren't explained is an automatic flag.
4. **Feeds the learning loop.** The "Ignored" section is valuable data — it shows what research was done but didn't make it into the output. Over time, if a source is consistently ignored, it may not be worth consulting for that output type.
5. **Honest reporting.** If a source was skipped (tool failed, not applicable, buyer said skip it), mark it [ ] with the reason. Never mark [x] for a source that wasn't actually consulted.

---

## Post-Generation: What to Show the Buyer

After generating all 4 files, show this summary:

```
Setup complete. Here's what I created:

1. company.md — Your company profile, writing rules, and tool inventory.
   This loads every session so I know who you are and how you work.

2. context-manifest.md — Controls what I load and when. Your identity and
   priorities load immediately. Everything else loads only when you need it.
   This keeps sessions fast and focused.

3. .agentignore — Files I'll never read (archives, old sessions, credentials).
   Edit this anytime to add or remove exclusions.

4. task-queue.md — Your task queue. Say "queue: [task]" to add work.
   I'll complete it and flag you for review.

Ready to start. What's first?
```

Do not explain the architecture. Do not mention tiers, CARL, gates, or tokens. The buyer just needs to know: here are your 4 files, here's what they do, let's go.

---

## CLAUDE.md Startup Replacement

When this onboarding completes, the CLAUDE.md `## Session Startup` section should be updated to:

```markdown
## Session Startup — DO THIS FIRST
1. Read context-manifest.md. Follow its loading tiers exactly.
2. Check .agentignore before reading any file not in the manifest.
3. Check task-queue.md for completed tasks pending review.
4. Run Tier 0 loads, then Tier 1 checks in parallel.
5. Present startup status. Respond to buyer's first message.
```

This replaces the current 7-step startup sequence. The manifest IS the startup sequence now. The old skills/session-start/SKILL.md phases are superseded by the manifest tiers — but the skill file can remain as documentation of the loading logic for agent reference.

---

## Reconciliation Protocol (for migrations from existing setup)

When onboarding a buyer who already has a CLAUDE.md with a startup sequence (i.e., this SDK is being installed into an existing project), run this reconciliation:

### Step 1: Inventory

Read the existing CLAUDE.md startup section. List every file and action it references.

### Step 2: Map

For each file/action, assign it to a manifest tier:
- If it's identity/rules/state → Tier 0
- If it's a scan/check/API call → Tier 1
- If it's task-specific → Tier 2
- If it's archived/excluded → Tier 3 (.agentignore)

### Step 3: Conflict Check

Verify:
- [ ] No file appears in more than one tier
- [ ] No file is in both context-manifest.md and .agentignore
- [ ] Tier 0 total is under 8k tokens
- [ ] Every file from the old startup is accounted for (none dropped silently)
- [ ] The old startup section in CLAUDE.md is replaced, not appended to

### Step 4: Reconciliation Note

Append to context-manifest.md under `## Reconciliation Log`:

```markdown
### Migration from [previous setup description]
- **Date:** [today]
- **Files moved startup → on-demand:** [list with reasons]
- **Files staying at startup:** [list]
- **Files added to .agentignore:** [list]
- **Files removed entirely:** [list with reasons — should be empty unless deprecated]
- **Double-load check:** PASSED — no file appears in multiple tiers
- **Token budget check:** Tier 0 = [X]k tokens — [PASS if under 8k / FLAG if over]
```

### Step 5: Verify

After writing context-manifest.md and updating CLAUDE.md:
1. Simulate a startup by listing what would load in order
2. Confirm the total matches the manifest
3. Confirm nothing loads that isn't in the manifest
4. Confirm nothing in .agentignore loads

This is a one-time migration step. Once reconciled, the manifest is the authority going forward.
