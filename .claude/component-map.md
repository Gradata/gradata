# AIOS Component Map

> Single reference for every named component in the system.
> When a change is made, this file tells you what was affected and where.
> Updated whenever components are added, renamed, or removed.

## Layers

| Layer | What it is | Files |
|-------|-----------|-------|
| **AIOS** | Company-agnostic operating system | CLAUDE.md, .carl/global, .carl/agents, .claude/*, soul.md |
| **Domain** | Sprites-specific sales ops | domain/*, domain/carl/*, domain/gates/* |
| **Brain** | Persistent memory vault | C:/Users/olive/SpritesWork/brain/* |

## Core Components

| Component | What it does | File(s) | Layer |
|-----------|-------------|---------|-------|
| **CLAUDE.md** | Master rules — session flow, work style, wrap-up steps | CLAUDE.md | AIOS |
| **DOMAIN.md** | Sprites config — role, ICP, tools, pipeline rules | domain/DOMAIN.md | Domain |
| **CARL Manifest** | Routes which CARL domains load and when | .carl/manifest | AIOS |
| **Agent Manifest Schema** | Second universal standard (alongside Score). Governs agent permissions, trust, context, agent-local rules. | agents/manifest-schema.md | AIOS |
| **Self-Model** | Live capability assessment — reliability per output type, blind spots, resource state. Read at session start. | brain/self-model.md | Brain |
| **Eval Suite** | Held-out golden test cases for regression detection after system changes. | brain/evals/ | Brain |
| **Rule Constitution** | Meta-rules governing how rules are created, modified, retired. Oliver-only modification. | .carl/global (CONSTITUTION_1-5) | AIOS |
| **Agent Scaffold** | Skill to create new agents with manifest + instructions + wiring | skills/agent-scaffold/SKILL.md | AIOS |
| **Escalation Ladder** | Graduated in-task error response: 3→change strategy, 4→reduce scope, 5→stop | .claude/fallback-chains.md (section) | AIOS |
| **5-Point Verification** | Consolidated verification: INPUT → GOAL → ADVERSARIAL → VOICE → SCORE (replaced 9-step stack) | .claude/gates.md (section) | AIOS |

## CARL Domains (behavioral rules)

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| **Global** | 4 universal rules (truth, honesty, complexity, conflict) | .carl/global | AIOS |
| **Domain Global** | Domain rules (research protocol, CCQ, OOO, credit gate) | domain/carl/global | Domain |
| **Safety** | Structural protections (never delete, never force-push) | .carl/safety | AIOS |
| **Context** | Context window bracket detection | .carl/context | AIOS |
| **Loop** | 60+ rules for closed-loop sales intelligence | domain/carl/loop | Domain |
| **Demo-Prep** | Demo research and cheat sheet rules | domain/carl/demo-prep | Domain |
| **Prospect-Email** | Email drafting rules (CCQ, personalization) | domain/carl/prospect-email | Domain |
| **Coldcall** | Phone script and voicemail rules | domain/carl/coldcall | Domain |
| **LinkedIn** | DM/InMail outreach rules | domain/carl/linkedin | Domain |
| **Listbuild** | Lead enrichment pipeline rules | domain/carl/listbuild | Domain |
| **Agents** | Multi-agent framework (types, contracts, boundaries) | .carl/agents | AIOS |
| **Domain Agents** | Sprites agent roster (research, draft, CRM, audit) | domain/carl/agents | Domain |

## Quality & Scoring

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| **Quality Rubrics** | Self-score protocol, confidence flags, blocking gate, metacognitive honesty | .claude/quality-rubrics.md | AIOS |
| **Auditor** | Session scoring, weight tiers (FULL/STANDARD/COMPRESSED/ABBREVIATED), calibration | .claude/auditor-system.md | AIOS |
| **Pre-flight** | Verification checklist before any prospect output | .claude/preflight.md | AIOS |
| **Humanizer** | 24-pattern AI writing detection, two-pass rewrite | soul.md (section) + /humanizer skill | AIOS |

## Gates (research → checkpoint → approval → output)

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| **Gate Protocol** | Universal gate execution framework (tag block, objection check, score) | .claude/gates.md | AIOS |
| **Integration Gate** | HARD GATE: every system addition must wire into neural bus + cross-wires + component map. No orphans. | .claude/gates.md | AIOS |
| **Pre-Draft** | 7-step research before any email | domain/gates/pre-draft.md | Domain |
| **Demo-Prep** | 13-step research before any demo cheat sheet | domain/gates/demo-prep.md | Domain |
| **Post-Demo** | Fireflies transcript required before follow-up | domain/gates/post-demo.md | Domain |
| **Cold-Call** | LinkedIn visit required before script | domain/gates/cold-call.md | Domain |
| **LinkedIn** | Profile visit required before DM | domain/gates/linkedin.md | Domain |
| **Pipedrive-Note** | Source verification before CRM publish | domain/gates/pipedrive-note.md | Domain |
| **Win/Loss** | Debrief required on every close | domain/gates/win-loss.md | Domain |

## Reflection System (detect → score → block → learn → escalate)

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| **Capture Hook** | Auto-detects corrections in real-time during session | .claude/hooks/reflect/scripts/capture_learning.py | AIOS |
| **Self-Score Protocol** | Confidence flag + score + fix-before-score + gap statement + blocking gate (<7) — unified in SCORE step of 5-Point Verification | .claude/quality-rubrics.md | AIOS |
| **/reflect** | Processes queued learnings, routes to CLAUDE.md or lessons.md | .claude/commands/reflect.md | AIOS |
| **Double-Loop** | After identifying what went wrong, asks what ALLOWED it (system gap) | .claude/commands/reflect.md (Step 4) | AIOS |
| **Micro-Reflections** | Lightweight integration check on every system addition | .claude/micro-reflections.md | AIOS |
| **Reflect-Patterns** | Root cause feed — written by /reflect, read by LOOP_RULE_45 | brain/sessions/reflect-patterns.md | Brain |
| **LOOP_RULE_32** | Rubric drift auto-tighten (3x self-score correction → rubric change) | domain/carl/loop | Domain |
| **LOOP_RULE_45** | Pattern escalation (3+ root causes without rule change → surface) | domain/carl/loop | Domain |
| **Heartbeat** | Every 10 outputs, auto-run /reflect mid-session | .claude/gap-scanner.md | AIOS |
| **Post-Commit Auto-Fire** | /reflect fires automatically after every git commit | .claude/hooks/reflect/scripts/post_commit_reminder.py | AIOS |
| **Pre-Commit Gate** | Must run /reflect + review provisionals + verify no unoverridden blocks before git | skills/wrap-up/SKILL.md (Phase 5c) | AIOS |

## Nervous System (sense → signal → respond)

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| **Neural Bus** | Session-level signal file with typed taxonomy (12 signal types). Systems write events, other systems read before acting. | brain/sessions/neural-bus.md | Brain |
| **Signal Taxonomy** | Typed signals (SAFETY_BLOCK, FALLBACK_FIRED, GATE_CATCH, SKILL_MISS, CORRECTION, etc.) with defined writer→reader contracts | brain/sessions/neural-bus.md | Brain |
| **Launch Validator** | Pre-session integrity check (headers, staleness, inter-session mods, RAG graduation). Emits LAUNCH_CHECK signal. | brain/scripts/launch.py | Brain |
| **Staleness Sensor** | Scans brain files >7 days stale at session start. Emits STALE_FILE signals. | skills/session-start/SKILL.md (Phase 0) | AIOS |
| **Gap Scanner** | Mid-session scan for skipped steps, unused tools, missing pre-flights | .claude/gap-scanner.md | AIOS |
| **Metacognitive Scan** | 60-second "what did this session reveal about AIOS" before wrap-up | skills/wrap-up/SKILL.md (Pre-Phase) | AIOS |
| **Cross-Wires** | 3-class feedback system: 12 event triggers (CW-1→12), 4 trend triggers (CW-13→16), 4 danger signals (DS-1→4). Utility-scored. | .claude/cross-wire-checklist.md | AIOS |
| **CW-8 Skill Miss** | Skill didn't auto-trigger → fix description keywords (from skills article) | .claude/cross-wire-checklist.md | AIOS |
| **CW-9 Safety Verdict** | Every safety block gets a verdict (legit vs false positive) — never just logged (from nova-tracer) | .claude/cross-wire-checklist.md | AIOS |
| **CW-10 Tool Violation** | Tool denied by manifest → check if allowlist needs updating or agent overstepped (DORMANT) | .claude/cross-wire-checklist.md | AIOS |
| **CW-11 Correction Rate** | Track correction rate → adjust trust_level up or down. Feeds graduated trust. | .claude/cross-wire-checklist.md | AIOS |
| **CW-12 Escalation → Lessons** | REDUCE_SCOPE or STOP escalation auto-generates a lesson | .claude/cross-wire-checklist.md | AIOS |

## Session Flow

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| **Session-Start** | Lazy-load startup (delta scan, heartbeat, brief, calendar, prospects) | skills/session-start/SKILL.md | AIOS |
| **Wrap-Up** | End-of-session (weight → ship → remember → review → anti-bloat → health → note → gate → git) | skills/wrap-up/SKILL.md | AIOS |
| **Session Weight** | Auto-calculates wrap-up depth (Light/Medium/Heavy/Structural) | skills/wrap-up/SKILL.md (Phase 0) | AIOS |
| **Session Note** | 10-section hard-gated note (Oliver's Summary through Line Counts) | skills/wrap-up/SKILL.md (Phase 5b) | AIOS |
| **Handoff** | Rewrites loop-state.md — pipeline snapshot, priorities, what changed | brain/loop-state.md | Brain |
| **Startup Brief** | Pipeline source of truth, refreshed every session | domain/pipeline/startup-brief.md | Domain |

## Fallback & Recovery

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| **Fallback Chains** | Generic tool failure framework + cost hierarchy | .claude/fallback-chains.md | AIOS |
| **Domain Overrides** | Sprites tool-specific fallbacks (Pipedrive, Apollo, Gmail, Fireflies) | domain/pipeline/fallback-overrides.md | Domain |
| **NotebookLM 3-Tier** | MCP → CLI → manual browser flag | .claude/skills/notebooklm/SKILL.md | AIOS |
| **Git Safety** | 3-tier: auto-commit (wrap-up) → stable tags (manual) → recovery branch (dual-confirm) | skills/wrap-up/SKILL.md (Phase 6) | AIOS |

## Learning & Compounding

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| **Lessons** | Active behavioral corrections with provisional/confirmed lifecycle | .claude/lessons.md | AIOS |
| **Lessons Archive** | Graduated lessons (reference only) | .claude/lessons-archive.md | AIOS |
| **PATTERNS.md** | Data-driven angle/tone/persona performance from tagged interactions | brain/emails/PATTERNS.md | Brain |
| **System Patterns** | Component effectiveness tracking (gates, lessons, smoke checks, audits) | brain/system-patterns.md | Brain |
| **Quality Loop** | Every-5-sessions system evaluation (scorecard, diagnose, fix) | skills/quality-loop/SKILL.md | AIOS |
| **NotebookLM Feeds** | Post-call/demo data fed back into notebooks for compounding | domain/notebooks/registry.md | Domain |

## Periodic Audits

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| **Periodic Audit Schedule** | Session-counted triggers for recurring audits (SDK, memory, RAG, bloat, self-audit) | .claude/periodic-audits.md | AIOS |
| **/sdk-audit** | SDK boundary enforcement — scans core files for Sprites contamination | .claude/commands/sdk-audit.md | AIOS |
| **SDK North Star** | Strategic context: Sprites Work vs Starter SDK boundary definition | brain/vault/sdk-north-star.md | Brain |
| **Self-Audit** | Compounding intelligence review — error patterns, outcome retrospective, judgment calibration. The mechanism that turns accumulated data into expertise. Every 10 sessions. | skills/self-audit/SKILL.md | AIOS |
| **Outcome Retrospectives** | Append-only vault of tactic→result pattern insights. Written by self-audit Lens 2. | brain/vault/outcome-retrospectives.md | Brain |
| **Judgment Calibration** | Append-only vault of decision evaluations against brain state at time of decision. Written by self-audit Lens 3. The proof of expertise development. | brain/vault/judgment-calibration.md | Brain |

## RAG Pipeline

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| **Config** | Shared paths, Gemini model settings, graduation thresholds, episodic/confidence/outcome config | brain/scripts/config.py | Brain |
| **Launch Validator** | Pre-session integrity: header consistency, staleness, RAG graduation check | brain/scripts/launch.py | Brain |
| **Embed** | Delta embedding with outcome linking + session metadata (hash-based, ChromaDB, Gemini) | brain/scripts/embed.py | Brain |
| **Query** | Semantic search with episodic recency weighting, confidence scoring, outcome surfacing | brain/scripts/query.py | Brain |
| **Session Launcher** | Single entry point: pre-flight → state restore → Claude Code launch | brain/scripts/start.py | Brain |
| **Graduation** | RAG activates at 20+ sessions. Domain packs can override threshold. | brain/scripts/config.py (RAG_ACTIVATION_THRESHOLD) | Brain |

## Voice & Writing

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| **Soul (Generic)** | Writing voice, tone rules, banned phrases, quality scoring | soul.md | AIOS |
| **Soul (Domain)** | Sprites email frameworks (CCQ, Inbound, Follow-Up), persona, signature | domain/soul.md | Domain |

## Statusline

| Component | What it does | File | Layer |
|-----------|-------------|------|-------|
| **Statusline** | Domain-aware status bar (domain name, skills, CARL, prospects, lessons, keys) | .claude/hooks/sprites-statusline.js | AIOS |
| **Prospect Counter** | Counts brain/prospects/ files with next_touch within 48h + overdue | .claude/hooks/sprites-statusline.js | AIOS |
