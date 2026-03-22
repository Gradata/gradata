# Agent: systems

## Identity
- id: systems
- name: Systems Agent
- status: active
- version: 2026-03-21
- department: systems
- description: Spawned for health audits, event verification, component integration, nervous system updates, RAG pipeline
- instruction_file: agents/systems/CLAUDE.md

## Permissions
- tools_allowed: [Read, Write, Edit, Grep, Glob, Bash]
- tools_denied: [Apollo, Gmail, Fireflies, Pipedrive, Instantly, Google Calendar, WebFetch, WebSearch]
- write_paths: [.claude/*, .carl/*, agents/*, brain/system-patterns.md, brain/sessions/*, brain/metrics/*, brain/scripts/*]

## Context
- bootstrap_files: [.claude/component-map.md, .claude/self-improvement.md]
- bootstrap_limit: 12000 chars/file, 30000 total
- warmup: [brain/system-patterns.md, brain/events.jsonl]
- scope_tags: [SYSTEM, ARCHITECTURE, INTEGRATION, SAFETY, AUDIT, QUALITY, NERVOUS-SYSTEM]
- scope_paths: [system-patterns.md, signals.md, metrics/*, events.jsonl]

## Trust
- trust_level: config+instructions+code
- correction_rate: 0.04 (backfilled from S1-S21 session notes, 10 corrections across 16 active sessions)
- consecutive_rejections: 0
- auto_pause_threshold: 3

**Trust context:** Rate of 0.04 is well below 0.10 promotion threshold. Eligible for promotion to config+instructions+code pending Oliver's approval. Last 5 sessions: 2 minor corrections (S18: direction hybrid, S20: clause ambiguity). 11/16 sessions completely clean.

## Changelog
- 2026-03-21: Created with Genus-inspired manifest schema.
- 2026-03-21: Backfilled correction data from S1-S21. Eligible for trust promotion (rate 0.04 < 0.10).
- 2026-03-21: Promoted to config+instructions+code. Oliver approved. Rate 0.04 over 16 sessions, 11 clean.
