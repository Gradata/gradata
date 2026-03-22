# AIOS Component Map v2.0

> Single reference for every active component. Updated when components change.

## Layers

| Layer | What | Files |
|-------|------|-------|
| **AIOS** | Company-agnostic OS | CLAUDE.md, .carl/global, .claude/*, hooks/ |
| **Domain** | Sprites-specific sales ops | domain/*, domain/carl/*, domain/gates/* |
| **Brain** | Persistent memory vault | C:/Users/olive/SpritesWork/brain/* |

## Core

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| CLAUDE.md | Master rules — session flow, work style, maturity | CLAUDE.md | AIOS |
| DOMAIN.md | Sprites config — role, ICP, tools, pipeline | domain/DOMAIN.md | Domain |
| CARL Manifest | Routes which CARL domains load and when | .carl/manifest | AIOS |
| Work Style | Detailed behavioral rules (loaded Tier 1) | .claude/work-style.md | AIOS |
| Self-Improvement | Instinct->Pattern->Rule pipeline | .claude/self-improvement.md | AIOS |
| Rule Constitution | Meta-rules for rule creation/modification | .carl/global (CONSTITUTION_1-5) | AIOS |
| Escalation Ladder | 3->change strategy, 4->reduce scope, 5->stop | .claude/fallback-chains.md | AIOS |
| 5-Point Verification | INPUT->GOAL->ADVERSARIAL->VOICE->SCORE | .claude/gates.md | AIOS |

## CARL Domains

| Component | File | Layer |
|-----------|------|-------|
| Global (4 universal rules) | .carl/global | AIOS |
| Domain Global (research, CCQ, credit gate) | domain/carl/global | Domain |
| Safety (structural protections) | .carl/safety | AIOS |
| Context (bracket detection) | .carl/context | AIOS |
| Loop (60+ closed-loop rules) | domain/carl/loop | Domain |
| Demo-Prep | domain/carl/demo-prep | Domain |
| Prospect-Email | domain/carl/prospect-email | Domain |
| Coldcall | domain/carl/coldcall | Domain |
| LinkedIn | domain/carl/linkedin | Domain |
| Listbuild | domain/carl/listbuild | Domain |
| Agents | .carl/agents + domain/carl/agents | AIOS+Domain |

## Quality & Scoring

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| Quality Rubrics | Self-score protocol, blocking gate | .claude/quality-rubrics.md | AIOS |
| Auditor | Session scoring, 8.0+ gate, calibration | .claude/auditor-system.md | AIOS |
| Pre-flight | Verification before prospect output | .claude/preflight.md | AIOS |
| Humanizer | AI pattern detection, rewrite | soul.md + /humanizer | AIOS |

## Gates

| Component | File | Layer |
|-----------|------|-------|
| Gate Protocol (universal) | .claude/gates.md | AIOS |
| Pre-Draft (7-step research) | domain/gates/pre-draft.md | Domain |
| Demo-Prep (13-step) | domain/gates/demo-prep.md | Domain |
| Post-Demo (Fireflies required) | domain/gates/post-demo.md | Domain |
| Cold-Call (LinkedIn required) | domain/gates/cold-call.md | Domain |
| LinkedIn (profile required) | domain/gates/linkedin.md | Domain |
| Pipedrive-Note (source verify) | domain/gates/pipedrive-note.md | Domain |
| Win/Loss (debrief required) | domain/gates/win-loss.md | Domain |

## Event System (replaced neural bus + cross-wires)

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| Events API | emit() + query() — dual-write JSONL+SQLite | brain/scripts/events.py | Brain |
| Events Log | Append-only event stream (SDK-portable) | brain/events.jsonl | Brain |
| Events Table | Queryable events in SQLite | brain/system.db (events) | Brain |
| Periodic Audits | Session-counted audit triggers | brain/system.db (periodic_audits) | Brain |

## Hooks (enforcement layer)

| Hook | Type | What it does | File |
|------|------|-------------|------|
| suggest-compact | PostToolUse | Compaction reminder at 50/75/100 tool calls | .claude/hooks/suggest-compact.js |
| cost-tracking | Stop | Log session token costs | .claude/hooks/cost-tracking.js |
| session-persist | Stop | Auto-save minimum handoff data | .claude/hooks/session-persist.js |
| quality-gate | PreToolUse:Write | Prospect-facing write reminder | .claude/hooks/quality-gate.js |
| mcp-health | PreToolUse:mcp__* | MCP server health + backoff | .claude/hooks/mcp-health.js |
| capture-learning | UserPromptSubmit | Real-time correction detection | .claude/hooks/reflect/scripts/capture_learning.py |
| delta-auto-tag | PostToolUse | Auto-tag prospect activities | .claude/hooks/delta-auto-tag.js |
| statusline | statusLine | 4-line context display | .claude/hooks/sprites-statusline.js |

## Session Flow

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| Session-Start | Lazy-load startup (delta scan, heartbeat, tools) | skills/session-start/SKILL.md | AIOS |
| Wrap-Up | 3-phase protocol + 3 agents | skills/wrap-up/SKILL.md | AIOS |
| Wrap-Up Validator | 10 mechanical checks, blocks commit on FAIL | brain/scripts/wrap_up_validator.py | Brain |
| Wrap-Up Automation | Mechanical steps (health, confidence, tags, cleanup) | brain/scripts/wrap_up.py | Brain |
| Handoff | Pipeline snapshot + priorities | brain/loop-state.md | Brain |
| Startup Brief | Pipeline source of truth | domain/pipeline/startup-brief.md | Domain |

## Reflection System

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| Capture Hook | Auto-detects corrections in real-time | .claude/hooks/reflect/scripts/capture_learning.py | AIOS |
| /reflect | Processes queued learnings, routes to files | .claude/commands/reflect.md | AIOS |
| Double-Loop | Asks what ALLOWED the error (system gap) | .claude/commands/reflect.md (Step 4) | AIOS |
| Reflect-Patterns | Root cause feed | brain/sessions/reflect-patterns.md | Brain |

## Fallback & Recovery

| Component | File | Layer |
|-----------|------|-------|
| Fallback Chains | .claude/fallback-chains.md | AIOS |
| Domain Overrides | domain/pipeline/fallback-overrides.md | Domain |
| NotebookLM 3-Tier | .claude/skills/notebooklm/SKILL.md | AIOS |
| Git Safety | skills/wrap-up/SKILL.md (Phase 6) | AIOS |

## Learning & Compounding

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| Lessons | Active instincts/patterns with confidence scores | .claude/lessons.md | AIOS |
| Lessons Archive | Graduated lessons (reference) | .claude/lessons-archive.md | AIOS |
| PATTERNS.md | Angle/tone/persona performance data | brain/emails/PATTERNS.md | Brain |
| System Patterns | Component effectiveness (read-only reference) | brain/system-patterns.md | Brain |

## Delta Measurement (untouched by v2.0)

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| Delta Tagger | Log activities, prep, outcomes to SQLite | brain/scripts/delta_tag.py | Brain |
| Delta Report | Monthly brain vs benchmark computation | brain/scripts/delta_report.py | Brain |
| Scorecard Delta | Evolution scorecard DELTA section | brain/scripts/evolution_scorecard.py | Brain |
| Marketplace Audit | 3-layer enterprise audit framework | brain/vault/marketplace-audit-framework.md | Brain |

## Agent Infrastructure

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| Agent Manifests | Declarative agent config (tools, paths, budget, trust) | .claude/agent-manifests.json | AIOS |
| Guardrails | Write path restrictions, exec validation, secret scanning | brain/scripts/guardrails.py | Brain |
| Secret Scan Hook | PostToolUse hook scanning writes for API keys/tokens | .claude/hooks/secret-scan.js | AIOS |
| Fact Extractor | Structured fact extraction from prospect markdown to SQLite | brain/scripts/fact_extractor.py | Brain |
| Enrichment Cache | Content-hash cache preventing double-dip enrichment | brain/scripts/enrichment_cache.py | Brain |
| Config Validator | Startup hook validating JSON configs | .claude/hooks/config-validate.js | AIOS |
| Context Budget | Startup hook enforcing file size limits | .claude/hooks/context-budget.js | AIOS |
| Skill Stocktake | Periodic audit of all skills for staleness/overlap/retirement | brain/scripts/skill_stocktake.py | Brain |
| Rules Distillation | Auto-detect lesson patterns for promotion to permanent rules | brain/scripts/rules_distill.py | Brain |
| Checkpoint | Named snapshots before parallel agents for rollback safety | brain/scripts/checkpoint.py | Brain |
| Cold-Start Plans | Multi-session work template with self-contained steps | .claude/templates/cold-start-plan.md | AIOS |

## Voice & Writing

| Component | File | Layer |
|-----------|------|-------|
| Soul (Generic) | soul.md | AIOS |
| Soul (Domain) | domain/soul.md | Domain |

## Statusline

| Component | File |
|-----------|------|
| Statusline v5 (context+pipeline+health+delta) | .claude/hooks/sprites-statusline.js |
