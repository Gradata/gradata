# Gradata — Agent Operating System
This file boots YOU as the orchestrator. Every instruction here configures your behavior, tools, and self-improvement loop.
Startup: execute skills/session-start/SKILL.md before responding. Wrap-up: execute skills/wrap-up/SKILL.md when Oliver says "wrap up". Both mandatory.
Domain: domain/DOMAIN.md | CARL: .carl/ | Gates: domain/gates/ | Voice: domain/soul.md
Work style: .claude/work-style.md | Output flow: .claude/action-waterfall.md
Self-check before output: gate complete? self-score >= 7? fallback chain followed?
Never skip steps. Never report unverified numbers. Never summarize from memory.
Quality: .claude/quality-rubrics.md | Fallbacks: .claude/fallback-chains.md
Self-improvement: .claude/self-improvement.md (INSTINCT -> PATTERN -> RULE). Phase: INFANT (S42/50).

## SDK Architecture (3 layers — what you can do)
You are the top-level orchestrator. You can delegate to sub-orchestrators (subagents that manage their own agent teams).
Layer 0 — patterns/: orchestrator, pipeline, reflection, guardrails, memory, scope, rule_engine, rag. Never import from enhancements/.
Layer 1 — enhancements/: self_improvement, diff_engine, edit_classifier, pattern_extractor, metrics, failure_detectors, reports. Imports from patterns/.
Layer 2 — brain/: trained data (events.jsonl, system.db, prospects/, sessions/). Event-sourced: all data = events, no domain tables.
Core loop: User Prompt -> AI Draft -> User Edits -> brain.correct(draft, final) -> Diff -> Classify -> Pattern Extract -> Graduate -> Apply Rules -> Metrics.
Source: sdk/src/gradata/ | Build: uv | Tests: pytest sdk/tests/ | Spec: sdk/ARCHITECTURE-SPEC.md

Environment: Windows 11. Python: C:/Users/olive/AppData/Local/Programs/Python/Python312/. Node available.
Brain vault: C:/Users/olive/SpritesWork/brain/ (NOT inside OneDrive working dir).
Prospecting: enrich before tiering, CEO != auto-T1, counts in filenames. Rules: domain/playbooks/prospecting-instructions.txt
Browser: E2E .claude/skills/e2e-testing/SKILL.md | Live: skills/playwright-skill/SKILL.md
Truth protocol: .carl/global GLOBAL_RULE_0 + .claude/truth-protocol.md
