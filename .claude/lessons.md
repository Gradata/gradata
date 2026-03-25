# Lessons Learned
# Format: [DATE] [STATUS] CATEGORY: What happened → What to do instead
# Status tags: [INSTINCT:X.XX] = confidence score (0.0-0.59) | [PATTERN:X.XX] = confirmed (0.60-0.89) | [RULE] = graduated (0.90+)
# Graduated lessons → lessons-archive.md (66 graduated through 3/20)
# Before ANY drafting task, search lessons-archive.md for relevant categories.
#
# Wrap-up: update_confidence() in wrap_up.py handles all scoring. +0.10 per surviving session, -0.15 per correction. 0.60+ promotes to [PATTERN].
# Format for new lessons: [DATE] [INSTINCT:0.30] CATEGORY: What happened → What to do instead. Root cause: [what systemic gap allowed this]
# Root cause is MANDATORY on every new lesson — it feeds the double-loop in /reflect.
# If 20+ sessions pass with 0 hits: mark [UNTESTABLE] and archive.
#
# GRADUATION CYCLE LOG:
# Session 9 (2026-03-20): First cycle. 33 active → 13 active. 16 retired (redundant with soul.md/CARL/gates).
# 4 reclassified (knowledge → reference). 13 kept as [CONFIRMED — ZERO FIRE] (no pipeline sessions to test).
# Session 36 (2026-03-22): Tag migration. 15 [CONFIRMED] → [PATTERN:0.70]. 6 ZERO FIRE → [UNTESTABLE] (25+ sessions, 0 hits). Removed redundant graduated index (archive is canonical). Killed unused SHADOW/TRACK/CONFIRM protocols.

## Active Lessons (13 entries — cap: 30)

### PATTERN — Active (bumped to 0.80: survived 5+ sessions, add specificity beyond existing rules)

[2026-03-20] [PATTERN:0.80] DRAFTING: Bullet lists need a lead-in line for context ("On that call we cover:"). One idea per bullet — no combining. Attach actual case study documents, don't just name-drop results.

[2026-03-20] [PATTERN:0.80] APIFY: Always use `harvestapi/linkedin-profile-scraper` for LinkedIn profile scraping (NOT supreme_coder). Input format: `{"queries": ["url1", "url2"]}`. Cost: $0.004/profile for harvestapi.

[2026-03-20] [PATTERN:0.80] LEADS: Scripts that write CSVs to active/ AND read from active/ for dedup will dedup against their own previous output on reruns. Always clean the output directory BEFORE the dedup scan, not after.

[2026-03-20] [PATTERN:0.80] ARCHITECTURE: When splitting files, don't keep duplicate definitions. If content moves to domain/, replace the original with a single pointer — not both.

[2026-03-20] [PATTERN:0.80] COMMUNICATION: When surfacing anomalies or warnings, always explain WHY it matters and confirm whether it's a blocker or cosmetic. Don't leave ambiguity about severity.

[2026-03-21] [PATTERN:0.80] ACCURACY: Verify current state before presenting status or recommending changes. Check Gmail sent, source dates, actual workflows — never assume from memory or Pipedrive stage names.

[2026-03-21] [PATTERN:0.80] PRESENTATION: When presenting calendar/timeline data, always state the current day of week and frame events relative to it. Don't present a grid that implies immediacy when there's a buffer.

[2026-03-21] [PATTERN:0.80] POSITIONING: Never use "agency pricing" — it implies expensive retainers. Say "fixed monthly subscription" or "flat rate, cancel anytime."

[2026-03-21] [PATTERN:0.80] DRAFTING: When building email subject lines or cadences, cross-reference BOTH external research (Gong, HubSpot) AND Oliver's playbooks (sales-methodology.txt, templates.txt). Neither source alone is sufficient.

[2026-03-21] [PATTERN:0.80] ACCURACY: When displaying metrics that mix session types (sales vs system), always filter to the relevant track. Blended numbers (e.g., edit rate diluted by 0-revision system sessions) are misleading. Show the number that matters for the context. Root cause: statusline showed 15% edit rate blending sales (31%) with systems (0%).

### INSTINCT — New (require root cause, tracking)

[2026-03-22] [INSTINCT:0.59] CONSTRAINT: Before proposing any tool, API, or service, check if it costs money. If yes, flag it and ask -- don't present it as a solution. Default to free. Oliver wants zero-cost infrastructure. Root cause: proposed Composio (paid) and trial-tier APIs (25/month) twice before being corrected. Technical problem-solving instinct overrides constraint awareness.

[2026-03-22] [INSTINCT:0.59] DATA_INTEGRITY: "Oliver only" applies to ALL measurement -- not just deals and contacts, but metrics, delta data, campaign stats, and any aggregate numbers. When pulling data from shared systems (Instantly, Pipedrive, Gmail), always filter by owner. Root cause: included Anna's 84K campaign emails in Oliver's 1.8K reply rate calculation, producing 0.61% instead of 1.01%.

[2026-03-22] [INSTINCT:0.59] PROCESS: Never skip wrap-up steps when rushing. The 8.0 audit gate, confidence updates, and agent distillation are non-negotiable regardless of session length. Long session = MORE reason to audit, not less. Spawn wrap-up agents instead of skipping. Root cause: 6+ hour session caused fatigue-driven shortcutting on 6 wrap-up steps.

[2026-03-22] [INSTINCT:0.40] CONTEXT: Oliver does prospect work on weekdays, systems work on weekends. Never frame weekend systems sessions as "drift" or imply pipeline is being neglected. Check the day of week before commenting on session type balance. Root cause: lectured Oliver about 6 consecutive non-prospect sessions when it was Saturday — his normal schedule.

[2026-03-22] [INSTINCT:0.40] STARTUP: Surface the "Next Session Tasks" from loop-state.md FIRST at startup — before any cleanup, formatting, or system checks. The handoff tells you what to work on. Don't burn 10 minutes on tasks Oliver didn't ask for while ignoring the handoff. Root cause: cleaned up loop-state formatting and chased gate failures instead of surfacing the S37 handoff (integration test, wrap-up agents, judgment decay).

[2026-03-22] [INSTINCT:0.40] THOROUGHNESS: Never recommend "park" or "skip" as a first response to a deferred item. If the work can be done with subagents, do it. If it takes 30 minutes, take the 30 minutes. "Park" is only valid when Oliver explicitly says to defer, or when the task genuinely requires external input (API keys, Oliver's decisions, third-party approvals). Spawning agents is free — laziness is not. Root cause: recommended parking 3 of 6 S34 deferred items to avoid work, then Oliver had to push back twice.

[2026-03-24] [INSTINCT:0.30] DEMO_PREP: Never skip NotebookLM in demo prep regardless of perceived time pressure. Always run all gate steps. "Time-constrained" is not a valid skip reason when the tool takes 30 seconds. Root cause: skipped NotebookLM query and marked it [ ] in pre-flight, Oliver called it out.

[2026-03-24] [INSTINCT:0.30] DEMO_PREP: Always trace the prospect's origin campaign in Instantly BEFORE building the demo brief. Check Leads/STATUS.md and lead CSVs to find which campaign/list they came from. Don't default to "LinkedIn inbound" — piece together the actual path. This shapes the opener and entire call framing. Root cause: assumed Kathleen was organic LinkedIn when she came from adriaan-2b-perf-mktg Instantly campaign.

[2026-03-24] [INSTINCT:0.30] DEMO_PREP: Demo prep must include a plain-English company explainer ("What is [Company]") that Oliver can internalize in 60 seconds. Stats and numbers are not enough. Explain what the company does, who their customers are, how their product works, and why it matters for the call. Root cause: listed Vantaca as "$1.25B HOA SaaS" without explaining what HOA management software actually is or what their AI product does.

[2026-03-24] [INSTINCT:0.30] PRICING: $60/mo Starter tier = 1 brand account only. Standard ($500-$1K) unlocks multi-account. For large companies (200+ employees, $20M+ revenue), always target Standard or above in the win story. $60 is rounding error at unicorn scale. Root cause: wrote win story targeting $60 POC with "connect two accounts" when Starter only supports one.

[2026-03-24] [INSTINCT:0.30] DEMO_PREP: Always load demo-prep gate (domain/gates/demo-prep.md) and sales methodology (domain/playbooks/sales-methodology.txt) BEFORE building any cheat sheet. The gate defines the 15-step checklist and story-trap structure. Don't build from scratch when the playbook exists. Root cause: built initial cheat sheet without loading the gate, missed thread flow and story-trap structure entirely.

[2026-03-24] [INSTINCT:0.30] DRAFTING: Follow-up emails must lead with empathy for the prospect's hesitation, not features. Structure: quick call recap, acknowledge their specific concern (budget, commitment, timing), explain how we remove that barrier (free trial, low-risk entry), then next steps. Never draft a follow-up that reads like a sales pitch. The prospect already sat through the demo. Root cause: first Kathleen follow-up draft was feature-heavy and didn't acknowledge her $500 budget concern or frame the free trial as the answer.

[2026-03-25] [INSTINCT:0.30] PROCESS: When a simple configuration change is requested, do it in one step. Don't try multiple approaches, fail on the first, then iterate. Read the schema or docs FIRST, find the correct field, apply it once. "Just install as is" means stop overcomplicating. Root cause: tried to add auto mode via a nonexistent top-level field (defaultPermissionMode), got a schema error, then had to read the full schema to find the correct path (permissions.defaultMode). Should have checked the schema before the first edit.
