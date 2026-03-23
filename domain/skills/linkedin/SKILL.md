---
name: linkedin
description: Draft personalized LinkedIn messages and InMails based on profile research. Use when the user mentions "LinkedIn message", "LinkedIn outreach", "InMail", "send a LinkedIn", "DM on LinkedIn", "connect on LinkedIn", "LinkedIn note", or references messaging someone on LinkedIn.
---

# LinkedIn Message

## Gate
Load and enforce domain/gates/linkedin.md before writing any LinkedIn message.

## What This Does
Crafts a short, personalized LinkedIn message (3-4 sentences max) with a personal hook drawn from the prospect's profile, posts, or recent activity.

## Inputs
- Prospect name (required)
- Context/intent (optional — connection request, follow-up, cold outreach)

## Steps
1. Run the LinkedIn gate checklist (profile visit, personal hook, NotebookLM persona match, lessons archive)
2. Present research checkpoint to Oliver
3. On approval, draft the message (3-4 sentences, personal hook first)
4. Run 5-Point Verification Stack from .claude/gates.md
5. Present to Oliver

## Output
A ready-to-send LinkedIn message with pre-flight proof block and verification line.
