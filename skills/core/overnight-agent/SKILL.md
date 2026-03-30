---
name: overnight-agent
description: Scheduled pre-session agent that runs at 7am PT daily (weekdays) — checks Gmail, Fireflies, Pipedrive, Instantly for overnight changes, pre-drafts due follow-ups, and writes morning-brief.md. Use when the user mentions "overnight agent", "morning brief", "overnight scan", "what happened overnight", "pre-session prep", "morning update", "overnight changes", or needs to run the daily briefing agent manually.
---

# Overnight Agent — Pre-Session Preparation

> Runs automatically at 7:00 AM PT weekdays via scheduled task.
> Writes output to brain/morning-brief.md.
> Oliver opens Claude → reads 20-line briefing → starts working immediately.

## Execution Steps

### Step 1: Gmail Scan
Search for new emails since last brief:
- `from:kevin.gilsdorf@kindlepoint.com OR from:hassan.s.ali@gmail.com OR from:celia@i-screen.me OR from:ogomez@skgroupusa.com` (active prospect replies)
- `to:oliver@spritesai.com is:unread` (any unread to Oliver)
- `from:calendly.com` (new bookings)
- Log: who replied, sentiment (positive/negative/question), subject line

### Step 2: Fireflies Scan
Search for recordings since last brief:
- `fireflies_get_transcripts(fromDate: yesterday, mine: true)`
- For each new recording: pull summary, match to prospect, flag for processing

### Step 3: Pipedrive Scan
Check for stage changes on Oliver's deals:
- Pull all deals with label 45 (Oliver's)
- Compare stages to brain/loop-state.md pipeline snapshot
- Flag any deals that moved stages externally (Siamak, prospect action)

### Step 4: Instantly Scan (Read-Only)
Check cold tier for new replies:
- `list_emails` with status filter for replies
- Any warm replies → flag for Oliver to convert to pipeline tier

### Step 5: Calendar Check
Pull today's calendar:
- Surface meetings, demos, calls
- For demos: check if demo prep gate has been completed (brain/prospects/ note exists with demo prep section)
- Flag unprepared demos

### Step 6: Due Touch Calculation
Read brain/loop-state.md pipeline snapshot:
- Calculate which prospects have touches due today
- For each due touch: read prospect note, check PATTERNS.md, suggest angle
- Pre-draft follow-ups for touches due today (save as brain/drafts/[prospect]-[date].md)

### Step 7: Signal Check
Read brain/signals.md:
- Check for any new signals from Google Alerts email forwards
- Score relevance, add to unprocessed signals table

### Step 8: Write Morning Brief
Write to C:/Users/olive/SpritesWork/brain/morning-brief.md:

```
# Morning Brief — [DATE]
> Auto-generated at 7:00 AM PT. Read this first.

## Overnight Changes
- [REPLIES]: [list or "none"]
- [RECORDINGS]: [list or "none"]
- [DEAL MOVES]: [list or "none"]
- [SIGNALS]: [list or "none"]

## Today's Calendar
- [time] — [event] [PREP STATUS]

## Due Touches
| Prospect | Touch # | Suggested Angle | Draft Ready? |
|----------|---------|----------------|-------------|

## Deal Health Alerts
- [any deals below 40 health score]

## Pre-Drafted Emails
- [list of drafts in brain/drafts/ ready for Oliver review]
```

### Step 9: Update Loop State
If any overnight changes detected (replies, stage moves), update brain/loop-state.md:
- Move replied prospects from "pending" to appropriate outcome
- Update "What Changed" section with overnight findings
- Do NOT update PATTERNS.md (wait for Oliver's session for full analysis)

## Self-Heal
If any MCP tool fails:
1. Log failure in morning brief under "## Tool Failures"
2. Continue with remaining steps
3. Note what data is missing due to failure

## Output
Morning brief should be <30 lines. Dense, scannable, actionable.
Oliver's first session command should be: "read the morning brief" → instant context.
