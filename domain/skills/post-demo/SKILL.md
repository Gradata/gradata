---
name: post-demo
description: Draft post-demo follow-up emails from Fireflies transcripts with specific call references. Use when the user mentions "post-demo", "post demo", "demo follow-up", "follow up after demo", "after the demo", "demo debrief", or references a demo that just happened and needs follow-up. Focused on demo-specific follow-up emails only (transcript extraction, quote-driven email, CRM stage update). NOT for full post-call automation with notebook feeds and daily logging — use post-call for that.
---

# Post-Demo Follow-Up

## Gate
Load and enforce domain/gates/post-demo.md before drafting any post-demo email.

## What This Does
Pulls the Fireflies transcript from the demo, extracts key quotes, reactions, objections, and buy signals, then drafts a follow-up email that references specific things from the actual conversation. No generic "thanks for your time" emails.

## Inputs
- Prospect name (required)
- Demo date (optional — defaults to most recent)

## Steps
1. Run the post-demo gate checklist (Fireflies transcript, LinkedIn re-check, NotebookLM, Pipedrive update, lessons archive)
2. Extract: what was shown, reactions, exact quotes, objections, buy signals, next steps, pricing
3. Present research checkpoint to Oliver
4. On approval, draft follow-up email (hook from their words, recap, proposal/next steps, CTA)
5. Update Pipedrive deal stage and add demo notes
6. Run 5-Point Verification Stack from .claude/gates.md
7. Present to Oliver

## Output
Gmail draft (HTML) with specific call references, plus updated CRM notes.
