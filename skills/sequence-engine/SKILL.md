---
---
DEPRECATED: Replaced by Loop. See skills/loop/SKILL.md

---
name: sequence-engine
description: Closed-loop sales intelligence system. Manages personalized email sequences, tracks outcomes, aggregates patterns, and gets smarter over time. Use when writing outbound emails, checking for replies, reviewing what's working, or prepping any prospect interaction. Also triggers on "sequence", "what's due", "follow-up check", "what's working", "pattern", "learning loop", "touch", or any email/call/demo prep for a specific prospect.
---

# Sequence Engine — Closed-Loop Sales Intelligence

## What This System Does
Every sales interaction is an experiment. This system:
1. **Writes** hyper-personalized emails using prospect context + learned patterns
2. **Tags** every interaction with structured metadata (type, intent, tone, angle, persona)
3. **Tracks** outcomes by checking Gmail for replies and Pipedrive for stage changes
4. **Learns** by aggregating patterns across all deals in PATTERNS.md
5. **Improves** by applying proven patterns to future interactions

## When to Load This Skill
- Writing any outbound email for a prospect in Pipedrive
- Checking for due follow-ups
- Prepping a demo or call
- Reviewing what's working / what's not
- Closing a deal (win/loss analysis)
- Oliver asks "what's due", "check replies", "what's working", "sequence status"

## Core Files
- **Prospect Notes:** `C:/Users/olive/SpritesWork/brain/prospects/[Name] — [Company].md`
- **Template:** `C:/Users/olive/SpritesWork/brain/prospects/_TEMPLATE.md`
- **Patterns:** `C:/Users/olive/SpritesWork/brain/emails/PATTERNS.md`
- **CARL Domain:** `.carl/sequence-engine`
- **Email Templates:** `"docs/Email Templates/templates.txt"` (framework reference)

## Workflow 1: Startup Scan (runs every session)

```
1. Scan brain/prospects/ for all notes with next_touch <= today
2. Check Gmail for replies from ANY prospect with outcome = "pending"
3. Group findings:
   - REPLIES RECEIVED: [prospect] replied on [date] — [positive/negative]
   - OVERDUE TOUCHES: [prospect] Touch N was due [date] — suggest [angle]
   - DUE TODAY: [prospect] Touch N — suggest [angle] based on PATTERNS.md
   - UPCOMING (3 days): [prospect] Touch N on [date]
4. Present to Oliver in 3-5 lines, not a wall of text
```

## Workflow 2: Write Email (triggered by Oliver)

```
1. Read prospect note in brain/prospects/
2. Read PATTERNS.md — check what works for this persona + stage
3. Check sequence history — what angles have been tried? What got no reply?
4. Load .carl/sequence-engine rules
5. Load "docs/Email Templates/templates.txt" for framework reference
6. Load "docs/Sales Playbooks/my-role.txt" for voice/banned words
7. Draft email following CLAUDE.md writing rules
8. Self-score against quality-rubrics.md (must be 7+)
9. Present to Oliver with tag summary:
   "Touch 3 for Tim Sok | type: follow-up | tone: direct | angle: their-own-words
    Based on PATTERNS.md: direct tone gets 35% reply rate for agency-owners [EMERGING]
    Previous touches: Touch 1 (case-study, no reply), Touch 2 (competitor-pain, no reply)"
10. Oliver approves → Gmail draft (HTML, clickable links)
11. Log to prospect note with full tag block
12. Set next_touch date based on cadence rules
13. Update Pipedrive activity
```

## Workflow 3: Process Reply (triggered at startup or manually)

```
1. Gmail shows reply from prospect
2. Read the reply content
3. Update prospect note:
   - outcome: positive-reply / negative-reply
   - reply_sentiment: positive / neutral / negative
   - outcome_date: today
4. If positive → surface to Oliver, draft response, advance deal stage
5. If negative → log objection, update PATTERNS.md negative patterns
6. If meeting booked → update outcome to "meeting-booked", create calendar event
```

## Workflow 4: Log Non-Email Interaction

```
For calls:
- Same tag block + opener, talk_track, duration, connected_with
- Outcome: connected / voicemail / no-answer / meeting-booked

For demos:
- threads_shown, resonated, fell_flat, buying_signals, objections
- Outcome: trial-agreed / proposal-requested / needs-follow-up / not-interested

For LinkedIn:
- message_type: connection-request / DM / InMail / comment
- Outcome: accepted / replied / ignored
```

## Workflow 5: Close Deal (Win/Loss)

```
1. Fill Deal Outcome section in prospect note
2. For WON: deciding factor, what almost killed it, cycle length, pricing, champion
3. For LOST: why, which objection, what would you do differently
4. Retroactively validate/invalidate the entire sequence
5. Update PATTERNS.md — every table that this deal's data touches
6. Update brain/objections/ if new objection pattern emerged
7. Update brain/personas/ if new persona insight emerged
8. Feed to NotebookLM Closed Won notebook
```

## Workflow 6: Pattern Review (weekly or on-demand)

```
1. Read PATTERNS.md
2. Scan all prospect notes for new outcome data
3. Recalculate all tables
4. Surface top insights:
   - "Best performing angle this month: [X] at [Y]% reply rate"
   - "Worst performing: [X] — consider dropping"
   - "New [EMERGING] pattern: [description]"
   - "Cadence adjustment suggested: [current] → [proposed] based on [data]"
5. Present to Oliver in weekly review
```

## Tag Reference

### type
cold | warm | follow-up | inbound | re-engage | post-demo | proposal | referral | breakup

### channel
email | call | linkedin | demo | meeting

### intent
book-call | get-reply | nurture | close | discover | deliver-value | handle-objection | push-decision

### tone
direct | casual | consultative | formal | curious | empathetic

### angle
pain-point | case-study | competitor-pain | roi-calc | trigger-event | personal-connection | industry-trend | their-own-words | new-feature | social-proof | mutual-contact | cost-savings

### framework
CCQ | gap-selling | JOLT | SPIN | inbound-welcome | breakup | consultative

### outcome
pending | no-reply | positive-reply | negative-reply | meeting-booked | deal-advanced | objection-raised | ghosted | unsubscribed

### reply_sentiment
positive | neutral | negative | N/A

### persona
agency-owner | fractional-cmo | ecom-director | founder | growth-lead | marketing-vp | ops-director

## Integration Points

- **Session Startup:** Workflow 1 runs automatically — scan for due touches + check replies
- **Pre-Draft Gate:** Workflow 2 extends the existing Pre-Draft Research Gate with pattern lookup
- **Post-Demo Gate:** Workflow 4 (demo variant) extends existing Post-Demo Follow-Up Gate
- **Wrap-Up:** Workflow 6 light version — update PATTERNS.md if any interactions happened
- **Weekly Review:** Full Workflow 6 — comprehensive pattern analysis
- **Win/Loss Gate:** Workflow 5 extends existing Win/Loss Analysis Gate with full attribution

## Anti-Patterns (Don't Do This)
- Don't repeat the same angle on consecutive touches (CARL rule 2)
- Don't present pattern insights without sample size + confidence level (CARL rule 15)
- Don't tag retroactively from memory — verify against Gmail/Fireflies/Pipedrive
- Don't optimize too early — need 10+ data points per variable minimum
- Don't log Anna's or Siamak's interactions unless Oliver says to (CARL rule 14)
- Don't change cadence timing based on <25 data points (hypothesis only)
