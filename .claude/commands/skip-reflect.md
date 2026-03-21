---
description: Discard queued learnings without processing
allowed-tools: Bash, AskUserQuestion
---

## Your Task

1. Check queue:
```bash
python .claude/hooks/reflect/scripts/read_queue.py 2>/dev/null || echo "[]"
```

2. If empty: "Queue is already empty. Nothing to skip."

3. If has items:
   - Show count and preview each item (type + first 50 chars)
   - Ask: "Discard [N] learning(s)? [y/n]"

4. If confirmed:
```bash
python -c "
import sys, os
sys.path.insert(0, os.path.join('.claude', 'hooks', 'reflect', 'scripts'))
from lib.reflect_utils import save_queue
save_queue([])
"
```
   - Output: "Discarded [N] learnings. Queue cleared."

5. If declined: "Aborted. Run /reflect to process instead."
