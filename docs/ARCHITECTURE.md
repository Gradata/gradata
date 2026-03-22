# Sprites.ai Sales Agent — System Architecture

## Overview

Autonomous AI sales agent built on Claude Code with recursive self-improvement capabilities. Manages the full deal lifecycle from prospecting through close with integrated CRM, email, calendar, and meeting intelligence. The system learns from every interaction, tracks its own component health, and self-optimizes through a five-layer intelligence architecture.

## Architecture Layers

### Layer 1: Sales Intelligence (Loop)

Closed-loop learning engine applied to all sales activities — emails, calls, demos, proposals, closes.

- **Tag → Track → Learn → Improve** cycle on every prospect interaction
- 82K+ email dataset seeding pattern recognition (cold tier via Instantly)
- Two-tier data model: Cold (bulk outreach, read-only) + Pipeline (personalized, Claude-written)
- Confidence-weighted recommendations with sample sizes: INSUFFICIENT (<3) → HYPOTHESIS (3-9) → EMERGING (10-25) → PROVEN (25-50) → HIGH CONFIDENCE (50-100) → DEFINITIVE (100+)
- Framework auto-selection: CCQ, Gap Selling, JOLT, SPIN, Challenger, Cohan — routed by persona and tracked conversion rates
- Pre-action pattern check prevents repeating failed angles; 70/30 proven/experimental split

### Layer 2: Component Monitoring (System Loop)

Same pattern as Layer 1 but applied to the system itself. Every internal component is tracked for effectiveness.

- 25+ tracked components across quality gates, lessons, smoke checks, startup/wrap-up execution, CARL routing, fallback chains
- Automated audit scoring with 8.0 minimum quality gate (hard gate — session cannot close below 8.0)
- Session-over-session trend analysis with lowest-dimension identification
- Ping-pong audit protocol: gaps found → concede/defend/partial → changes written
- Bloat prevention: file size limits, lesson caps, session note rotation, active prospect ceiling

### Layer 3: Cross-Wiring (Bidirectional Feedback)

Automated connections between system components that fire procedurally every session.

| Connection | Rule | Purpose |
|------------|------|---------|
| Auditor → Gates | R34 | Audit findings tighten gate steps |
| Gates → Lessons | R35 | Gate catches become logged lessons |
| Lessons → CARL | R36 | Repeated lessons become permanent rules |
| Smoke → Lessons | R37 | Smoke check failures generate lessons |
| Rubric Drift → Tighten | R38 | Self-score drift triggers rubric recalibration |
| Fallback → Reorder | R39 | Better-performing fallbacks get promoted to primary |
| PATTERNS → Gates | R40 | Pattern insights update gate checklists |

These are procedural execution checklists — they run every session, not aspirationally.

### Layer 4: Meta-Optimization

Tracks which event connections and hooks actually produce value and prunes the ones that do not.

- Reviews hook/event connection performance every 5 sessions
- Kill switch: 5 consecutive cycles of zero value → connection goes DORMANT
- Self-evaluates after 3 cycles (session 18) — determines if meta-optimization itself improves the system
- Prevents unbounded complexity growth in the event/hook layer

### Layer 5: Convergence Detection

Monitors whether the system is stabilizing or still forming, and adjusts optimization frequency accordingly.

| Indicator | Threshold | Purpose |
|-----------|-----------|---------|
| Sessions since last new lesson | 3 | Learning rate slowdown |
| Sessions since last rule change | 3 | Rule stability |
| Sessions since last gate catch | 3 | Gate effectiveness plateau |
| Avg audit score (last 5) | 9.0+ | Quality maturity |
| Event connection dormancy rate | >50% stable | Hook/event maturation |

- At convergence: optimization frequency reduces from every 5 sessions to every 10
- Divergence detection re-enables aggressive optimization on regression
- Current state: FORMING (0/5 indicators stable as of session 4)

## Data Infrastructure

- **SQLite Database**: Queryable backing store for deals, signals, frameworks, audit history, event connections
- **Markdown Views**: Human-readable views of database state for context loading (system-patterns.md, PATTERNS.md, prospect notes)
- **CARL Rule Engine**: ~60 rules across 10 domains (global, context, commands, loop, agents, prospect-email, demo-prep, coldcall, linkedin, listbuild) with keyword-triggered lazy loading
- **Brain Vault**: Structured knowledge store — prospects, pipeline data, email patterns, system patterns, loop state handoffs

## Quality Assurance

- **Mandatory gates** before every output: Pre-Draft (7-step), Demo Prep (8-step), Post-Demo Follow-Up, Cold Call, LinkedIn, Pipedrive Notes, Win/Loss, Calendar Check
- **Self-scoring** with calibration against human feedback (quality-rubrics.md)
- **Event-driven hooks** prevent recurring failures from persisting
- **Rule validation** detects conflicts and dead references
- **Auditor system** with ping-pong protocol — independent scoring, gap identification, fix cycles
- **Loop audit** — separate audit focused on sales intelligence effectiveness
- **Health audit** — comprehensive system health check across files, vault, MCPs, credits, process, data, learning

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
- 2+ point score divergence between draft and audit → flagged for human review
- Every spawn logged: agent type, task, I/O contract, boundary violations
- Cost control: maximum 5 subagents per session unless explicitly approved

## Key Metrics

| Metric | Value |
|--------|-------|
| CARL rules governing behavior | ~60 across 10 domains |
| Event connections | Hooks + events.jsonl queries |
| Convergence indicators | 5 tracking system maturity |
| Quality gates | 8 mandatory checkpoints |
| Tracked system components | 25+ |
| Cold email dataset | 82K+ for pattern seeding |
| Agent boundary rules | 5 hard enforcement rules |
| Audit minimum score | 8.0 (hard gate) |
| Max subagents per session | 5 (cost-controlled) |
| Pipeline health model | Calibrates at 15+ closed deals |
| Complexity budget ceiling | 100 CARL rules, 10 event connections, 5 meta-trackers, 3 optimization layers |

## ICP (Ideal Customer Profile)

Multi-brand ecommerce, PE rollups, franchise groups, solo consultants, lean DTC, agencies. 10-300 employees. Running Meta Pixel and/or Google Ads. US primary market, UK/CA/AU/NZ/EU secondary.
