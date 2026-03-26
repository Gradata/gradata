> **DEPRECATED (S65):** This is a pre-v2.0 overview. For the canonical architecture reference, see `sdk/SPEC.md`. This file is kept for historical context only.

# Sprites.ai Sales Agent — System Architecture (v2.1)

## Overview

Autonomous AI sales agent built on Claude Code with recursive self-improvement capabilities. Manages the full deal lifecycle from prospecting through close with integrated CRM, email, calendar, and meeting intelligence. The system learns from every interaction, tracks its own component health via an events backbone, and self-optimizes through a three-step improvement pipeline (Instinct -> Pattern -> Rule).

## Architecture

### Sales Intelligence (Loop)

Closed-loop learning engine applied to all sales activities — emails, calls, demos, proposals, closes.

- **Tag -> Track -> Learn -> Improve** cycle on every prospect interaction
- 82K+ email dataset seeding pattern recognition (cold tier via Instantly)
- Two-tier data model: Cold (bulk outreach, read-only) + Pipeline (personalized, Claude-written)
- Confidence-weighted recommendations with sample sizes: INSUFFICIENT (<3) -> HYPOTHESIS (3-9) -> EMERGING (10-25) -> PROVEN (25-50) -> HIGH CONFIDENCE (50-100) -> DEFINITIVE (100+)
- Framework auto-selection: CCQ, Gap Selling, JOLT, SPIN, Challenger, Cohan — routed by persona and tracked conversion rates
- Pre-action pattern check prevents repeating failed angles; 70/30 proven/experimental split

### Events Backbone (replaced neural bus + cross-wires in v2.0)

All system signals flow through a unified events layer. No separate cross-wire checklist, no neural bus markdown file.

- **events.jsonl** — append-only event stream (SDK-portable, brain layer)
- **system.db (events table)** — queryable SQLite mirror for aggregation and trend analysis
- **Event types:** CORRECTION, GATE_RESULT, AUDIT_SCORE, LESSON_CHANGE, COST_EVENT, TOOL_FAILURE, CALIBRATION, HEALTH_CHECK, DEFER, STEP_COMPLETE, OUTPUT, HALLUCINATION, STALE_DATA, GATE_OVERRIDE
- **emit() + query()** API in brain/scripts/events.py — dual-write to both stores
- Hooks consume events for enforcement; wrap-up queries events for scoring

### Quality System

Two tiers of quality enforcement:

**Per-output (inline):**
- Self-score against quality-rubrics.md — 7+ quality floor, block below 7
- Oliver's calibration overrides adjust rubric thresholds
- 5-point verification: INPUT -> GOAL -> ADVERSARIAL -> VOICE -> SCORE

**Per-session (wrap-up):**
- **15-check binary gate** via wrap_up_validator.py — 80% threshold required to close
- Auto-fix with up to 3 retry cycles before escalating
- **Brain Report Card** — 4 scores: System, AI Quality, Growth, Architecture
- Visible in statusline + wrap-up output

### Self-Improvement Pipeline

Three steps. No meta-layers. Evidence-driven. See .claude/self-improvement.md.

```
INSTINCT (confidence 0.00 - 0.59)
    |  +0.10 per session where it prevents a mistake
    |  -0.15 per session where Oliver corrects despite the rule
    v
PATTERN (confidence 0.60 - 0.89)
    |  Accumulates evidence via [TRACK:N/3]
    |  3+ fires across 2+ sessions -> promote
    v
RULE (confidence 0.90+)
    |  Permanent in CARL / CLAUDE.md / gates
    |  Kill switch by maturity phase (INFANT: 10 cycles)
    v
ARCHIVE (graduated, reference only)
```

### Self-Heal Infrastructure

- **Validator retry loop** — wrap_up_validator.py 15 checks, auto-fix up to 3 cycles
- **Startup self-heal** — session_start_reminder.py hook (6 automated checks), auto-creates events.jsonl if missing
- **Agnix** — config lint, auto-runs at startup
- **Ruff** — Python auto-fix at wrap-up
- **Biome** — JS lint
- **config-validate.js** — JSON config validation hook at startup

### Hooks (enforcement layer)

8 core hooks + 4 specialized hooks:

| Hook | Type | What it does |
|------|------|-------------|
| suggest-compact | PostToolUse | Compaction reminder at 50/75/100 tool calls |
| cost-tracking | Stop | Log session token costs |
| session-persist | Stop | Auto-save minimum handoff data |
| quality-gate | PreToolUse:Write | Prospect-facing write reminder |
| mcp-health | PreToolUse:mcp__* | MCP server health + backoff |
| context-budget | Startup | File size limit enforcement |
| config-validate | Startup | JSON config validation |
| secret-scan | PostToolUse | API key/token detection in writes |
| session-start-reminder | Startup | 6 automated system checks |
| delta-auto-tag | PostToolUse | Auto-tag prospect activities |
| sprites-statusline | statusLine | 4-line context display (Report Card + pipeline + health + delta) |
| gsd | Various | Task execution hooks |

## Data Infrastructure

- **SQLite Database** (brain/system.db): Queryable backing store for events, periodic audits, delta tags, deals, signals
- **events.jsonl**: Append-only event stream — primary audit trail
- **Markdown Views**: Human-readable views for context loading (system-patterns.md, PATTERNS.md, prospect notes)
- **CARL Rule Engine**: ~109 rules across 10 domains with keyword-triggered lazy loading
- **Brain Vault**: Structured knowledge store — prospects, pipeline data, email patterns, system patterns, loop state handoffs

## Quality Assurance

- **Mandatory gates** before every output: Pre-Draft (7-step), Demo Prep (13-step), Post-Demo Follow-Up, Cold Call, LinkedIn, Pipedrive Notes, Win/Loss, Calendar Check
- **Self-scoring** with calibration against human feedback (quality-rubrics.md) — 7+ floor
- **15-check binary gate** at wrap-up (80% threshold, auto-fix 3 cycles)
- **Brain Report Card** — 4 scores visible in statusline
- **Event-driven hooks** prevent recurring failures from persisting
- **Rule validation** (Agnix) detects conflicts and dead references

## Integration Layer

| Tool | Purpose | Access Pattern |
|------|---------|---------------|
| Gmail | Drafts, thread matching, search | MCP — HTML drafts with thread ID verification |
| Google Calendar | Scheduling, meeting detection | MCP — 2-month lookahead before any task |
| Pipedrive CRM | Deal management, activity logging | Composio MCP — Oliver-tagged deals only (label 45) |
| Apollo | Contact enrichment, company data | MCP + browser fallback — batch queries, no double-dip |
| Fireflies | Meeting transcription, call scoring | MCP — search by attendee email across all team members |
| Instantly | Cold outreach data | MCP — read-only, 82K+ emails, never overlaps with CRM |
| Calendly | Booking link | Static link in all CTAs |
| Clay | Deep enrichment | Sparingly, when Apollo insufficient |
| NotebookLM | Persona pattern research | 7 notebooks, on-demand |
| Apify | Web scraping | On-demand for list building |
| Prospeo/ZeroBounce | Email finding/verification | List building pipeline |

## Multi-Agent Architecture

Four specialized agent types with enforced boundaries and an orchestrator:

| Agent | Scope | Cannot Do |
|-------|-------|-----------|
| Research Agent | Apollo, LinkedIn, web, Fireflies, NotebookLM | Draft emails, update CRM, approve output |
| Draft Agent | Email, scripts, proposals, LinkedIn messages | Research, update CRM, approve own output |
| CRM Agent | Pipedrive reads/writes, deal updates, activity logging | Draft communications, research, strategy |
| Audit Agent | Quality scoring, gate verification, pattern analysis | Fix issues it finds (separation of concerns) |

**Hard boundaries enforced:**
- Research agent prompts must not include drafting instructions
- Draft agent receives research output as input, no research tool access
- Audit agent never sees draft agent's self-score (prevents self-grading bias leakage)
- 2+ point score divergence between draft and audit -> flagged for human review
- Every spawn logged: agent type, task, I/O contract, boundary violations
- Cost control: maximum 5 subagents per session unless explicitly approved

## Key Metrics

| Metric | Value |
|--------|-------|
| CARL rules governing behavior | ~109 across 10 domains |
| Event types tracked | 14 via events backbone |
| Hooks (enforcement layer) | 8 core + 4 specialized |
| Quality gates | 8 mandatory checkpoints |
| Tracked system components | 25+ |
| Cold email dataset | 82K+ for pattern seeding |
| Agent boundary rules | 5 hard enforcement rules |
| Wrap-up gate | 15-check binary, 80% threshold |
| Per-output quality floor | 7/10 (self-score, Oliver calibrates) |
| Max subagents per session | 5 (cost-controlled) |
| Pipeline health model | Calibrates at 15+ closed deals |
| Self-improvement pipeline | Instinct -> Pattern -> Rule (confidence-scored) |

## ICP (Ideal Customer Profile)

Multi-brand ecommerce, PE rollups, franchise groups, solo consultants, lean DTC, agencies. 10-300 employees. Running Meta Pixel and/or Google Ads. US primary market, UK/CA/AU/NZ/EU secondary.
