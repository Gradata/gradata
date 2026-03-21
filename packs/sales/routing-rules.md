# Learning Routing — Sales Pack

## Route 1: Behavioral Rule
**Target:** CLAUDE.md → most relevant existing section (default: `## Work Style Rules`)
**Criteria:** Universal directive. Applies across all sessions. Imperative voice.
**Format:** Single bullet point with `_Why:` italic suffix if reason isn't obvious.
**Examples:**
- "Always check Pipedrive before asking Oliver"
- "Never send emails without verifying threadId matches subject"
- "When replying to a prospect, search Gmail for Oliver's most recent sent email first"

### Sales-Specific Section Routing
| Signal in Learning | Target Section |
|-------------------|----------------|
| Research, free-first, paid tools, Apollo, Fireflies | `## Prospect Research Order` |
| Gate, checklist, pre-draft, demo prep, cold call | `## Mandatory Gates` |
| Voice, tone, writing, email, signature, banned words | `## Voice, Writing & Email Frameworks` |
| Pipedrive, CRM, deal, activity, sync | `## Pipedrive Auto-Sync` |
| ICP, segment, employee count, vertical | `## ICP` |
| Pattern, tag, outcome, confidence tier | `## Loop` |
| Tool, MCP, fallback, credits | `## Tool Stack` or `## Work Style Rules` |
| Default / unclear | `## Work Style Rules` |

## Route 2: Specific Mistake
**Target:** .claude/lessons.md
**Criteria:** Tied to an incident. Has root cause. Pattern: "did X → should have done Y"
**Format:** `[DATE] [PROVISIONAL:5] CATEGORY: What happened → What to do instead`
**Categories:**
| Category | What It Covers |
|----------|---------------|
| DRAFTING | Email structure, length, flow, missing sections |
| LANGUAGE | Word choice, banned words, jargon, filler |
| CTA | Call-to-action clarity, strength, placement |
| FORMAT | HTML formatting, links, whitespace, signature |
| TONE | Voice mismatch, too formal/casual, not matching Oliver |
| RESEARCH | Missed data source, wrong source priority, incomplete research |
| CRM | Pipedrive errors, wrong fields, missing activities, bad sync |
| PROCESS | Skipped gates, wrong order, missed steps |
| STRATEGY | Wrong angle, bad timing, misread prospect |
| ACCURACY | Wrong facts, hallucinated data, stale info |
| TOOL | Wrong tool used, tool misuse, fallback not followed |
| ICP | Misqualified lead, wrong segment, bad scoring |
| SIGNATURE | Wrong title, missing info, formatting errors |

## Route 3: Methodology Insight
**Target:** Manual review (present to Oliver with options)
**Criteria:** Strategic. Needs judgment. About approach, market, prospect psychology, or competitive intelligence.
**Action:** Present to Oliver — never auto-write. Offer these route options:
1. `brain/emails/PATTERNS.md` — if it's an outreach pattern (email angle, subject line, CTA)
2. `brain/prospects/[name].md` — if it's prospect-specific or company-specific
3. `CLAUDE.md` as a rule — only if Oliver confirms it's universal
4. `brain/pipeline/` — if it's about deal strategy or pipeline management
5. Skip for now

### Sales Insight Signals
These phrases suggest Route 3 (not Route 1 or 2):
- "This approach works better for [segment]"
- "PE rollups respond better to X than Y"
- "Gap selling outperforms CCQ for [type]"
- "The market is shifting toward..."
- "This objection pattern is effective when..."
- "Competitors are doing X, we should..."

## Upgrade Rule
When 3+ lessons in the same category share the same root cause, propose consolidation into a CLAUDE.md rule. Present the proposed rule to Oliver for approval before writing.
