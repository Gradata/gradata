---
name: post-call
description: Full post-call automation for ANY sales call — pull transcript, draft follow-up email, prep CRM notes, feed NotebookLM notebooks, and log to daily note. Use this skill whenever Oliver says "post-call", "post call", "call follow up", "after the call", "draft follow-up from the call", "what happened on that call", or references a call that just ended and needs follow-up. Also trigger when Oliver mentions a contact name right after a scheduled call time has passed. Input is typically a contact name. NOT for demo-only follow-up emails without the full automation pipeline — use post-demo for lightweight demo follow-ups.
---

# Post-Call Automation

## Why This Exists
After every sales call, Oliver needs three things fast: a personalized follow-up email (while the conversation is fresh), CRM notes, and a daily log entry. This skill pulls the transcript, queries NotebookLM for intelligence, generates all outputs, then feeds learnings BACK into the notebooks so they get smarter with every call.

## Steps

### 1. Find the Call
- Search Apollo MCP for the contact by name
- Open Apollo browser → contact's Activities tab → find the most recent call recording
- If transcript is still processing, tell Oliver and suggest retrying in 5 minutes (don't silently wait)
- Also check Fireflies for the recording if Apollo doesn't have it

### 2. Extract Key Intel
Read the full transcript and pull:
- **Pain points** the prospect mentioned
- **Current tools** they're using (competitors to Sprites)
- **Objections** or concerns raised
- **Questions** they asked about Sprites
- **Interest level** — curious, evaluating, or urgent need
- **Next steps** discussed on the call
- **Buying signals** or red flags
- **Outcome** — did they agree to pilot, need time, say no?

### 3. Query NotebookLM (multi-notebook) — tier system: .claude/skills/notebooklm/SKILL.md
Query the right notebooks based on what happened on the call:

**Always query:**
- Sprites Sales → best case study for their profile:
  `notebooklm ask "case studies for [prospect's industry or pain point]" -n 1e9d15ed-0308-4a30-ae27-edf749dc8953`
- Closed Won Patterns → what framing closes similar deals:
  `notebooklm ask "what approach closes deals with [prospect profile type]?" -n 2eb736e0-9a78-4561-8fa0-94d4a4b2b340`

**Query if relevant:**
- Objection Handling → if prospect raised objections, check how similar ones were handled:
  `notebooklm ask "how were objections about [topic] handled successfully?" -n 73f909fa-1ebc-4792-aa22-d810df2d7ca0`
- Competitor Intel → if prospect mentioned a competitor tool or agency:
  `notebooklm ask "how does Sprites compare to [competitor]?" -n 829aa5bb-9bc0-4b07-a184-dc983375612b`

### 4. Draft Follow-Up Email
Create a Gmail draft (HTML format) following CLAUDE.md's Follow-Up framework:
- "Hi [First Name],"
- Thank them briefly for the time
- Recap their specific pain + how Sprites solves it (reference what THEY said, not generic pitch)
- Include the case study that NotebookLM identified as most relevant
- Use framing from Closed Won patterns (audit-first? pilot? cost comparison?)
- CTA: [Book a call here](https://calendly.com/oliver-spritesai/30min)
- Hyperlink [Sprites.ai](https://www.sprites.ai) at least once
- Close with Oliver's signature

Present the draft to Oliver for review before sending. Oliver decides when to send.

### 5. Prep CRM Notes
Output a copy-paste ready summary:
- Date and duration of call
- Key takeaways (2-3 bullets)
- Current stack/tools mentioned
- Objections/concerns
- Next steps agreed on
- Suggested follow-up date
- Deal stage recommendation

### 6. Feed the Notebooks (CRITICAL — this is the learning loop)
After extracting call intel, feed it back into the notebooks so they compound:

**Objection Handling notebook** — if new objections were raised:
Save a text file with the objection, how it was handled, and the outcome. Add it:
`notebooklm source add "[objection-file]" -n 73f909fa-1ebc-4792-aa22-d810df2d7ca0`

**Closed Won Patterns notebook** — if deal closed or strong buying signals:
Save the conversion pattern (what tipped them, buying signals, profile). Add it:
`notebooklm source add "[closed-won-file]" -n 2eb736e0-9a78-4561-8fa0-94d4a4b2b340`

**ICP Signals notebook** — always update with prospect profile data:
Save prospect profile + signals + outcome. Add it:
`notebooklm source add "[icp-signal-file]" -n bf84ba08-214f-40ce-9d5f-a37f822d25ff`

**Competitor Intel notebook** — if prospect mentioned competitor tools:
Save what they said about the competitor. Add it:
`notebooklm source add "[competitor-file]" -n 829aa5bb-9bc0-4b07-a184-dc983375612b`

Save these files to `docs/Exports/notebook-feeds/` for reference.

### 7. Log to Daily Note + Brain
Append to today's daily note at `C:\Users\olive\OneDrive\Desktop\Sprites Work\[YYYY-MM-DD].md`:
```
### Post-Call: [Contact Name] at [Company]
[2-3 bullet summary]
```
Update brain prospect note in `C:/Users/olive/SpritesWork/brain/prospects/[Name] — [Company].md`

### 8. Present to Oliver
- Show the draft email for review
- Show the CRM notes
- Flag any urgent follow-up items (e.g., they asked for pricing, they want a trial)
- Confirm which notebooks were updated
