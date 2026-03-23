---
name: pipedrive-note
description: Build verified, source-tagged CRM notes for Pipedrive deals and vault prospect files. Use when the user mentions "CRM note", "Pipedrive note", "update Pipedrive", "deal note", "prospect note", "update the deal", "log to CRM", "write a note for", or references adding notes to a deal or contact.
---

# Pipedrive Note

## Gate
Load and enforce domain/gates/pipedrive-note.md before publishing any note.

## What This Does
Creates schema-validated, source-tagged CRM notes for Pipedrive and vault prospect files. Every factual claim is tagged with its source. No pending fields, no unverified data, no duplicates.

## Inputs
- Prospect/deal name (required)
- Note type: CRM (Pipedrive) or vault (brain/prospects/) (optional — defaults to both)

## Steps
1. Run the pipedrive-note gate checklist (source verification, lessons archive, schema validation)
2. Gather data from verified sources (Apollo, Fireflies, Gmail, Calendar, LinkedIn)
3. Tag every claim with bracketed source
4. Validate against schema (required fields, format checks, no pending values)
5. Delete old note if replacing
6. Run 5-Point Verification Stack from .claude/gates.md
7. Present to Oliver

## Output
HTML-formatted CRM note with inline source tags and schema validation pass.
