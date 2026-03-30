# CLAUDE.md Archive
# Sections moved here to keep CLAUDE.md under 150 lines. Still accessible on demand.

## What Sprites Is (moved 2026-03-18)
AI performance marketing platform. Connects to Meta, Google, and LinkedIn ad accounts.
Launches campaigns, shifts budget, creates content, publishes SEO blogs.
Fully automated with human approval before anything goes live.
Pricing: $60/mo Starter | $500-1000/mo Standard | Enterprise custom
Oliver's meeting link: https://calendly.com/oliver-spritesai/30min

## CARL Integration Details (moved 2026-03-18)
CARL is installed at .carl/ in this workspace. At session start:
1. Read .carl/manifest and .carl/global
2. Load any ALWAYS_ON=true domains automatically
3. For other active domains, check recall keywords against the current task and load matching domain files
4. Respect exclusion rules before matching
5. If DEVMODE=true in manifest, include debug output about which domains loaded

## Self-Improvement Meta-Rules (moved 2026-03-18)
- ALWAYS use absolute directives (NEVER, ALWAYS) not suggestions
- Lead with WHY — explain the problem before the solution
- Keep rules under 20 words. If longer, it belongs in a skill file.
- Never duplicate. Search existing rules before adding.
- Delete rules that are no longer relevant. Prune > grow.
- Bullets over paragraphs. Action before theory.
- Don't add examples for obvious rules. Don't explain what a bullet can say.
- When adding rules, ALWAYS update the Rules Index at top.
- Max 150 lines for this file. If over, compress or move to .claude/ reference files.

## Auto-Archive Rules (moved 2026-03-18)
If CLAUDE.md exceeds 150 lines during a session:
1. Move completed campaign details, old tool notes, and resolved rules to .claude/CLAUDE-archive.md
2. Keep: Rules Index, Oliver's Role, Read First, Work Style Rules, Prospect Research Order, Tool Stack, ICP, Writing Rules, Email Frameworks, Demo Prep Rules, Self-Improvement, Accuracy Rules
3. Archive: anything specific to a past campaign, resolved one-time issues, or deprecated rules
4. Never delete — always archive

## Folder Structure (moved 2026-03-18)
CLAUDE.md (this file) | .claude/ (skills, leads, sweep rules, lessons.md) | docs/sprites_context.md (product context) | skills/ | leads/enriched/, leads/wip/ | sequences/ | prospects/ | research/ | Demo Material/ | outputs/

## Tool Call Failure Protocol (moved 2026-03-18)
1. Try an alternative approach immediately (different tool, different method)
2. If no alternative, explain what failed and what you tried
3. NEVER silently skip a required step. Log the failure and attempt recovery.
