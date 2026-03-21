# Lead Lists — Status Index

## WIP

### claude-code-80hrs-2026-03-16
- **Source:** LinkedIn post "80+ hours in Claude Code" (4,851 commenters)
- **Post:** https://www.linkedin.com/feed/update/urn:li:activity:7436770896872239105
- **Stage:** Filtered + sweep in progress
- **Files:**
  - `claude code 80 marketer post.csv` — master source (4,851 rows, don't edit)
  - `claude-code-80hrs-ICP-MATCH.csv` — 2,211 title-matched ICP leads (ready for enrichment)
  - `claude-code-80hrs-NO-MATCH.csv` — 2,477 leads (sweep input queue, don't edit)
  - `claude-code-80hrs-NO-MATCH-SWEPT.csv` — grows daily (+200/run)
- **Sweep progress:** 32/2,477 swept before LinkedIn temp restriction (lifted 1:16 PM PDT 3/16)
- **Next:** Resume daily sweep (100/day, safer limits), then enrich ICP list in Clay, build outbound sequence
- **Sweep script:** `python linkedin-sweep-nomatch.py` (updated: 100/day, 45-90s delays to avoid LinkedIn flags)


## DONE

### adsgpt-post
- AdsGPT "AI Beats Human Marketers Google Ads" post
- Raw + 4 filtered batches + combined final. Completed.

### claude-setup-post
- "How to set up Claude in 10 minutes" post
- Raw + filtered (714 leads) + 11 batches + Clay exports. Completed.

### 80-marketer-post
- 80 marketer post
- Raw + enriched (207 verified leads). Completed.

### adriaan-2b-perf-mktg-2026-03-13
- Adriaan Dekker's "$2B+ performance marketing + Claude Skill" post
- **Post:** https://www.linkedin.com/posts/adriaan-dekker_2b-in-performance-marketing-budgets-managed-activity-7306291765664485376
- 237 commenters scraped, 112 profiles swept, 43 ICP leads identified (re-filtered with expanded geo)
- Clay import file: `adriaan-clay-import.csv` (43 leads) — imported to "Oliver's Leads"
- 3 profiles need re-sweep: `adriaan-needs-resweep.csv`
- Sweep complete. Imported to Clay 2026-03-16.
