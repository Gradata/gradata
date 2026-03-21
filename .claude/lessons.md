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
| 1 | DRAFTING | Don't open with "I hope this email finds you well" | 3/18 |
| 2 | LANGUAGE | No em dashes in emails | 3/18 |
| 3 | LANGUAGE | Banned words list (genuinely, straightforward, etc.) | 3/18 |
| 4 | CTA | Always use Calendly link, never mention duration | 3/18 |
| 5 | FORMAT | Hyperlink Sprites.ai to spritesai.com | 3/18 |
| 6 | TONE | 5-8 sentences, under 150 words | 3/18 |
| 7 | RESEARCH | Check Pipedrive before asking Oliver | 3/18 |
| 8 | RESEARCH | Check vault before external tools | 3/18 |
| 9 | CRM | Oliver-tagged deals only (label 45) | 3/18 |
| 10 | CRM | Never update deal value/pricing | 3/18 |
| 11 | PROCESS | Save to Sprites Work, not Desktop | 3/18 |
| 12 | PROCESS | Gmail drafts as HTML always | 3/18 |
| 13 | STRATEGY | CCQ for cold, Gap Selling for current→future | 3/18 |
| 14 | STRATEGY | Inbound = "Welcome to Sprites, [First]" | 3/18 |
| 15 | STRATEGY | Follow-up = their words first, then referral ask | 3/18 |
| 16 | TONE | "Hi [First Name]," opening always | 3/18 |
| 17 | ACCURACY | Never list pending items from memory, verify | 3/18 |
| 18 | ACCURACY | Never double-dip enrichment | 3/18 |
| 19 | ICP | Multi-brand ecom, PE rollups, franchise, agencies | 3/18 |
| 20 | ICP | 10-300 employees, Meta Pixel and/or Google Ads | 3/18 |
| 21 | PROCESS | Log to lessons/vault/daily notes without asking | 3/18 |
| 22 | PROCESS | Oliver approves copy → straight to Gmail draft | 3/18 |
| 23 | SIGNATURE | Best, Oliver Le, AE Sprites.ai | 3/18 |
| 24 | TOOL | Fireflies search by attendee email + name + company | 3/18 |
| 25 | TOOL | Calendar check 2 months out before any task | 3/18 |
| 26 | ACCURACY | Never assume team size/role scope. Verify on LinkedIn | 3/19 |
| 27 | STRATEGY | Never disqualify website visitors regardless of size | 3/19 |
| 28 | KNOWLEDGE | Oliver shares Apollo account with Siamak | 3/19 |
| 29 | DRAFTING | Discovery Qs = TRAP sections in threads, not separate | 3/19 |
| 30 | STRATEGY | Don't re-pitch rejected pricing. Lead with alternatives | 3/19 |
| 31 | LANGUAGE | "The way I'd frame it" sounds AI. Write human | 3/19 |
| 32 | LANGUAGE | "Replicate" implies stealing. Say "build from scratch" | 3/19 |
| 33 | ACCURACY | Build cost $500K-$1M+, not $68K. Be credible | 3/19 |
| 34 | ACCURACY | Fact-check claims from transcript. Don't inflate | 3/19 |
| 35 | CRM | Pipedrive has no probability field. Skip in API | 3/19 |
| 36 | TECHNICAL | Subagents use RUBE_MULTI_EXECUTE_TOOL | 3/19 |
| 37 | STRATEGY | White label = alternative revenue angle for agencies | 3/19 |
| 38 | STRATEGY | Next steps start with prospect's decision first | 3/19 |
| 39 | REFERRALS | Include referral ask + fee in post-demo follow-ups | 3/19 |
| 40 | DRAFTING | Inbound paywall emails — graceful, not condescending | 3/19 |
| 41 | LANGUAGE | Don't repeat their resume. Make it about their pain | 3/19 |
| 42 | VAULT | Brain compounds. Read before research, write at wrap-up | 3/19 |
| 43 | STARTUP | Check Gmail/Fireflies/Calendar before anything else | 3/19 |
| 44 | PARALLEL | 3+ independent items → parallel agents | 3/19 |
| 45 | CORRECTION | Day 1-2 follow-ups too needy. Earliest Day 3 | 3/19 |
| 46 | CORRECTION | Fact-check Gmail sent before claiming email not sent | 3/19 |
| 47 | FORMAT | Email drafts use <p> tags, not <br> between sentences | 3/19 |
| 48 | STRATEGY | Instantly READ-ONLY. All outbound via Gmail | 3/19 |
| 49 | CORRECTION | Gmail thread matching: most recent sent to:[email] | 3/19 |
| 50 | PROCESS | Capture full strategic vision immediately. No abbreviation | 3/19 |
| 51 | TONE | Condescending "fix that" → "happy to open that up" | 3/20 |
| 52 | HONESTY | Don't claim Oliver watched/listened to something | 3/20 |
| 53 | FLOW | Bridge sentence connecting prospect to case study | 3/20 |
| 54 | COST | Free tools before paid (baked into fallback-chains) | 3/20 |
| 55 | COST | State cost and ask before any paid tool | 3/20 |
| 56 | LEADS | Filter before enrichment (baked into SOP) | 3/20 |
| 57 | TONE | Don't re-pitch after close — operational only | 3/20 |
| 58 | FORMAT | Numbered lists for sequential action items | 3/20 |
| 59 | DETAIL | Practical prep instructions in onboarding emails | 3/20 |
| 60 | STYLE | Imperative verbs, not gerunds — Oliver's style | 3/20 |
| 61 | DRAFTING | Specific subject lines, not generic "Good chatting" | 3/20 |
| 62 | DRAFTING | Full omnichannel scope in Sprites pitch | 3/20 |
| 63 | DEMO PREP | Fireflies is post-demo only, not pre-demo | 3/20 |
| 64 | PROCESS | Brain/NLM mandatory (LOOP_RULE_43) | 3/20 |
| 65 | PROCESS | Pre-flight mandatory (LOOP_RULE_44) | 3/20 |
| 66 | AUDIT | Never log FAIL — keep fix-cycling to 8.0+ | 3/20 |
| 67 | SIGNATURE | Spell out "Account Executive" not "AE" in email signatures | 3/20 |
| 68 | CRM | Pipedrive notes = clean prospect intel only. No AI/tool citations, no methodology names, no book refs. Detail goes in cheat sheet/draft | 3/20 |
| 69 | DEMO PREP | Research FIRST (LinkedIn, NotebookLM, web), push to Pipedrive LAST. Tag Oliver label on deals | 3/20 |
| 70 | DEMO PREP | Use ALL sales playbooks before building cheat sheet (Great Demo, SPIN, Gap, JOLT, etc.) | 3/20 |

## Active Lessons (18 entries — cap: 30)

[2026-03-19] [CONFIRMED — ZERO FIRE] LEADS: Never label leads "needs manual review." If you have their title and company from LinkedIn, you can score them programmatically. No lazy buckets.

[2026-03-19] [CONFIRMED — ZERO FIRE] LEADS: Run the filter ONCE comprehensively. Don't iterate 3 times because each pass was incomplete. One pass with full keyword lists from the start.

[2026-03-19] [CONFIRMED — ZERO FIRE] PROCESS: When Oliver says "filter" or "clean this list," execute the full lead-filtering-sop.md and show results. Don't ask permission at each step.

[2026-03-19] [CONFIRMED — ZERO FIRE] PROCESS: Check Gmail sent folder before listing "active items." Verify before presenting status — don't list drafts as pending when Oliver already sent them.

[2026-03-19] [CONFIRMED — ZERO FIRE] LEADS: Build comprehensive keyword lists ONCE up front. Pre-build the full list before first pass, not through iterative discovery.

[2026-03-19] [CONFIRMED — ZERO FIRE] LEADS: Dedup across ALL wip files at the START of any lead work, not when Oliver asks.

[2026-03-19] [CONFIRMED — ZERO FIRE] PROCESS: CC relevant team members (Siamak) on deal emails. Team visibility on active deals.

[2026-03-19] [CONFIRMED — ZERO FIRE] PIPEDRIVE: Deal titles use company name ONLY (e.g., "Cosprite"), not "Cosprite - Matt Rajcok". Person name already linked via person_id.

[2026-03-19] [CONFIRMED — ZERO FIRE] PIPEDRIVE: ALWAYS schedule a next activity when creating a deal. Check calendar 1 month out first, then log the activity. No deal should ever have the warning icon.

[2026-03-19] [CONFIRMED — ZERO FIRE] ACCURACY: Never guess email addresses. Always verify from Apollo contacts (free search), Pipedrive, or Gmail before creating a draft.

[2026-03-19] [CONFIRMED — ZERO FIRE] DEMO PREP: The cheat sheet is NOT a research doc. It's a battle card Oliver reads mid-demo. Sequential PHASES with TRAP → assumed answer → QUANTIFY → TRANSITION → thread link → land value. Include "IF YOU PANIC" box. Two drafts: (1) research doc, (2) clean cheat sheet.

[2026-03-19] [CONFIRMED — ZERO FIRE] DEMO PREP: After the trap springs and they admit pain, QUANTIFY before showing the thread. Turn "hours" into "260 hours/year." The number makes them lean in.

[2026-03-19] [CONFIRMED — ZERO FIRE] DEMO PREP: Full 12-step research process: Calendar, company search, person search, Apollo+recordings, deeper person, leadership, homepage+tech, Gmail threads, Gmail read, personal site, synthesize into demo flow with thread links + methodology + disco Qs + objections + close.

[2026-03-20] [PROVISIONAL:5] DRAFTING: Use a lead-in line before bullet lists in emails ("On that call we cover:"). Gives the list context and makes it scannable. Don't drop bullets inline without framing.

[2026-03-20] [PROVISIONAL:5] DRAFTING: One idea per bullet. Don't combine multiple concepts into a single bullet point. Each bullet should land one clear point.

[2026-03-20] [PROVISIONAL:5] DRAFTING: When referencing case studies in emails, ATTACH the actual document. Don't just name-drop results. Gives the prospect something tangible to forward to their team for internal buy-in.

[2026-03-20] [PROVISIONAL:5] FOLLOW-UP: No referral ask until close-won + onboarding. Referral requests in post-demo follow-ups are premature. Save for the welcome/customer success email.

[2026-03-20] [PROVISIONAL:5] APIFY: Always use `harvestapi/linkedin-profile-scraper` for LinkedIn profile scraping (NOT supreme_coder). Input format: `{"queries": ["url1", "url2"]}`. Supreme_coder works but is way too slow (~28min/500 vs ~5min/500). Cost: $0.004/profile for harvestapi.

[2026-03-20] [PROVISIONAL:5] LEADS: Scripts that write CSVs to active/ AND read from active/ for dedup will dedup against their own previous output on reruns. Always clean the output directory BEFORE the dedup scan, not after. process-claude-ads-leads.py had this bug — fixed by moving cleanup to before the URL scan.

[2026-03-20] [PROVISIONAL:5] WRAP-UP: Step 6 (health audit) is a SEPARATE check from step 8 (quality audit). Step 6 covers files/vault/MCPs/credits/process/data. Step 8 covers session scoring. Don't collapse them. The parallelized wrap-up gate must list ALL mandatory steps explicitly — steps 0.5, 1, 6, 7, 8, 9, 9.5, 10.

[2026-03-20] [PROVISIONAL:5] SIGNATURE: Spell out "Account Executive" in email signatures, not "AE". Full title reads more professional in prospect-facing emails.

[2026-03-20] [PROVISIONAL:5] ACCURACY: Don't inflate self-scores on systems-only sessions. No prospect work = no real gates fired, no real outputs judged. Untested infrastructure doesn't earn 8.5+. Cap systems-only sessions at 8.0 unless Oliver says otherwise.
