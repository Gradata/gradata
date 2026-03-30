---
name: enrich
description: Find, verify, or enrich email addresses and contact data for prospects using Prospeo, ZeroBounce, and LeadMagic APIs. Use this skill whenever Oliver says "find their email", "enrich this contact", "verify email", "get their email", "do we have an email for", or when Apollo returned no email for a prospect and you need an alternative source. Also use when processing enrichment batches or when any prospect needs email data before outreach can happen. Requires either a LinkedIn URL (for Prospeo) or company domain + name (for LeadMagic).
---

# Enrichment Skill — Prospeo + ZeroBounce + LeadMagic

## Why This Exists
Apollo doesn't always have emails. Rather than burning credits blindly, this skill chains three APIs in priority order — cheapest/most-reliable first — and verifies results before using them.

## Security
API keys live in `.env` (gitignored). Read them at runtime via `source .env` or python-dotenv. If `.env` is missing, stop and tell Oliver. Never log, print, or include keys in any output.

## Python Path
C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe

## Enrichment Flow

1. **Check Apollo first** — free if contact exists. If email found, done.
2. **Prospeo LinkedIn finder** — needs a LinkedIn URL
   - Endpoint: `POST https://api.prospeo.io/social-url/email-finder`
   - Headers: `Content-Type: application/json`, `X-KEY: $PROSPEO_API_KEY`
   - Body: `{ "url": "<linkedin_profile_url>" }`
   - Cost: 1 credit per search. Balance tracked in docs/startup-brief.md.
3. **Prospeo domain search** (alternative if no LinkedIn URL)
   - Endpoint: `POST https://api.prospeo.io/domain-search`
   - Body: `{ "company": "example.com", "first_name": "Tom", "last_name": "Stewart" }`
4. **ZeroBounce verification** — verify any email found above
   - Endpoint: `GET https://api.zerobounce.net/v2/validate?api_key=$ZEROBOUNCE_API_KEY&email=<email>&ip_address=`
   - If status = "valid" → use it. If "invalid" → discard. If "catch-all" → flag as risky.
5. **LeadMagic fallback** — only if Prospeo fails
   - Endpoint: `POST https://api.leadmagic.io/email-finder`
   - Headers: `X-API-Key: $LEADMAGIC_API_KEY`
   - Body: `{ "first_name": "Tom", "last_name": "Stewart", "domain": "example.com" }`
   - Note: LeadMagic has been blocked by Cloudflare in the past. If 403, tell Oliver and skip.
6. **Update records** — add verified email to Obsidian brain note and any existing Gmail draft.

## Error Handling
- If Prospeo returns empty `person` object → no data found, move to next API
- If any API times out → retry once, then move to next
- If all three fail → tell Oliver, suggest manual LinkedIn check
- Log failures in `.claude/lessons.md`

## Credit Tracking
After each API call, note credits used. Update Prospeo balance in docs/startup-brief.md at session end.
