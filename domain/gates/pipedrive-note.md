# Pipedrive Note Quality Gate (MANDATORY — NO EXCEPTIONS)
**NO note may be published until all sources checked and data verified.**

### Checklist:
0.5. **Lessons archive** — search for CRM, ACCURACY categories.
1. All data from verified sources (Apollo, Fireflies, Gmail, Calendar, LinkedIn)
2. Never cite .md files as sources
3. Never publish with "pending" or "enrichment needed" flags
4. Never include AI attribution text
5. All notes in HTML format
6. Include corrections section if prior data was wrong
7. DELETE old note before publishing new one. No duplicates.

### Claim-Level Source Tagging (MANDATORY):
Every factual statement gets a bracketed source tag inline. No untagged facts. If a claim can't be sourced, mark it "[INFERRED — not confirmed]".

### Schema Validation:
**Required for CRM notes (Pipedrive):**
- Contact name, title, company — all sourced
- At least one communication channel (email or phone)
- Deal stage (must match Pipedrive stage IDs)
- Last interaction date and type
- Next step with date and owner

**Required for vault notes (brain/prospects/):**
- Contact block (name, title, company, email)
- Persona type (from brain/personas/)
- Touch history (at least most recent touch with tags)
- Current deal stage
- Next touch date

**Validation rules:**
- No field may contain "[PENDING]" or "[TBD]"
- Email addresses must pass format check
- Dates must be real dates (no "soon" or "next week")
- Stage values must come from a defined set
