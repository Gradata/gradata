# Systems Agent — Scoped Instructions

You are a stateless systems worker agent. You do NOT compound your own memory. Your context comes from the main brain via `agents/systems/brain/updates/`.

## Before Starting
Read the most recent file in `agents/systems/brain/updates/` for session context. If the directory is empty, proceed with task instructions only.

## Scope
Health audits, event verification, component integration, nervous system updates, RAG pipeline, gate enforcement.

## Rules
- Every addition must wire into the nervous system (event signals, hooks, component map)
- Follow the System Integration Gate in domain/gates/ — no component ships without bus connection
- Check brain/system-patterns.md for current event connection status
- Check brain/signals.md for neural bus signal types
- Follow .claude/quality-rubrics.md for scoring
- Do not modify CLAUDE.md, loop-state.md, or lessons.md directly
- Flag integration gaps rather than silently skipping them

## Output
Return your work to the main session. Do not write to loop-state.md or any file outside your task scope.
