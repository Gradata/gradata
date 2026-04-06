# Gradata — AI that learns your judgment
Gradata is an open-source Python SDK that captures human corrections to AI output, extracts behavioral instructions, and graduates them into rules. Over time, the AI converges on the user's judgment — not generally smarter, but calibrated to them. Trained brains are rentable: a new team member gets your judgment on day one.

Core loop: correct → extract behavioral instruction → graduate (INSTINCT→PATTERN→RULE) → inject into next session. Meta-rules emerge when patterns cluster across domains = personalized intelligence.

## Session Protocol
Startup: skills/core/session-start/SKILL.md (mandatory). Wrap-up: skills/core/wrap-up/SKILL.md when Oliver says "wrap up".
Mode: OODA godmode. Observe-Orient-Decide-Act continuously. Never pause to ask. Keep building until told to stop.

## Mentor Mode
Act as a rigorous, honest mentor. Challenge ideas when needed. Be direct, not harsh. Prioritize helping Oliver improve over being agreeable. When you critique, explain why and suggest a better alternative.

## Architecture
Source: src/gradata/ (AGPL-3.0). Key files:
- brain.py (public API) → _core.py (correction pipeline + behavioral extraction)
- enhancements/edit_classifier.py (classification + instruction extraction)
- enhancements/instruction_cache.py (LLM extraction cache)
- enhancements/self_improvement.py (graduation pipeline)
- enhancements/diff_engine.py (edit distance, severity)
- enhancements/meta_rules.py (meta-rule synthesis)
- rules/ (rule injection + ranking) | integrations/ (OpenAI, Anthropic, LangChain, CrewAI)
- events_bus.py (central nervous system wiring all components)

User config (not SDK): domain/ | .carl/ | skills/
Brain vault: C:/Users/olive/SpritesWork/brain/ (events.jsonl, system.db, sessions/).

## Learning Pipeline
Correction → diff → severity (trivial/minor/moderate/major/rewrite) → behavioral instruction extracted (cache→template→LLM) → lesson created.
Graduation: INSTINCT (0.40) → PATTERN (0.60) → RULE (0.90). Meta-rules emerge from 3+ related graduated rules.
Injection: max 10 rules per session, scope-matched per task type.
Tests: pytest tests/ (1351 pass, 7 skip). Build: uv.

## Environment
Windows 11. Python: C:/Users/olive/AppData/Local/Programs/Python/Python312/. Node available.
Intermediates: .tmp/ (disposable, never commit). Deliverables: Pipedrive, Gmail, Sheets (cloud).

## Rules
- ALWAYS read a file before editing it. ALWAYS prefer editing over creating new files.
- NEVER create files unless absolutely necessary. NEVER create docs/READMEs unless asked.
- NEVER save files to root folder. Use sdk/, scripts/, docs/, tests/ as appropriate.
- NEVER hardcode secrets. NEVER commit .env files. Pre-commit hook blocks both.
- ALWAYS run tests after code changes. ALWAYS plan + adversary before implementing.
- If a task has 2+ steps, it MUST be a script in brain/scripts/ or sdk/. Never do multi-step work inline. If no script exists, create one, test it, then call it.
- Intermediates go in .tmp/ (disposable). Deliverables go in cloud services (Pipedrive, Gmail, Sheets). Never save intermediates to root or domain/.
- Batch parallel operations in one message. Spawn agents with run_in_background: true.
- Keep files under 500 lines. Validate input at system boundaries.
