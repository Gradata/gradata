# Sales Pack — Sprites.ai

Profession pack for the Sprites.ai sales agent. Contains the sales-specific configuration that powers learning routing, outcome tracking, and correction detection.

## Files

| File | Job | Read By | Written By |
|------|-----|---------|------------|
| routing-rules.md | Classifies learnings into 3 routes: CLAUDE.md rules, lessons.md mistakes, manual review insights | `/reflect` (step 4: classify) | Manual — update when new categories or sections are added |
| outcome-schema.md | Defines tactic→result types, field formats, storage destinations, and pattern detection rules | `/log-outcome` (step 2-3: format + route) | Manual — update when new outcome types emerge |
| patterns.md | Regex patterns for real-time correction detection during sessions | capture_learning.py hook (UserPromptSubmit) | Manual — update when new correction signals are identified |

## How It Works

1. **During session:** `capture_learning.py` uses patterns from `patterns.md` to detect corrections in Oliver's messages and queue them
2. **At wrap-up (step 7):** `/reflect` uses `routing-rules.md` to classify each queued item into the right destination
3. **At wrap-up (step 4):** `/log-outcome` uses `outcome-schema.md` to format and route tactic→result pairs
4. **Pattern detection:** After logging outcomes, the schema's pattern detection rules flag emerging patterns (3+ similar results)

## Adapting for Another Role

1. Copy `packs/_template/` to `packs/[profession]/`
2. Fill in `routing-rules.md` with your profession's CLAUDE.md sections, lesson categories, and insight signals
3. Fill in `outcome-schema.md` with your profession's tactic types, result outcomes, and storage locations
4. Fill in `patterns.md` with any profession-specific correction signals (the universal patterns work for everyone)
