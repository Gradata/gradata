# Gradata Component Map v3.0

> Single reference for every active component. Updated when components change.

## Layers

| Layer | What | Files |
|-------|------|-------|
| **Gradata** | Company-agnostic OS | CLAUDE.md, .carl/global, .claude/*, hooks/ |
| **Domain** | Sprites-specific sales ops | domain/*, domain/carl/*, domain/gates/* |
| **Brain** | Persistent memory vault | C:/Users/olive/SpritesWork/brain/* |

## Core

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| CLAUDE.md | Master rules — session flow, work style, maturity | CLAUDE.md | Gradata |
| DOMAIN.md | Sprites config — role, ICP, tools, pipeline | domain/DOMAIN.md | Domain |
| CARL Manifest | Routes which CARL domains load and when | .carl/manifest | Gradata |
| Work Style | Detailed behavioral rules (loaded Tier 1) | .claude/work-style.md | Gradata |
| Self-Improvement | Instinct->Pattern->Rule pipeline | .claude/self-improvement.md | Gradata |
| Rule Constitution | Meta-rules for rule creation/modification | .carl/global (CONSTITUTION_1-5) | Gradata |
| Escalation Ladder | 3->change strategy, 4->reduce scope, 5->stop | .claude/fallback-chains.md | Gradata |
| 5-Point Verification | INPUT->GOAL->ADVERSARIAL->VOICE->SCORE | .claude/gates.md | Gradata |

## CARL Domains

| Component | File | Layer |
|-----------|------|-------|
| Global (4 universal rules) | .carl/global | Gradata |
| Domain Global (research, CCQ, credit gate) | domain/carl/global | Domain |
| Safety (structural protections) | .carl/safety | Gradata |
| Context (bracket detection) | .carl/context | Gradata |
| Loop (60+ closed-loop rules) | domain/carl/loop | Domain |
| Demo-Prep | domain/carl/demo-prep | Domain |
| Prospect-Email | domain/carl/prospect-email | Domain |
| Coldcall | domain/carl/coldcall | Domain |
| LinkedIn | domain/carl/linkedin | Domain |
| Listbuild | domain/carl/listbuild | Domain |
| Agents | .carl/agents + domain/carl/agents | Gradata+Domain |

## Quality & Scoring

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| Quality Rubrics | Per-output self-score, 7+ blocking gate | .claude/quality-rubrics.md | Gradata |
| Binary Gate | 15-check wrap-up validator, 80% threshold, 3 auto-fix cycles | brain/scripts/wrap_up_validator.py | Brain |
| Brain Report Card | 4 scores: System, AI Quality, Growth, Arch | wrap-up protocol | Gradata |
| Pre-flight | Verification before prospect output | .claude/preflight.md | Gradata |
| Humanizer | AI pattern detection, rewrite | soul.md + /humanizer | Gradata |

## Gates

| Component | File | Layer |
|-----------|------|-------|
| Gate Protocol (universal) | .claude/gates.md | Gradata |
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
| suggest-compact | PostToolUse | Compaction reminder at 50/75/100 tool calls | .claude/hooks/post-tool/suggest-compact.js |
| cost-tracking | Stop | Log session token costs | .claude/hooks/stop/cost-tracking.js |
| session-persist | Stop | Auto-save minimum handoff data | .claude/hooks/stop/session-persist.js |
| quality-gate | PreToolUse:Write | Prospect-facing write reminder | .claude/hooks/pre-tool/quality-gate.js |
| mcp-health | PreToolUse:mcp__* | MCP server health + backoff | .claude/hooks/pre-tool/mcp-health.js |
| capture-learning | UserPromptSubmit | Real-time correction detection | .claude/hooks/reflect/scripts/capture_learning.py |
| delta-auto-tag | PostToolUse | Auto-tag prospect activities | .claude/hooks/post-tool/delta-auto-tag.js |
| statusline | statusLine | 4-line context display | .claude/hooks/statusline/sprites-statusline.js |

## Session Flow

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| Session-Start | Lazy-load startup (delta scan, heartbeat, tools) | skills/core/session-start/SKILL.md | Gradata |
| Wrap-Up | 3-phase protocol + 3 agents | skills/core/wrap-up/SKILL.md | Gradata |
| Wrap-Up Validator | 10 mechanical checks, blocks commit on FAIL | brain/scripts/wrap_up_validator.py | Brain |
| Wrap-Up Automation | Mechanical steps (health, confidence, tags, cleanup) | brain/scripts/wrap_up.py | Brain |
| Handoff | Pipeline snapshot + priorities | brain/loop-state.md | Brain |
| Startup Brief | Pipeline source of truth | domain/pipeline/startup-brief.md | Domain |

## Reflection System

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| Capture Hook | Auto-detects corrections in real-time | .claude/hooks/reflect/scripts/capture_learning.py | Gradata |
| /reflect | Processes queued learnings, routes to files | .claude/commands/reflect.md | Gradata |
| Double-Loop | Asks what ALLOWED the error (system gap) | .claude/commands/reflect.md (Step 4) | Gradata |
| Reflect-Patterns | Root cause feed | brain/sessions/reflect-patterns.md | Brain |

## Fallback & Recovery

| Component | File | Layer |
|-----------|------|-------|
| Fallback Chains | .claude/fallback-chains.md | Gradata |
| Domain Overrides | domain/pipeline/fallback-overrides.md | Domain |
| NotebookLM 3-Tier | .claude/skills/notebooklm/SKILL.md | Gradata |
| Git Safety | skills/core/wrap-up/SKILL.md (Phase 6) | Gradata |

## Learning & Compounding

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| Lessons | Active instincts/patterns with confidence scores | .claude/lessons.md | Gradata |
| Lessons Archive | Graduated lessons (reference) | .claude/lessons-archive.md | Gradata |
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
| Guardrails | Write path restrictions, exec validation, secret scanning | brain/scripts/guardrails.py | Brain |
| Secret Scan Hook | PreToolUse hook scanning writes for API keys/tokens | .claude/hooks/pre-tool/secret-scan.js | Gradata |
| Fact Extractor | Structured fact extraction from prospect markdown to SQLite | brain/scripts/fact_extractor.py | Brain |
| Enrichment Cache | Content-hash cache preventing double-dip enrichment | brain/scripts/enrichment_cache.py | Brain |
| Config Validator | Startup hook validating JSON configs | .claude/hooks/session-start/config-validate.js | Gradata |
| Skill Stocktake | Periodic audit of all skills for staleness/overlap/retirement | brain/scripts/skill_stocktake.py | Brain |
| Rules Distillation | Auto-detect lesson patterns for promotion to permanent rules | brain/scripts/rules_distill.py | Brain |
| Checkpoint | Named snapshots before parallel agents for rollback safety | brain/scripts/checkpoint.py | Brain |
| Cold-Start Plans | Multi-session work template with self-contained steps | .claude/templates/cold-start-plan.md | Gradata |

## Voice & Writing

| Component | File | Layer |
|-----------|------|-------|
| Soul (Voice + Writing) | domain/soul.md | Domain |

## Skills Inventory (250 total, post-S73 purge)

| Category | Count | Key Skills |
|----------|-------|------------|
| **core/** | 9 | session-start, wrap-up, self-improving-agent, loop, quality-loop, rule-validator |
| **dev/** | 45 | fitfo, adversarial-review, agenthub, tdd-guide, focused-fix, playwright-pro |
| **marketing/** | 41+90 nested | c-level-advisor (28 sub), marketing-skill (40 sub), minimalist-entrepreneur (10 sub) |
| **sales/** | 22 | cold-email, lead-pipeline, enrich, competitor-research, sales-skills (9 sub) |
| **tools/** | 12 | xlsx, pptx, pdf, obsidian-cli, n8n (7 sub), prompt-master |

## Statusline

| Component | File |
|-----------|------|
| Statusline v5 (context+pipeline+health+delta) | .claude/hooks/statusline/sprites-statusline.js |
