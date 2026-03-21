# Tool Failure Fallback Chains
# When a mandatory tool fails, follow the chain. Don't improvise.

## Fireflies (call transcripts)
**PRIMARY:** Fireflies MCP — search by attendee email first, then contact name, then company name. Search all team members (oliver@, anna@, siamak@spritesai.com).
**FALLBACK 1:** Fireflies browser (https://app.fireflies.ai) via Claude in Chrome. Same search order.
**FALLBACK 2:** Ask Oliver: "Was there a recording for [company]? Can you share the link or paste key quotes?"
**FAIL STATE:** FLAG: "No transcript available. Cannot draft post-demo follow-up without it." SKIP: post-demo email drafting for this prospect. Do NOT draft without transcript — this gate has no bypass.

## Apollo MCP (contact enrichment)
**PRIMARY:** Check vault (brain/ notes) for existing data first. If not enriched, Apollo MCP enrichment.
**FALLBACK 1:** Apollo browser (https://app.apollo.io) via Claude in Chrome. Manual search and extraction.
**FALLBACK 2:** LinkedIn profile via Claude in Chrome → then Google search "[name] [company] [title]" for supplementary data.
**FAIL STATE:** FLAG to Oliver: "Cannot enrich [name] at [company]. Need manual lookup or alternative source." SKIP: publishing CRM note with unenriched fields — leave fields blank with "[UNENRICHED]" tag, never fill with guesses.

## Pipedrive (CRM via Composio)
**PRIMARY:** RUBE_MULTI_EXECUTE_TOOL with batched calls (reads first, then writes).
**FALLBACK 1:** RUBE_SEARCH_TOOLS to rediscover tool slugs (schemas change on Composio updates), then retry with corrected slugs.
**FALLBACK 2:** Individual Composio tool calls (unbatched) — slower but may work if batching is the failure point.
**FAIL STATE:** FLAG to Oliver: "Pipedrive MCP down. All intended CRM updates logged below for manual entry." SKIP: automated CRM sync. Save ALL intended updates (deal changes, notes, activities, contact updates) to daily notes with exact field values so Oliver can enter manually. Never silently skip CRM updates.

## Gmail (email drafting)
**PRIMARY:** Gmail MCP gmail_create_draft with HTML body, correct threadId, and recipient.
**FALLBACK 1:** Gmail browser via Claude in Chrome — compose draft directly in Gmail UI.
**FALLBACK 2:** Save draft as HTML file in Sprites Work/drafts/[prospect-name]-[date].html with all metadata (to, subject, threadId, body). FLAG Oliver to copy-paste.
**FAIL STATE:** FLAG: "Gmail completely inaccessible. Draft saved locally at [path]." SKIP: nothing — the draft MUST be preserved locally. Never lose a draft.

## Google Calendar
**PRIMARY:** gcal_list_events / gcal_get_event with search terms and date range.
**FALLBACK 1:** Google Calendar browser via Claude in Chrome — visual check of calendar.
**FALLBACK 2:** Ask Oliver: "Can you check your calendar for [date range] — I need to confirm [meeting/availability]?"
**FAIL STATE:** FLAG: "Calendar inaccessible. Cannot confirm scheduling." SKIP: any follow-up task, next-step scheduling, or availability-dependent action. Never create a follow-up with a date without confirming calendar first. Wait for Oliver's manual check.

## NotebookLM
See .claude/skills/notebooklm/SKILL.md for three-tier fallback: MCP → CLI → manual browser flag.

## Obsidian Vault
1. Obsidian CLI (if enabled)
2. CLI fails → Direct file read/write to C:\Users\olive\SpritesWork\brain\
3. Direct file fails → FLAG: "Vault inaccessible. Skipping vault check but flagging it."
4. Vault check can be skipped with a flag but must be noted in daily notes.

## Composio Credit Exhaustion
1. Check credit count at session start if possible
2. If credits low (<100 remaining) → batch aggressively, skip non-essential reads
3. If credits exhausted → FLAG Oliver immediately
4. Save all intended Pipedrive updates to daily notes for manual entry
5. Do NOT attempt calls that will fail — check credit status first

## Cost Hierarchy (FREE FIRST — MANDATORY)
**Never use a paid tool when a free one can do the job. Always ask permission before paid tools.**

### Single Person / Small Lookup (1-10 people)
1. **Vault** — brain/ notes (free, instant)
2. **Web search** — WebSearch tool (free)
3. **Web browse** — WebFetch or Claude in Chrome (free)
4. **NotebookLM** — persona patterns (free)
5. **LinkedIn browser** — Claude in Chrome, visit profile directly (free)
6. **Company website** — WebFetch their domain (free)
7. **Apollo MCP** — ONLY if above steps missing critical data. **Costs 1 credit per person.** Ask Oliver first.
8. **Apify scraper** — NEVER for single lookups. Only for bulk (50+).
9. **Prospeo / Lead Magic / Clay** — only when Oliver directs

### Bulk Enrichment (50+ people)
1. **Vault scan** — check if any already enriched (free)
2. **Apollo free search** — apollo_contacts_search with filters, returns basic data without consuming enrichment credits
3. **Apify LinkedIn scraper** — $4/1K profiles. **Ask Oliver for budget approval first.**
4. **Prospeo** — email enrichment. Oliver runs manually or approves.
5. **Lead Magic** — phone enrichment. Oliver runs manually.
6. **Clay** — sparingly, only when Oliver says

### Hard Rules
- **Under 10 people:** Web search + LinkedIn browser FIRST. No paid tools without exhausting free options.
- **10-50 people:** Web search impractical. Apollo search (not enrichment) is OK. Apify only with approval.
- **50+ people:** Bulk tools appropriate. Get Oliver's OK on cost estimate before running.
- **NEVER use Apollo bulk_match or people_match for single lookups** — that's $1/person. Use web search instead.
- **NEVER use Apify for single person lookups** — that's paying for something the browser does for free.
- **Always state the cost** before running any paid tool: "This will cost ~$X. OK to proceed?"

## General Rule
- If a required tool fails and no fallback works → FLAG to Oliver with: what failed, what data is missing, what the impact is
- Never silently skip a gate step
- Never publish incomplete data as if it were complete
- Never improvise a new fallback not listed here without logging it as a lesson
