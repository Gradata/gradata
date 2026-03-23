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

## Active Lessons (20 entries — cap: 30)

### PATTERN — Active (migrated from legacy [CONFIRMED] format, Session 36)

[2026-03-20] [PATTERN:0.70] DRAFTING: Bullet lists need a lead-in line for context ("On that call we cover:"). One idea per bullet — no combining. Attach actual case study documents, don't just name-drop results.

[2026-03-20] [PATTERN:0.70] APIFY: Always use `harvestapi/linkedin-profile-scraper` for LinkedIn profile scraping (NOT supreme_coder). Input format: `{"queries": ["url1", "url2"]}`. Cost: $0.004/profile for harvestapi.

[2026-03-20] [PATTERN:0.70] LEADS: Scripts that write CSVs to active/ AND read from active/ for dedup will dedup against their own previous output on reruns. Always clean the output directory BEFORE the dedup scan, not after.

[2026-03-20] [PATTERN:0.70] ACCURACY: Systems-only sessions use the System/Architecture rubric in quality-rubrics.md, not sales output rubrics. Score against engineering standards, not prospect output quality.

[2026-03-20] [PATTERN:0.70] PROCESS: startup-brief.md must refresh every session during wrap-up (step 10.5). Never let the pipeline source of truth go stale.

[2026-03-20] [PATTERN:0.70] ARCHITECTURE: When splitting files, don't keep duplicate definitions. If content moves to domain/, replace the original with a single pointer — not both.

[2026-03-20] [PATTERN:0.70] COMMUNICATION: When surfacing anomalies or warnings, always explain WHY it matters and confirm whether it's a blocker or cosmetic. Don't leave ambiguity about severity.

[2026-03-21] [PATTERN:0.70] CRM: When analyzing Pipedrive data, filter out unworked deals (no value, no activity, no org) before drawing conclusions. Only deals with activity, assigned value, and real stage progression count as training data.

[2026-03-21] [PATTERN:0.70] STRATEGY: Don't conflate cold outreach reply data with close-cycle effectiveness. "Show the tool" gets cold replies. Pain-based selling (Gap, SPIN) closes deals. Different stages need different approaches.

[2026-03-21] [PATTERN:0.70] ACCURACY: Verify current state before presenting status or recommending changes. Check Gmail sent, source dates, actual workflows — never assume from memory or Pipedrive stage names.

[2026-03-21] [PATTERN:0.70] ARCHITECTURE: When adding any component, think big picture FIRST — behavior and purpose before file locations and wiring diagrams.

[2026-03-21] [PATTERN:0.70] PRESENTATION: When presenting calendar/timeline data, always state the current day of week and frame events relative to it. Don't present a grid that implies immediacy when there's a buffer.

[2026-03-21] [PATTERN:0.70] POSITIONING: Never use "agency pricing" — it implies expensive retainers. Say "fixed monthly subscription" or "flat rate, cancel anytime."

[2026-03-21] [PATTERN:0.70] DRAFTING: When building email subject lines or cadences, cross-reference BOTH external research (Gong, HubSpot) AND Oliver's playbooks (sales-methodology.txt, templates.txt). Neither source alone is sufficient.

[2026-03-21] [PATTERN:0.70] PROCESS: Parallelize wrap-up and multi-step tasks using background agents. 3+ independent items → fire concurrently, not sequentially.

[2026-03-21] [PATTERN:0.70] PROCESS: Don't start building before researching — even when excited about a feature. The design-first check and source-verification gate exist for a reason. Research best practices, prior art, and architecture patterns BEFORE writing code. Root cause: jumped straight to writing snapshot.py without researching how sales activity tracking systems work.

[2026-03-21] [PATTERN:0.70] ACCURACY: When displaying metrics that mix session types (sales vs system), always filter to the relevant track. Blended numbers (e.g., edit rate diluted by 0-revision system sessions) are misleading. Show the number that matters for the context. Root cause: statusline showed 15% edit rate blending sales (31%) with systems (0%).

### INSTINCT — New (require root cause, tracking)

[2026-03-22] [INSTINCT:0.49] CONSTRAINT: Before proposing any tool, API, or service, check if it costs money. If yes, flag it and ask -- don't present it as a solution. Default to free. Oliver wants zero-cost infrastructure. Root cause: proposed Composio (paid) and trial-tier APIs (25/month) twice before being corrected. Technical problem-solving instinct overrides constraint awareness.

[2026-03-22] [INSTINCT:0.49] DATA_INTEGRITY: "Oliver only" applies to ALL measurement -- not just deals and contacts, but metrics, delta data, campaign stats, and any aggregate numbers. When pulling data from shared systems (Instantly, Pipedrive, Gmail), always filter by owner. Root cause: included Anna's 84K campaign emails in Oliver's 1.8K reply rate calculation, producing 0.61% instead of 1.01%.

[2026-03-22] [INSTINCT:0.49] PROCESS: Never skip wrap-up steps when rushing. The 8.0 audit gate, confidence updates, and agent distillation are non-negotiable regardless of session length. Long session = MORE reason to audit, not less. Spawn wrap-up agents instead of skipping. Root cause: 6+ hour session caused fatigue-driven shortcutting on 6 wrap-up steps.

[2026-03-22] [INSTINCT:0.30] CONTEXT: Oliver does prospect work on weekdays, systems work on weekends. Never frame weekend systems sessions as "drift" or imply pipeline is being neglected. Check the day of week before commenting on session type balance. Root cause: lectured Oliver about 6 consecutive non-prospect sessions when it was Saturday — his normal schedule.

[2026-03-22] [INSTINCT:0.30] THOROUGHNESS: Never recommend "park" or "skip" as a first response to a deferred item. If the work can be done with subagents, do it. If it takes 30 minutes, take the 30 minutes. "Park" is only valid when Oliver explicitly says to defer, or when the task genuinely requires external input (API keys, Oliver's decisions, third-party approvals). Spawning agents is free — laziness is not. Root cause: recommended parking 3 of 6 S34 deferred items to avoid work, then Oliver had to push back twice.
