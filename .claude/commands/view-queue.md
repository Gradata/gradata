---
description: View the learnings queue without processing
allowed-tools: Bash, Read
---

## Context
- Queue file: per-project at `~/.claude/projects/<encoded-cwd>/learnings-queue.json`

## Your Task

Display the current learnings queue in a readable format.

```bash
python .claude/hooks/reflect/scripts/read_queue.py 2>/dev/null || echo "[]"
```

**Output format:**
```
════════════════════════════════════════════════════════════
LEARNINGS QUEUE: [N] items
════════════════════════════════════════════════════════════

[0.85] "don't send emails without checking Pipedrive" (guardrail) - 2 hours ago
[0.70] "perfect, that follow-up was exactly right" (positive) - 1 day ago
[0.90] "remember: always check calendar 2 months out" (explicit) - just now

════════════════════════════════════════════════════════════
Commands:
  /reflect        - Process and route learnings
  /session-audit  - Full end-of-session routine
  /skip-reflect   - Discard all learnings
════════════════════════════════════════════════════════════
```

If queue is empty:
```
════════════════════════════════════════════════════════════
LEARNINGS QUEUE: Empty
════════════════════════════════════════════════════════════
No learnings queued. Corrections are auto-detected during sessions.
Use "remember: <learning>" to explicitly add items.
════════════════════════════════════════════════════════════
```

Parse each item's confidence, message (truncated to 60 chars), pattern name, and relative timestamp.
