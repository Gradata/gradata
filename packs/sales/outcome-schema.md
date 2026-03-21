# Outcome Schema — Sales Pack

## Outcome Types

| Type | Description | Storage Location | Pattern Feed |
|------|------------|------------------|-------------|
| email | Outreach email sent — opened, replied, bounced, ghosted | brain/emails/PATTERNS.md | Win/loss counts by angle, segment, framework |
| call | Cold call or follow-up call — connected, voicemail, objection, booked | brain/prospects/[name].md | Call history section |
| demo | Demo delivered — engagement level, questions, objections, next steps | brain/prospects/[name].md | Demo notes section |
| proposal | Proposal sent — accepted, countered, ghosted, rejected | brain/prospects/[name].md | Deal progression |
| objection | Objection encountered — what was said, response used, result | brain/emails/PATTERNS.md | Objection patterns table |
| close | Deal won or lost — reason, timeline, debrief notes | brain/pipeline/ | Win/loss debrief log |
| linkedin | LinkedIn outreach — connection accepted, replied, ignored | brain/emails/PATTERNS.md | LinkedIn outcomes table |
| lead-filter | Lead qualified or disqualified — ICP match, reason, tier | brain/emails/PATTERNS.md | Filtering outcomes table |

## Outcome Entry Format

```
## [DATE] [TYPE] — [PROSPECT/COMPANY]
- **Tactic:** [what was done — angle, framework, approach, specific words used]
- **Result:** [what happened — reply, no reply, booked, objection, close, ghost]
- **Tags:** [angle], [framework], [segment], [tier]
- **Signal:** [positive|negative|neutral]
```

## Field Definitions

### Tactic
The specific action taken. Be concrete enough to reproduce:
- Email: subject line approach, opening hook, framework used (gap selling, CCQ, TRAP), CTA type
- Call: opening line, talk track, objection response technique
- Demo: story structure, features shown, pain points addressed
- Proposal: pricing approach, packaging, urgency lever

### Result
What actually happened. Use standardized outcomes:
| Outcome | Meaning |
|---------|---------|
| reply-positive | Replied with interest, asked questions, moved forward |
| reply-neutral | Replied but noncommittal, asked for more info |
| reply-negative | Replied to decline, objected, or asked to stop |
| no-reply | No response after reasonable wait (3+ business days for email) |
| booked | Meeting/demo/call scheduled |
| connected | Reached live on phone |
| voicemail | Left voicemail |
| objection | Raised specific objection (capture verbatim) |
| close-won | Deal closed, signed |
| close-lost | Deal lost (capture reason) |
| ghost | Went dark after engagement |

### Tags
Freeform but prefer these standardized tags for pattern aggregation:
- **Angle:** gap-selling, ccq, pain-first, social-proof, case-study, roi, urgency
- **Framework:** TRAP, story-trap, before-after, problem-agitate-solve
- **Segment:** multi-brand, pe-rollup, franchise, solo-consultant, lean-dtc, agency
- **Tier:** T1, T2, T3, international

### Signal
- **positive:** Tactic moved the deal forward or got engagement
- **negative:** Tactic failed, got rejected, or caused disengagement
- **neutral:** No clear signal either way (e.g., voicemail left, no reply yet)

## Pattern Detection

After logging, scan the last 10 entries of the same type:
- 3+ similar tactics with same result direction → flag as **emerging pattern**
- Format: `Pattern emerging: [tactic type] → [result] (N/M times)`
- Confidence tiers apply: <3 INSUFFICIENT, 3-9 HYPOTHESIS, 10-25 EMERGING, 25-50 PROVEN, 50-100 HIGH CONFIDENCE, 100+ DEFINITIVE

## Auto-Routing by Type

| Type | Destination | Update Action |
|------|-------------|---------------|
| email | brain/emails/PATTERNS.md | Add to outcomes table, update win/loss counts per angle |
| call | brain/prospects/[name].md | Add to call history section, update call score |
| demo | brain/prospects/[name].md | Add to demo notes, score talk ratio/questions/next steps |
| proposal | brain/prospects/[name].md | Add to deal progression timeline |
| objection | brain/emails/PATTERNS.md | Add to objection patterns, track response effectiveness |
| close | brain/pipeline/ | Log win/loss with full debrief, trigger Win/Loss Analysis gate |
| linkedin | brain/emails/PATTERNS.md | Add to LinkedIn outcomes, track by connection type |
| lead-filter | brain/emails/PATTERNS.md | Add to filtering outcomes, track ICP accuracy |
