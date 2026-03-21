---
name: competitor-research
description: Build a pre-call research brief on a prospect's company — their ad presence, tech stack, competitive landscape, and talking points for Oliver's call. Use this skill whenever Oliver says "research [company]", "competitor research", "pre-call research", "what do we know about [company]", "prep for my call with [name]", "look into [company] before the demo", or any time Oliver needs intel on a prospect's company before a call or outreach. Also trigger when Oliver mentions a company name and asks what they're running for ads or what tools they use.
---

# Pre-Call Competitor & Prospect Research

## Why This Exists
Oliver closes better when he walks into calls knowing what the prospect's company does, what ads they run, what tools they use, and where Sprites fits. This skill builds that brief fast, using free sources first to save credits.

## Research Order (cheapest first)

### 1. Free Web Research (no credits)
- Google the company — what they sell, who their customers are, company size
- Visit their website — services, team page, case studies, blog
- Check for recent news, funding, acquisitions, leadership changes
- Look at careers page — hiring for marketing/paid media roles signals growth
- Check for testimonials (reveals their customers and positioning)

### 2. Ad & Tech Stack Research (no credits)
- Search "[Company] Meta ads" — check Meta Ad Library for active campaigns
- Search "[Company] Google ads" — any visible search presence
- Look for marketing tech mentions (tools, platforms, agencies)
- Note visible pain points (outdated site, no blog, weak SEO, no ad presence)

### 3. Contact Research (Apollo credits)
- Search Apollo MCP for the contact
- Pull: title, email, phone, stage, last activity, sequence status
- **Open Apollo browser → Activities tab** for prior calls, emails, or notes
- If there are call transcripts/insights from prior cold calls or discovery calls, save them as a text file and add to the Demo Prep notebook: `notebooklm source add "[transcript-file]" -n 6bdf40a0-e9e5-462b-bfcd-02a2985214c1`
- This is pre-demo context — the demo should pick up where the prior call left off
- Search LinkedIn (web) for recent posts, activity, job changes

### 4. NotebookLM Research (automated — deep web + multi-notebook) — tier system: .claude/skills/notebooklm/SKILL.md

**Source ingestion (run first, query after):**
- Add the prospect's website:
  `notebooklm source add "[company-website-url]" -n 6bdf40a0-e9e5-462b-bfcd-02a2985214c1`
- Run deep web research on the prospect (indexes 20+ sources — news, LinkedIn, industry, job postings, competitor mentions):
  `notebooklm source add-research "[prospect name] [company] marketing performance ads" --mode deep --no-wait --import-all -n 6bdf40a0-e9e5-462b-bfcd-02a2985214c1`
- Wait for research to complete:
  `notebooklm research wait -n 6bdf40a0-e9e5-462b-bfcd-02a2985214c1`

**Multi-notebook queries:**
- Demo Prep notebook → marketing setup, pain points, team size, ad channels:
  `notebooklm ask "[company] marketing setup, pain points, team size, ad spend" -n 6bdf40a0-e9e5-462b-bfcd-02a2985214c1`
- Sprites Sales → relevant case studies:
  `notebooklm ask "case studies for [prospect's industry]" -n 1e9d15ed-0308-4a30-ae27-edf749dc8953`
- Objection Handling → likely objections for this profile:
  `notebooklm ask "objections from [prospect profile type] prospects" -n 73f909fa-1ebc-4792-aa22-d810df2d7ca0`
- Closed Won → what closes similar deals:
  `notebooklm ask "what closes deals with [prospect profile type]?" -n 2eb736e0-9a78-4561-8fa0-94d4a4b2b340`
- ICP Signals → score this prospect:
  `notebooklm ask "how does [prospect profile] score against ICP patterns?" -n bf84ba08-214f-40ce-9d5f-a37f822d25ff`

### 5. Competitive Landscape
- Query Competitor Intel notebook if prospect mentions specific tools:
  `notebooklm ask "how does Sprites compare to [competitor]?" -n 829aa5bb-9bc0-4b07-a184-dc983375612b`
- Also run competitor-specific research if a new competitor surfaces:
  `notebooklm source add-research "[competitor name] pricing features reviews" -n 829aa5bb-9bc0-4b07-a184-dc983375612b`
- What are they likely using instead of Sprites? (agencies, in-house team, other AI tools)
- What's the switching cost? (contracts, team reliance, integrations)
- Where does Sprites win over their current setup?

## Output: Research Brief

Save to `docs/Demo Prep/` and present to Oliver:

```
## Pre-Call Brief: [Contact Name] at [Company]
**Date:** [Today] | **Call Time:** [If known from calendar]

### Company Snapshot
- What they do, size, location, industry

### Marketing & Ad Presence
- Meta Ads: Active/Inactive
- Google Ads: Active/Inactive
- Current tools/agency
- Marketing team size (if discoverable)

### Contact Intel
- Role, tenure, LinkedIn activity
- Previous touchpoints (calls, emails, sequences)
- Stage: Cold/Warm/Demo/Follow-up

### Talking Points
1. [Specific observation about their company]
2. [Pain point to probe]
3. [How Sprites solves their situation]
4. [Relevant case study]

### Objection Prep
- Likely objection + response

### Goal for This Call
[Target outcome — demo booking, trial, next meeting]
```

Also append to today's daily note.
