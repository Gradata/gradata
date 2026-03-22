# Lessons Learned
# Format: [DATE] [STATUS] CATEGORY: What happened → What to do instead
# Status tags: [PROVISIONAL:N] = N sessions of probation remaining | [CONFIRMED] = survived probation
# Graduated lessons → lessons-archive.md (66 graduated through 3/20)
# Before ANY drafting task, search lessons-archive.md for relevant categories.
#
# Shadow Mode: New lessons can use [SHADOW:0/3] instead of immediate activation.
# Shadow lessons track what WOULD have been different, without changing output.
# After 3 shadow occurrences: promote to active or kill. See auditor-system.md.
#
# Wrap-up: decrement all [PROVISIONAL:N] counters. Delete any with reversal flag. Promote [PROVISIONAL:0] to [CONFIRMED].
# CONFIRMATION LOOP: First 3 times a lesson's category comes up in live work, ask Oliver: "Did [lesson] hold?"
# After 3 confirmed holds: graduate automatically. If Oliver says no: flag [INEFFECTIVE], rewrite the rule.
# Format: [CONFIRM:0/3] after promotion to [CONFIRMED]. Tracks holds, not just time.
# Format for new lessons: [DATE] [PROVISIONAL:5] CATEGORY: What happened → What to do instead. Root cause: [what systemic gap allowed this]
# Root cause is MANDATORY on every new lesson — it feeds the double-loop in /reflect.
# Effectiveness: New lessons start with [TRACK:0/3]. After each scenario occurrence, increment and log Y/N.
# Format: [TRACK:hits/3:YYN] where Y=prevented, N=repeated. At 3 hits: 2+Y=[EFFECTIVE], 2+N=[REWRITE NEEDED].
# If 20+ sessions pass with 0 hits: mark [UNTESTABLE].
#
# GRADUATION CYCLE LOG:
# Session 9 (2026-03-20): First cycle. 33 active → 13 active. 16 retired (redundant with soul.md/CARL/gates).
# 4 reclassified (knowledge → reference). 13 kept as [CONFIRMED — ZERO FIRE] (no pipeline sessions to test).

## Graduated Lessons Index (search archive for full context)
<!-- 1-line summaries. If a topic matches your current task, read the full lesson from lessons-archive.md -->
| # | Category | Topic | Graduated |
|---|----------|-------|-----------|
| # | Category | Topic | Graduated |
|---|----------|-------|-----------|
| 1 | DRAFTING | No generic openers or subject lines. Be specific to their situation. | 3/18 → merged 3/21 (#1+#61) |
| 4 | CTA | Always use Calendly link, never mention duration | 3/18 |
| 5 | FORMAT | Hyperlink Sprites.ai to spritesai.com | 3/18 |
| 6 | TONE | 5-8 sentences, under 150 words | 3/18 |
| 7 | RESEARCH | Research internal sources first (vault, Pipedrive, Gmail), then external tools + NotebookLM. Only ask Oliver when it requires costs. | 3/18 → merged 3/21 (#7+#8+#54+#55) |
| 9 | CRM | Oliver-tagged deals only (label 45) | 3/18 |
| 10 | CRM | Never update deal value/pricing | 3/18 |
| 11 | PROCESS | Save to Sprites Work, not Desktop | 3/18 |
| 12 | PROCESS | Gmail drafts as HTML always | 3/18 |
| 13 | STRATEGY | CCQ for cold, Gap Selling for current→future | 3/18 |
| 14 | STRATEGY | Inbound = "Welcome to Sprites, [First]" | 3/18 |
| 15 | STRATEGY | Follow-up = their words first. Referral ask only after close-won/onboarding OR as last breakup email | 3/18 → compounded 3/21 (#15+#39) |
| 16 | TONE | "Hi [First Name]," opening always | 3/18 |
| 17 | ACCURACY | Never list pending items from memory, verify | 3/18 |
| 18 | ACCURACY | Never double-dip enrichment | 3/18 |
| 19 | ICP | Multi-brand ecom, PE rollups, franchise, agencies | 3/18 |
| 20 | ICP | 10-300 employees, Meta Pixel and/or Google Ads | 3/18 |
| 21 | PROCESS | Log to lessons/vault/daily notes without asking | 3/18 |
| 22 | PROCESS | Oliver approves copy → straight to Gmail draft | 3/18 |
| 23 | SIGNATURE | Best, Oliver Le, Account Executive, Sprites.ai | 3/18 → compounded 3/21 (#23+#67) |
| 24 | TOOL | Fireflies search by attendee email + name + company | 3/18 |
| 25 | TOOL | Calendar check 2 months out before any task | 3/18 |
| 26 | ACCURACY | Never assume team size/role scope. Verify on LinkedIn | 3/19 |
| 27 | STRATEGY | Never disqualify website visitors regardless of size | 3/19 |
| 28 | KNOWLEDGE | Oliver shares Apollo account with Siamak | 3/19 |
| 29 | DRAFTING | Discovery Qs = TRAP sections in threads, not separate | 3/19 |
| 30 | STRATEGY | Don't re-pitch rejected pricing. Lead with alternatives | 3/19 |
| 33 | ACCURACY | Build cost $500K-$1M+, not $68K. Be credible | 3/19 |
| 34 | ACCURACY | Fact-check claims from transcript. Don't inflate | 3/19 |
| 35 | CRM | Pipedrive has no probability field. Skip in API | 3/19 |
| 36 | TECHNICAL | Subagents use RUBE_MULTI_EXECUTE_TOOL | 3/19 |
| 37 | STRATEGY | White label = alternative revenue angle for agencies | 3/19 |
| 38 | STRATEGY | Next steps start with prospect's decision first | 3/19 |
| 40 | DRAFTING | Inbound paywall emails — graceful, not condescending | 3/19 |
| 41 | LANGUAGE | Don't repeat their resume. Make it about their pain | 3/19 |
| 42 | VAULT | Brain compounds. Read before research, write at wrap-up | 3/19 |
| 45 | CORRECTION | Day 1-2 follow-ups too needy. Earliest Day 3 | 3/19 |
| 47 | FORMAT | Email drafts use <p> tags, not <br> between sentences | 3/19 |
| 48 | STRATEGY | Instantly READ-ONLY. All outbound via Gmail | 3/19 |
| 49 | CORRECTION | Gmail thread matching: most recent sent to:[email] | 3/19 |
| 50 | PROCESS | Capture full strategic vision immediately. No abbreviation | 3/19 |
| 51 | TONE | Condescending "fix that" → "happy to open that up" | 3/20 |
| 52 | HONESTY | Don't claim Oliver watched/listened to something | 3/20 |
| 53 | FLOW | Bridge sentence connecting prospect to case study | 3/20 |
| 56 | LEADS | Filter before enrichment (baked into SOP) | 3/20 |
| 57 | TONE | Don't re-pitch after close — operational only | 3/20 |
| 58 | FORMAT | Numbered lists for sequential action items | 3/20 |
| 59 | DETAIL | Practical prep instructions in onboarding emails | 3/20 |
| 60 | STYLE | Imperative verbs, not gerunds — Oliver's style | 3/20 |
| 62 | DRAFTING | Full omnichannel scope in Sprites pitch | 3/20 |
| 63 | DEMO PREP | Fireflies is post-demo only, not pre-demo | 3/20 |
| 68 | CRM | Pipedrive notes = clean prospect intel only. No AI/tool citations, no methodology names, no book refs | 3/20 |
| 69 | DEMO PREP | Research FIRST (LinkedIn, NotebookLM, web), push to Pipedrive LAST | 3/20 → updated 3/21 |
| 70 | DEMO PREP | Use ALL sales playbooks before building cheat sheet (Great Demo, SPIN, Gap, JOLT, etc.) | 3/20 |

## Active Lessons (21 entries — cap: 30)

### ZERO FIRE — Consolidated (awaiting first pipeline session to test)

[2026-03-19] [CONFIRMED — ZERO FIRE] LEADS: Do lead filtering in one complete pass with full criteria. Build keyword lists up front, dedup across ALL wip files at the START, score programmatically (no "needs manual review" buckets). When Oliver says "filter" — execute the full SOP and show results, don't ask permission at each step.

[2026-03-19] [CONFIRMED — ZERO FIRE] PROCESS: CC relevant team members (Siamak) on deal emails. Team visibility on active deals.

[2026-03-19] [CONFIRMED — ZERO FIRE] PIPEDRIVE: Deal titles use company name ONLY (e.g., "Cosprite"), not "Cosprite - Matt Rajcok". Person name already linked via person_id.

[2026-03-19] [CONFIRMED — ZERO FIRE] PIPEDRIVE: ALWAYS schedule a next activity when creating a deal. Check calendar 1 month out first, then log the activity. No deal should ever have the warning icon.

[2026-03-19] [CONFIRMED — ZERO FIRE] ACCURACY: Never guess email addresses. Always verify from Apollo contacts (free search), Pipedrive, or Gmail before creating a draft.

[2026-03-19] [CONFIRMED — ZERO FIRE] DEMO PREP: Cheat sheet = battle card, NOT research doc. TRAP → QUANTIFY (turn "hours" into "260 hours/year") → TRANSITION → thread link mapped to their specific pain (from cold call or research) → land value. Include "IF YOU PANIC" box. Two drafts: (1) research doc, (2) clean cheat sheet. Full 12-step research process before building.

### PROVISIONAL — Active

[2026-03-20] [CONFIRMED] DRAFTING: Bullet lists need a lead-in line for context ("On that call we cover:"). One idea per bullet — no combining. Attach actual case study documents, don't just name-drop results.

[2026-03-20] [CONFIRMED] APIFY: Always use `harvestapi/linkedin-profile-scraper` for LinkedIn profile scraping (NOT supreme_coder). Input format: `{"queries": ["url1", "url2"]}`. Cost: $0.004/profile for harvestapi.

[2026-03-20] [CONFIRMED] LEADS: Scripts that write CSVs to active/ AND read from active/ for dedup will dedup against their own previous output on reruns. Always clean the output directory BEFORE the dedup scan, not after.

[2026-03-20] [CONFIRMED] ACCURACY: Systems-only sessions use the System/Architecture rubric in quality-rubrics.md, not sales output rubrics. Score against engineering standards, not prospect output quality.

[2026-03-20] [CONFIRMED] PROCESS: startup-brief.md must refresh every session during wrap-up (step 10.5). Never let the pipeline source of truth go stale.

[2026-03-20] [CONFIRMED] ARCHITECTURE: When splitting files, don't keep duplicate definitions. If content moves to domain/, replace the original with a single pointer — not both.

[2026-03-20] [CONFIRMED] COMMUNICATION: When surfacing anomalies or warnings, always explain WHY it matters and confirm whether it's a blocker or cosmetic. Don't leave ambiguity about severity.

[2026-03-21] [CONFIRMED] CRM: When analyzing Pipedrive data, filter out unworked deals (no value, no activity, no org) before drawing conclusions. Only deals with activity, assigned value, and real stage progression count as training data.

[2026-03-21] [CONFIRMED] STRATEGY: Don't conflate cold outreach reply data with close-cycle effectiveness. "Show the tool" gets cold replies. Pain-based selling (Gap, SPIN) closes deals. Different stages need different approaches.

[2026-03-21] [CONFIRMED] ACCURACY: Verify current state before presenting status or recommending changes. Check Gmail sent, source dates, actual workflows — never assume from memory or Pipedrive stage names.

[2026-03-21] [CONFIRMED] ARCHITECTURE: When adding any component, think big picture FIRST — behavior and purpose before file locations and wiring diagrams.

[2026-03-21] [CONFIRMED] PRESENTATION: When presenting calendar/timeline data, always state the current day of week and frame events relative to it. Don't present a grid that implies immediacy when there's a buffer.

[2026-03-21] [CONFIRMED] POSITIONING: Never use "agency pricing" — it implies expensive retainers. Say "fixed monthly subscription" or "flat rate, cancel anytime."

[2026-03-21] [CONFIRMED] DRAFTING: When building email subject lines or cadences, cross-reference BOTH external research (Gong, HubSpot) AND Oliver's playbooks (sales-methodology.txt, templates.txt). Neither source alone is sufficient.

[2026-03-21] [CONFIRMED] PROCESS: Parallelize wrap-up and multi-step tasks using background agents. 3+ independent items → fire concurrently, not sequentially.

[2026-03-21] [CONFIRMED] PROCESS: Don't start building before researching — even when excited about a feature. The design-first check and source-verification gate exist for a reason. Research best practices, prior art, and architecture patterns BEFORE writing code. Root cause: jumped straight to writing snapshot.py without researching how sales activity tracking systems work.

[2026-03-21] [CONFIRMED] ACCURACY: When displaying metrics that mix session types (sales vs system), always filter to the relevant track. Blended numbers (e.g., edit rate diluted by 0-revision system sessions) are misleading. Show the number that matters for the context. Root cause: statusline showed 15% edit rate blending sales (31%) with systems (0%).

[2026-03-22] [PROVISIONAL:1] CONSTRAINT: Before proposing any tool, API, or service, check if it costs money. If yes, flag it and ask -- don't present it as a solution. Default to free. Oliver wants zero-cost infrastructure. Root cause: proposed Composio (paid) and trial-tier APIs (25/month) twice before being corrected. Technical problem-solving instinct overrides constraint awareness.

[2026-03-22] [PROVISIONAL:1] DATA_INTEGRITY: "Oliver only" applies to ALL measurement -- not just deals and contacts, but metrics, delta data, campaign stats, and any aggregate numbers. When pulling data from shared systems (Instantly, Pipedrive, Gmail), always filter by owner. Root cause: included Anna's 84K campaign emails in Oliver's 1.8K reply rate calculation, producing 0.61% instead of 1.01%.

[2026-03-22] [PROVISIONAL:1] PROCESS: Never skip wrap-up steps when rushing. The 8.0 audit gate, provisional decrements, and agent distillation are non-negotiable regardless of session length. Long session = MORE reason to audit, not less. Spawn wrap-up agents instead of skipping. Root cause: 6+ hour session caused fatigue-driven shortcutting on 6 wrap-up steps.

[2026-03-22] [PROVISIONAL:5] CONTEXT: Oliver does prospect work on weekdays, systems work on weekends. Never frame weekend systems sessions as "drift" or imply pipeline is being neglected. Check the day of week before commenting on session type balance. Root cause: lectured Oliver about 6 consecutive non-prospect sessions when it was Saturday — his normal schedule.
