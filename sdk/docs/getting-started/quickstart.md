# Quick Start

Get a brain learning from your corrections in under 5 minutes.

## 1. Create a Brain

```python
from aios_brain import Brain

brain = Brain.init("./my-brain", domain="Sales", name="My Brain")
```

Or from the CLI:

```bash
aios-brain init ./my-brain --domain Sales
```

## 2. Log an AI Output

Every time the AI generates something, log it:

```python
brain.log_output(
    "Hi John, I wanted to reach out about our AI platform.",
    output_type="email",
    self_score=7.0,
    session=1,
)
```

## 3. Record a Correction

When the user edits the AI's output, that edit is the learning signal:

```python
event = brain.correct(
    draft="Hi John, I wanted to reach out about our AI platform.",
    final="John, saw your team is scaling paid ads. We cut creative testing time in half.",
    session=1,
)
```

The brain automatically analyzes what changed and why.

## 4. Get Rules for the Next Draft

```python
rules = brain.apply_brain_rules(
    "email_draft",
    {"audience": "marketing_manager"}
)
```

Early on, this returns nothing. As corrections accumulate and patterns prove themselves, the brain starts providing rules that shape future output.

## 5. Check Brain Health

```python
health = brain.health()
manifest = brain.manifest()
print(f"Sessions: {manifest['metadata']['sessions_trained']}")
```

## 6. Search the Brain

```python
results = brain.search("budget objections")
for r in results:
    print(f"[{r['confidence']}] {r['source']}: {r['text'][:80]}")
```

## What's Next

- [Core Concepts](concepts.md) -- how brains compound over sessions
- [Training Guide](../guides/training.md) -- full training workflow
- [MCP Integration](../guides/mcp.md) -- connect to Claude Code, Cursor, etc.
