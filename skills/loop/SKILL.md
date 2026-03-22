---
name: loop
description: Use when user wants to Closed-loop sales intelligence engine. Tags every prospect interaction, tracks outcomes, builds PATTERNS.md, rotates angles based on data. Loaded via CARL LOOP domain (always-on).
---

# Loop — Closed-Loop Sales Intelligence

## What Loop Is
Loop is your personal sales intelligence engine. Every sales activity you do — emails, calls, demos, proposals, closes — gets tagged, tracked, and fed back into the system. Over time, Loop learns what works for each persona, angle, tone, and deal stage. It makes every interaction smarter than the last.

Loop is not a CRM. It's the intelligence layer that sits between you and your CRM.

## How It Works

```
You ask Claude to draft/prep something
    ↓
Claude reads PATTERNS.md (what's worked before?)
    ↓
Claude checks prospect history (what's been tried?)
    ↓
Claude picks best approach (angle, tone, framework)
    ↓
Claude drafts + tags the output
    ↓
You approve → Gmail/Pipedrive
    ↓
Next session: Claude checks for outcomes
    ↓
Updates records → recalculates patterns
    ↓
Loop gets smarter → repeat
```

## How You Interact With Loop

Just talk naturally. These all trigger Loop:

| What You Say | What Happens |
|---|---|
| "What's due?" | Scan all prospects for due touches, pending outcomes, overdue follow-ups |
| "Check my pipeline" | Pull Pipedrive deals, cross-reference brain notes, surface action items |
| "Run Loop" | Full scan: outcomes, due touches, pattern insights, stale deals |
| "Draft a follow-up for [name]" | Load prospect note → check PATTERNS.md → pick best angle/tone → draft |
| "What's working?" | Read PATTERNS.md, surface top insights by persona/angle/tone |
| "Show patterns" | Full pattern dump with confidence levels and sample sizes |
| "Nurture my stale deals" | Find all prospects 14+ days since last touch, draft personalized emails |
| "Log this call" | Create tagged call entry in prospect note |
| "[Name] demo went great" | Create tagged demo entry with what resonated/fell flat |
| "We closed [name]" | Fill Deal Outcome, score entire sequence retroactively, update PATTERNS.md |
| "We lost [name]" | Fill Deal Outcome with loss analysis, update negative patterns |
| "Start sequence for [name]" | Create prospect note from template, set cadence, draft Touch 1 |
| "What should I try for [persona]?" | Query PATTERNS.md for best angle, tone, framework for that persona |
| "Check Instantly" | Pull campaign analytics, update cold tier data |

## Two Data Tiers

### Cold Tier (Instantly)
- Bulk cold outreach data (82K+ emails from Anna's + Oliver's campaigns)
- High volume, lower personalization
- Useful for: which angles/personas work at scale, what to avoid, broad benchmarks
- Source: Instantly MCP campaign analytics

### Pipeline Tier (Claude-written)
- Hyper-personalized touches for active Pipedrive deals
- Lower volume, much higher signal quality
- Useful for: what converts to meetings/revenue, persona-specific approaches, deal velocity
- Source: brain/prospects/ notes with tagged sequence history

These tiers have different benchmarks. Don't compare cold bulk rates (1-5% reply) to warm pipeline rates (15-25% reply).

## What Gets Tagged

Every interaction gets these tags:

| Tag | Values | Purpose |
|-----|--------|---------|
| **type** | cold, warm, follow-up, inbound, re-engage, post-demo, proposal, referral, breakup, nurture | What kind of touch |
| **channel** | email, call, linkedin, demo, meeting, proposal | How it was delivered |
| **intent** | book-call, get-reply, nurture, close, discover, deliver-value, handle-objection, push-decision, get-referral | Goal of this touch |
| **tone** | direct, casual, consultative, formal, curious, empathetic | Voice used |
| **angle** | pain-point, case-study, competitor-pain, roi-calc, trigger-event, personal-connection, industry-trend, their-own-words, trial-results, white-label, breakup-referral, research-invite, time-savings, revenue-lift, cost-reduction | Specific hook used |
| **framework** | CCQ, gap-selling, JOLT, SPIN, inbound-welcome, breakup | Sales methodology applied |
| **sequence_position** | 1, 2, 3... | Which touch in the sequence |

Activity-specific tags:
- **Calls:** opener, talk_track, duration, connected_with
- **Demos:** threads_shown, resonated, fell_flat, buying_signals, objections
- **Proposals:** pricing_tier, packaging, discount
- **Closes:** deciding_factor, what_almost_killed_it, cycle_length, champion

## Confidence Levels

| Data Points | Label | How Claude Treats It |
|-------------|-------|---------------------|
| <3 | [INSUFFICIENT] | Never presents as guidance |
| 3-9 | [HYPOTHESIS] | Mentions with heavy caveats |
| 10-25 | [EMERGING] | Uses as directional guidance |
| 25-50 | [PROVEN] | Follows unless Oliver overrides |
| 50-100 | [HIGH CONFIDENCE] | Reliable for moderate effects |
| 100+ | [DEFINITIVE] | Safe for playbook-level rules |

## Default Cadences

| Scenario | Touch Schedule (days) |
|----------|----------------------|
| Post-Demo Follow-Up | 1, 3, 7, 14 |
| Cold Sequence | 0, 3, 6, 8 (LinkedIn), 12, 16 (breakup) |
| Re-engage (Gone Silent) | 7, 14, 30 |
| Nurture (Warm, No Urgency) | 7, 21, 45 |
| Proposal Follow-Up | 1, 3, 5, 10 |
| Trial Check-in | 1, 3, 7 (check-in), 14 (results review) |

Key insight from data: breakup emails (last touch) consistently generate the most replies across all sequences.

## Startup Integration
At every session startup, Loop automatically:
1. Scans brain/prospects/ for touches where outcome = "pending" → checks Gmail
2. Identifies overdue touches (next_touch < today)
3. Identifies due-today touches
4. Surfaces upcoming touches (next 3 days)
5. Presents as a scannable table grouped by urgency

## Wrap-Up Integration
At every session wrap-up, Loop automatically:
1. Scans all prospect notes for interactions logged this session
2. Recalculates PATTERNS.md tables (reply rates, conversion rates, confidence levels)
3. Adds new negative patterns to "What NOT to Do"
4. Surfaces "what changed" — new patterns crossing confidence thresholds
5. Updates cadence rules if data suggests adjustments

## Key Files
| File | Purpose |
|------|---------|
| brain/emails/PATTERNS.md | The learning database — all aggregate patterns |
| brain/prospects/_TEMPLATE.md | Prospect note template with full Loop tagging |
| brain/prospects/[Name].md | Individual prospect sequence history |
| .carl/loop | CARL domain rules (21 rules) |
| brain/pipeline/ | Weekly pulse snapshots |
| brain/objections/ | Objection playbook linked from patterns |
| brain/demos/ | Demo-specific notes |

## Baked-In Learnings (from 82K+ cold emails)

### What Works
1. **Direct angle** — 8.8% reply rate [PROVEN]. Simple beats clever.
2. **Break-up email (Touch 4)** — highest reply step across all campaigns
3. **Founder-to-founder framing** — warmer responses than brand emails
4. **Research/curiosity angle** — 1.5% reply but generates most pipeline volume (44 opps)
5. **Pattern interrupt on Touch 2** — triggers curiosity ("what do you do?")
6. **Agency vertical** — best performing segment by far
7. **Short subject lines** — "quick intro", "quick question" outperform

### What Fails (Never Do Again)
1. **"Replace your agency"** — 0.1% (672 emails). Dead.
2. **Urgency/scarcity tone** — 0% (437 emails). Zero replies.
3. **Free audit offer** — 0% (96 emails). Zero replies.
4. **Multi-brand angle** — 0% (97 emails). Zero replies.
5. **Operational chaos framing** — 0.3% (711 emails). Too abstract.
6. **Future-tech/cursor angle** — 0% (244 emails). Too abstract for agency DMs.
7. **Free trial to mobile founders** — 0.3% (7,950 emails). Wrong channel for persona.
8. **Freelancer targeting** — 0.2% (1,423 emails). Not ICP.

## The Loop Audit
After every session, the auditor scores Loop-specific dimensions:
- Were all interactions tagged before output?
- Were PATTERNS.md insights used in drafts?
- Were outcomes checked and updated?
- Were new patterns surfaced?
- Is confidence labeling accurate?

Score below 7 on any dimension = flag for next session improvement.
