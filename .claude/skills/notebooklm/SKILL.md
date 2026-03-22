---
name: notebooklm
description: Use when user wants to Three-tier NotebookLM integration — MCP (preferred), CLI (fallback), manual browser (last resort). Use this skill whenever querying or feeding NotebookLM notebooks. Covers tier detection, authentication, failure handling, and logging. All NotebookLM operations in the system route through this file.
---

# NotebookLM Integration — Three-Tier Fallback

All NotebookLM operations (queries, source adds, deep research) use this tier system.
No other file defines NotebookLM fallback order. This is the single source of truth.

## Notebook Registry

| Notebook | ID | Use When |
|---|---|---|
| Sprites Sales | 1e9d15ed-0308-4a30-ae27-edf749dc8953 | Case studies, proof points, pricing |
| Demo Prep | 6bdf40a0-e9e5-462b-bfcd-02a2985214c1 | Pre-call prospect intel, company websites |
| Objection Handling | 73f909fa-1ebc-4792-aa22-d810df2d7ca0 | Real objections from calls + how handled |
| Closed Won Patterns | 2eb736e0-9a78-4561-8fa0-94d4a4b2b340 | What made deals convert, buying signals |
| Competitor Intel | 829aa5bb-9bc0-4b07-a184-dc983375612b | Competitor features, pricing, positioning |
| ICP Signals | bf84ba08-214f-40ce-9d5f-a37f822d25ff | Lead scoring patterns, conversion signals |
| Sprites Brain (Full Vault) | 88ea6815-e01d-49f7-87d2-d3177edd8843 | RAG over entire Obsidian brain |
| Inbound Prospecting | 9f674e3a-89d0-4848-bd8a-c86110df90f6 | Persona match, pain point angles, email framework selection |

## Tier Detection (run once per session at startup)

Check in order. Use the first tier that responds:

1. **Check Tier 1 (MCP):** Call the MCP tool `notebooklm_list_notebooks` or equivalent list operation. If it returns notebook data, MCP is available. Use Tier 1 for the session.
2. **Check Tier 2 (CLI):** Run `nlm --version` via Bash. If it returns a version string, CLI is installed and authenticated. Use Tier 2.
3. **Neither available:** Log to session notes. All NotebookLM operations this session will use Tier 3 (manual flag).

Surface the result in startup status: `[notebooklm] Tier [1/2/3] active`

## Tier 1: MCP (preferred)

**Package:** jacob-bd/notebooklm-mcp-cli
**Installation:** `uv tool install notebooklm-mcp-cli` then `nlm setup add claude-code`
**How it works:** Native MCP tool calls — no Bash, no CLI. Claude calls MCP tools directly.

**Operations:**
- **Query:** Use the MCP query/ask tool with notebook ID and question
- **Add source:** Use the MCP source-add tool with file path or URL and notebook ID
- **Deep research:** Use the MCP research tool with query and notebook ID
- **List notebooks:** Use the MCP list tool

**Success condition:** MCP tool returns data (not an error or timeout).
**If MCP call fails:** Log the error, fall through to Tier 2 for THIS operation. Do not retry the same MCP call more than once.

## Tier 2: CLI via Bash (fallback)

**Package:** notebooklm-py (already installed if `nlm --version` works)
**How it works:** Bash commands using the `notebooklm` CLI. This is how the system works today.

**Operations:**
- **Query:** `notebooklm ask "[question]" -n [notebook-id]`
- **Add source (file):** `notebooklm source add "[file-path-or-url]" -n [notebook-id]`
- **Deep research:** `notebooklm source add-research "[query]" --mode deep --no-wait --import-all -n [notebook-id]`
- **Wait for research:** `notebooklm research wait -n [notebook-id]`
- **List notebooks:** `notebooklm list`

**Success condition:** CLI returns output (exit code 0, non-empty stdout).
**If CLI fails:** Check if it's an auth error (see Re-Authentication below). If not auth, log the error and fall through to Tier 3.

## Tier 3: Manual Browser Flag (last resort)

**When:** Both Tier 1 and Tier 2 failed for an operation.
**What to do:**
1. Do NOT silently skip the NotebookLM step.
2. Log the failure to brain/sessions/[YYYY-MM-DD].md:
   ```
   ## NotebookLM Failure — [timestamp]
   - Operation attempted: [query/source-add/research]
   - Notebook: [name] ([id])
   - Question/source: [what was being queried or added]
   - Tier 1 (MCP) result: [error message or "not available"]
   - Tier 2 (CLI) result: [error message or "not available"]
   - Manual action needed: [exact steps Oliver should do in browser]
   ```
3. Surface it immediately to Oliver: "NotebookLM unavailable (MCP + CLI both failed). Logged to session notes. [What needs to be done manually]."
4. In the pre-flight block, mark: `[ ] NotebookLM: TOOL FAILED — Tier 1 [error] / Tier 2 [error]. Manual action logged.`
5. At wrap-up step 11 (handoff), include in brain/loop-state.md: "NotebookLM was down this session. [Operation] needs to be done manually or re-run next session."

## Failure Conditions That Trigger Fallback

| Failure | Tier 1 → Tier 2 | Tier 2 → Tier 3 |
|---------|-----------------|-----------------|
| Tool not found / MCP server not running | YES | N/A |
| Authentication expired (401/403) | YES | YES (see Re-Auth) |
| Timeout (>30 seconds no response) | YES | YES |
| Empty response (tool returns nothing) | YES | YES |
| Network error | YES | YES |
| Notebook ID not found | NO — fix the ID first | NO — fix the ID first |
| Rate limit | Retry once after 5s, then YES | Retry once after 5s, then YES |

## Re-Authentication

**When auth expires (cookies/tokens stale):**
1. Tell Oliver: "NotebookLM auth expired. Run `nlm login` in your terminal — takes 30 seconds, opens a browser window."
2. Oliver runs `! nlm login` in the Claude Code prompt (the `!` prefix runs it in-session).
3. After login completes, retry the failed operation.
4. Cookies typically last weeks. No need to re-auth every session.

**Signs of expired auth:**
- CLI returns "unauthorized", "401", "403", "login required", or "session expired"
- MCP returns authentication errors
- Queries that previously worked now return errors

## Logging

**Every NotebookLM operation gets logged (silently, no output to Oliver):**
- Which tier was used
- Whether it succeeded or fell back
- If fallback fired, what the error was

**Where to log:**
- Tier fallback events: brain/sessions/[YYYY-MM-DD].md under a `## NotebookLM Operations` section (create if not present)
- Persistent failures (3+ in one session): also flag in brain/loop-state.md handoff

This logging helps track whether the MCP integration is stable or if CLI remains the reliable path.
