# Tool Failure Fallback Chains — AIOS Framework
# When a mandatory tool fails, follow the chain. Don't improvise.
# Domain-specific tool fallbacks: domain/pipeline/fallback-overrides.md

## NotebookLM
See .claude/skills/notebooklm/SKILL.md for three-tier fallback: MCP → CLI → manual browser flag.

## Obsidian Vault
1. Obsidian CLI (if enabled)
2. CLI fails → Direct file read/write to brain/ directory
3. Direct file fails → FLAG: "Vault inaccessible. Skipping vault check but flagging it."
4. Vault check can be skipped with a flag but must be noted in daily notes.

## Google Calendar
**PRIMARY:** gcal_list_events / gcal_get_event with search terms and date range.
**FALLBACK 1:** Google Calendar browser via Claude in Chrome.
**FALLBACK 2:** Ask user to check calendar manually.
**FAIL STATE:** FLAG: "Calendar inaccessible. Cannot confirm scheduling."

## Cost Hierarchy (FREE FIRST — MANDATORY)
**Never use a paid tool when a free one can do the job. Always ask permission before paid tools.**

### Single Person / Small Lookup (1-10 people)
1. **Vault** — brain/ notes (free, instant)
2. **Web search** — WebSearch tool (free)
3. **Web browse** — WebFetch or Claude in Chrome (free)
4. **NotebookLM** — persona patterns (free)
5. **LinkedIn browser** — Claude in Chrome, visit profile directly (free)
6. **Company website** — WebFetch their domain (free)
7. **Paid tools** — ONLY if above steps missing critical data. Ask first.

### Bulk Enrichment (50+ people)
1. **Vault scan** — check if any already enriched (free)
2. **Free search** — search tools with filters, basic data without credits
3. **Paid scrapers** — ask for budget approval first
4. **Premium enrichment** — user runs manually or approves

### Hard Rules
- **Under 10 people:** Free sources FIRST. No paid tools without exhausting free options.
- **10-50 people:** Free search impractical. Basic search OK. Scrapers only with approval.
- **50+ people:** Bulk tools appropriate. Get OK on cost estimate before running.
- **Always state the cost** before running any paid tool.

## In-Task Escalation Ladder

When consecutive errors accumulate within a single task (not session-wide — per task):

| Consecutive Errors | Level | Action |
|---|---|---|
| 3 | **CHANGE_STRATEGY** | Stop current approach. Consult fallback chains above. Try alternative method. Log `TOOL_FAILURE` event via events.py. |
| 4 | **REDUCE_SCOPE** | Simplify the goal. Drop optional steps. Tell Oliver what's being cut and why. Log `TOOL_FAILURE` event. |
| 5 | **STOP** | Summarize what failed, what was tried, and present options. Wait for Oliver. Log `TOOL_FAILURE` event. |

**Hard abort:** 10 total errors on a single task (consecutive or not) → STOP regardless of level.

**What counts as an error:** Tool failure, API error, gate failure, output blocked by self-score, verification failure. Does NOT count: Oliver requesting revisions (that's feedback, not failure).

**Recovery:** After CHANGE_STRATEGY succeeds, error counter resets to 0. After REDUCE_SCOPE, counter carries forward (next error = STOP).

**Auto-lesson:** On REDUCE_SCOPE or STOP, auto-generate a lesson from the failure and log a CORRECTION event via events.py.

## General Rule
- If a required tool fails and no fallback works → FLAG with: what failed, what data is missing, what the impact is
- Never silently skip a gate step
- Never publish incomplete data as if it were complete
- Never improvise a new fallback not listed here without logging it as a lesson
