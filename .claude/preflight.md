# Pre-Flight Blocker — Mandatory Before ANY Prospect Output

> This is not a suggestion. This is a blocker. No prospect-related output (email, demo prep,
> CRM note, cheat sheet, call script, follow-up) may be presented to Oliver until ALL
> applicable checks show PASS. If any check shows FAIL, fix it before presenting.

## Pre-Flight Checklist

Before presenting ANY prospect-related output, verify and show this block:

```
PRE-FLIGHT: [Prospect Name] — [Output Type]
[x] Vault: brain/prospects/[Name].md READ (or CREATED from template)
[x] Persona MOC: brain/personas/[type].md READ
[x] Knowledge Graph: query-playbook [persona] RAN — [top angle], [top objection]
[x] PATTERNS.md: READ — [relevant insight or "no data for this persona"]
[x] NotebookLM (tier system: .claude/skills/notebooklm/SKILL.md): [notebook] queried — [case study/proof point found or "no match"]
[x] Lessons archive: scanned for [relevant categories] — [X applicable lessons]
[x] Gmail history: checked for prior threads with [prospect email]
[x] Humanizer: draft passed through /humanizer
[x] Self-score: [X]/10 — agree? Say "that's a [X]" to override
CLEARED FOR PRESENTATION
```

## Which Checks Apply to Which Output Type

| Check | Email | Demo Prep | CRM Note | Call Script | Follow-Up |
|-------|-------|-----------|----------|-------------|-----------|
| Vault | YES | YES | YES | YES | YES |
| Persona MOC | YES | YES | NO | YES | YES |
| Knowledge Graph | YES | YES | NO | YES | YES |
| PATTERNS.md | YES | YES | NO | YES | YES |
| NotebookLM | YES | YES | NO | YES | YES |
| Lessons archive | YES | YES | YES | YES | YES |
| Gmail history | YES | NO | NO | NO | YES |
| Humanizer | YES | NO | NO | NO | YES |
| Self-score | YES | YES | YES | YES | YES |

## Enforcement

- If a check is skipped: the output CANNOT be presented. Period.
- If a tool fails (NotebookLM down, knowledge graph error): log the failure, note "TOOL FAILED — [which]" in the pre-flight block, and proceed with remaining checks. Don't silently skip.
- The pre-flight block MUST appear above every prospect output Oliver sees. It's proof the process was followed.
- At wrap-up, count how many pre-flights ran and how many checks passed/failed. Log to analytics.py.

## Why This Exists

Sessions 1-6: Oliver had to repeatedly remind the agent to check the vault, use NotebookLM, read PATTERNS.md. These tools compound — every time they're skipped, the system doesn't learn. The pre-flight blocker makes skipping physically impossible. The agent must show proof of each check before Oliver sees any output.

This is inspired by:
- **Aviation**: Pre-flight checklists that computers enforce, not pilots remember
- **Google SRE**: Production readiness reviews that block deployment until verified
- **Amazon**: Operational readiness reviews before any launch
- **Stripe**: No code ships without passing CI — our version is "no output ships without passing pre-flight"
