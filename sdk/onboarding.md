# SDK Onboarding Flow

> This script runs on first session with a new user. It replaces all domain-specific
> content by asking 5 questions and generating 4 configured files.
> Works for any knowledge worker — not just sales.

---

## Setup vs Working Sessions

**Setup sessions** are when you configure the system — answer onboarding questions, adjust rules, add workflows, tune quality checks. The system doesn't learn during setup. It's scaffolding.

**Working sessions** are when you do your actual job with the agent. Write a report, prepare for a client meeting, review a deliverable, respond to a request. This is when the system learns. Every working session feeds the learning loop — corrections become rules, patterns become workflows, quality scores calibrate to your standards.

Most users need 1-2 setup sessions. After that, every session should be a working session. The system gets better from work, not from configuration. If you find yourself spending more time configuring than working, something is wrong.

**The compounding model:** Session 1 is the worst the system will ever be. By session 5, it knows your common tasks and quality bar. By session 15, it anticipates your corrections before you make them. By session 30, it handles routine work at your standard without intervention. But this only happens through working sessions — the system learns from your actual work, not from hypothetical rules.

---

## The Five Questions

### Q1: "What do you do?"

**Prompt:** "Describe your role in one sentence — your title, your company or practice, and what you spend most of your time on."

**Examples:**
- "I'm a recruiter at a staffing firm, filling mid-level tech roles."
- "I'm a tax advisor with 40 small business clients."
- "I'm a media buyer managing 12 e-commerce accounts."
- "I'm a freelance copywriter doing landing pages and email sequences."
- "I'm a financial advisor at a wealth management firm."

**Generates:**
- `company.md` — company/practice name, industry, size (extracted from answer)
- CLAUDE.md header — role title, domain tag (replaces `<!-- DOMAIN: sales -->`)
- CARL domain seed — determines which starter domain template loads

**Extraction logic:**
- Parse role title (noun phrase after "I'm a/an")
- Parse company/practice name (after "at" or implied)
- Parse industry from context clues
- Parse primary activity (after "doing" / "managing" / "filling" / verb phrase)
- If ambiguous, ask one clarifying follow-up

---

### Q2: "What's the one task you do most often that still requires judgment every time?"

**Prompt:** "Think about the task you do every week — maybe every day — that you can't just autopilot through. The one where quality matters and shortcuts show."

**Examples:**
- "Writing candidate outreach emails that actually get responses."
- "Preparing client tax summaries before quarterly meetings."
- "Building campaign briefs for new product launches."
- "Reviewing contracts for risk clauses before sending to clients."
- "Writing session notes after therapy appointments."

**Generates:**
- `task-queue.md` — primary workflow seeded as the default task type
- First gate in gates.md — research → checkpoint → approval → output for this task
- First CARL domain file — rules specific to this task type

**Extraction logic:**
- Identify the task type (writing, reviewing, preparing, building, analyzing)
- Identify the output artifact (email, report, brief, contract, notes)
- Identify the quality dimension (responses, accuracy, completeness, risk coverage)
- Map to gate template: what research precedes this task? What must be checked?

---

### Q3: "Who do you do this work for — and what do they care about most?"

**Prompt:** "Who sees your output? A client, a hiring manager, a patient, a team? And what's the one thing they'd complain about if you got it wrong?"

**Examples:**
- "Hiring managers who want speed and culture fit."
- "Small business owners who want to pay less tax legally."
- "CMOs who want provable ROAS on every dollar."
- "Opposing counsel who will catch any error in my filings."
- "Patients who need to feel heard, not rushed."

**Generates:**
- `soul.md` — voice rules calibrated to audience expectations
  - Formality level (from audience type)
  - Optimization target (from "what they care about")
  - Tone constraints (professional, empathetic, direct, etc.)
- Quality rubric dimensions — what "good" means for this audience
- Self-check criteria — audience-aware verification before output

**Extraction logic:**
- Identify audience type (client, manager, patient, peer, opposing party)
- Identify primary quality dimension (speed, accuracy, empathy, thoroughness)
- Map formality: client/opposing counsel = formal, team/peer = direct, patient = warm
- Map self-check: "what would [audience] complain about?" becomes the top rubric dimension

---

### Q4: "What's one mistake you've seen in your field that makes you cringe?"

**Prompt:** "The kind of error that makes you think 'how did that get past someone?' Not a typo — a judgment failure."

**Examples:**
- "Sending a candidate to the wrong company because nobody checked the brief."
- "Missing a deduction because you didn't ask the right question."
- "Recommending ad spend without looking at historical performance."
- "Filing a motion with the wrong court's formatting rules."
- "Copy-pasting a template and leaving another client's name in it."

**Generates:**
- First 3 lessons in `lessons.md` — derived from the cringe error + its inverse
  - Lesson 1: The error itself as a hard constraint ("Never [X] without [Y]")
  - Lesson 2: The verification step that prevents it ("Before [output], check [source]")
  - Lesson 3: The quality signal that catches it ("If [indicator], stop and verify")
- Truth protocol emphasis areas — what claims require verification in this domain
- Hard constraints in CARL global — the "never do this" rules

**Extraction logic:**
- Identify the failure mode (wrong data, missing step, copy error, assumption)
- Identify the prevention mechanism (check, verify, confirm, ask)
- Identify the detection signal (what would tip you off that this happened?)
- Generate inverse rules: error → prevention lesson → detection lesson → constraint

---

### Q5: "What tools do you already use daily?"

**Prompt:** "List the 3-5 tools you open every workday. Email, CRM, project management, spreadsheets, whatever you actually use."

**Examples:**
- "LinkedIn Recruiter, Greenhouse, Gmail, Slack."
- "Drake, QuickBooks, Outlook, Excel."
- "Meta Ads Manager, Google Sheets, Slack, Figma."
- "Clio, Outlook, Westlaw, Teams."
- "SimplePractice, Google Calendar, Zoom."

**Generates:**
- `.agentignore` — excludes irrelevant tool configs + OS artifacts
- `context-manifest.md` Tier 2 entries — tool-specific workflows load on demand
- Fallback chain seeds — what to try when primary tool fails

**Extraction logic:**
- Match tool names to known categories (email, CRM, calendar, research, messaging)
- For each tool: is there an MCP connector? If yes, add to Tier 2 with trigger intent
- For tools without connectors: add to "manual reference" in context-manifest
- Generate .agentignore: exclude all tool config directories NOT in the user's list
- Seed fallback chains: email tool fails → try web → try manual draft

---

## Output Files

After all 5 questions are answered, generate these 4 files:

### 1. company.md
```
# [Company/Practice Name]
Industry: [extracted from Q1]
Size: [extracted from Q1, or "ask" if unclear]
Domain: [tag derived from Q1 — e.g., recruiting, tax, media-buying, legal, therapy]
Primary role: [title from Q1]
Primary task: [from Q2]
Audience: [from Q3]
Quality priority: [from Q3 — what audience cares about most]
```

### 2. soul.md
```
# Agent Voice & Working Identity

## Tone
[Derived from Q3 audience type — formality, warmth, directness]

## Quality Bar
[Derived from Q3 + Q4 — what good looks like, what bad looks like]

## Hard Constraints
[Derived from Q4 — the "never do this" rules]

## Output Standards
[Derived from Q2 — what the primary task output should look like]
```

### 3. .agentignore
```
# OS artifacts
.DS_Store
Thumbs.db
desktop.ini

# Tool configs not in user's stack
[Generated from Q5 — exclude everything not listed]

# Archive and cold storage
archive/*
*.bak
```

### 4. task-queue.md
```
# Task Queue

## Primary Workflow: [from Q2]
Gate: [auto-generated from Q2 extraction]
Tools: [from Q5]
Quality check: [from Q3 + Q4]

## Queue
[Empty — populated through working sessions]
```

---

## Post-Onboarding

After generating files, display:

> **Setup complete.** Your system is configured for [role] at [company].
>
> Your primary workflow ([task from Q2]) has a quality gate. Your quality bar
> is calibrated to [audience from Q3]. Your hard constraints reflect [error from Q4].
>
> This was a setup session. The system starts learning in your next session —
> when you do real work. Every correction you give makes it smarter.
> By session 5, it knows your patterns. By session 30, it handles routine
> work at your standard.
>
> To get started: just tell me what you need to do today.

---

## Step 6: Initialize the Vault

After generating the four config files, create the brain/ directory structure so the
compounding loop has somewhere to write from session one. All directories empty except
for template and seed files.

```
brain/
├── prospects/
│   └── _TEMPLATE.md          # Prospect/client note template (domain-agnostic)
├── pipeline/
│   └── .gitkeep
├── emails/
│   └── PATTERNS.md           # Empty pattern tables with column headers only
├── personas/
│   └── .gitkeep
├── signals.md                 # Empty signal log with column headers
├── forecasting.md             # Empty health/tracking table with column headers
├── system-patterns.md         # Compound brain status + empty tracking tables
├── loop-state.md              # "Session 0: onboarding complete. First working session next."
└── VERSION.md                 # v0.1.0
```

### Why this matters

Without these directories and seed files, the first working session can't write notes,
log patterns, or update the handoff. The compounding loop breaks before it starts.
Initializing the vault at onboarding means session 1 is a full working session — no
scaffolding delay.

### Template content

**_TEMPLATE.md** (domain-agnostic — no sales fields):
```markdown
# [Name]
Company: [company]
Role: [role]
Source: [how they entered your workflow]
Created: [date]

## Context
[What you know about this person and their situation]

## Interactions
<!-- Append each interaction with date, type, and outcome -->

## Quality Notes
<!-- What matters to this person. What to check before any output involving them. -->
```

**PATTERNS.md** (empty seed):
```markdown
# Pattern Library
> Tracks what works and what doesn't across all interactions.
> Updated at session wrap-up. Read before any task that matches a known pattern.

## By Task Type
| Task | Approach | Times Used | Success Rate | Confidence |
|------|----------|-----------|-------------|------------|

## Negative Patterns (approaches that failed)
| Task | Approach | Times Failed | Failure Mode | Confidence |
|------|----------|-------------|-------------|------------|
```

**loop-state.md** (initial):
```markdown
# Loop State — Session 0 Close
Date: [onboarding date]

## What Changed
- Onboarding complete. Four config files generated. Vault initialized.

## Due Next Session
- First working session. System will begin learning from real tasks.

## Compound Brain Status
0/5 active. The system is new. Start working to build patterns.
```
