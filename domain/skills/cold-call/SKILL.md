---
name: cold-call
description: Generate personalized cold call scripts with pattern-interrupt openers based on LinkedIn research. Use when the user mentions "cold call", "call script", "phone script", "dial", "cold outreach call", "write a script for", or references calling a prospect by phone.
---

# Cold Call Script

## Gate
Load and enforce domain/gates/cold-call.md before generating any script.

## What This Does
Builds a personalized cold call script for a specific prospect. The script uses a pattern-interrupt opener drawn from their LinkedIn profile, a one-sentence reason for calling based on their situation, and a soft ask to book a demo.

## Inputs
- Prospect name (required)
- Company name (optional — will be looked up)

## Steps
1. Run the cold-call gate checklist (LinkedIn, company site, Apollo, Pipedrive, lessons archive)
2. Present research checkpoint to Oliver
3. On approval, generate the 5-part script (opener, intro, reason, bridge, ask)
4. Run 5-Point Verification Stack from .claude/gates.md
5. Present to Oliver

## Output
A ready-to-use cold call script with pre-flight proof block and verification line.
