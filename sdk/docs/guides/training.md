# Training a Brain

This guide walks through the full training workflow, from first session to graduated rules.

## Session Structure

A session is a bounded unit of work. The brain tracks session numbers to measure correction density and pattern survival.

```python
from aios_brain import Brain

brain = Brain("./my-brain")
session = 1  # Increment each session
```

## The Training Loop

### Step 1: Log AI Output

Every time the AI generates something, log it:

```python
brain.log_output(
    text="Draft email content...",
    output_type="email",
    self_score=7.5,
    session=session,
)
```

### Step 2: Capture Corrections

When the user edits the AI's output, record the correction:

```python
event = brain.correct(
    draft="The original AI draft...",
    final="The user's edited version...",
    session=session,
)
```

The SDK automatically computes:

- **Edit distance**: How different the final is from the draft (0.0 to 1.0)
- **Severity**: as-is, minor, moderate, major, or discarded
- **Classifications**: Which categories were edited (tone, content, structure, factual, style)
- **Patterns**: Behavioral preferences extracted from the edits

### Step 3: Apply Rules

Before generating the next output, ask the brain for applicable rules:

```python
rules = brain.apply_brain_rules(
    task="email_draft",
    context={"audience": "executive", "domain": "sales"},
)

# Inject rules into the LLM prompt
prompt = f"""
{rules}

Draft an email to the VP of Marketing about...
"""
```

### Step 4: Check Health

Periodically check brain health:

```python
health = brain.health()
manifest = brain.manifest()
```

## Timeline

| Sessions | What Happens |
|----------|-------------|
| 1-5 | Collecting initial corrections. No rules yet. |
| 6-15 | First patterns start emerging from repeated corrections. |
| 16-30 | Patterns that survive across sessions gain confidence. Contradictions get demoted. |
| 31-50 | Proven patterns become active rules. Correction rate declines. |
| 50+ | Brain is self-correcting. New corrections are rare and targeted. |

## Quality Metrics

Track these over time:

- **Correction rate**: Should decline as rules take effect
- **Severity distribution**: Should shift from major/moderate toward minor/as-is
- **Lessons active**: Count of lessons in each tier
- **Lessons graduated**: Total lessons that reached RULE status

```python
from aios_brain.enhancements.metrics import compute_metrics

metrics = compute_metrics(brain.db_path, window=20)
```

## Multi-Domain Training

A single brain can handle multiple domains. Scopes ensure rules only fire in the right context:

```python
# Sales corrections won't affect engineering outputs
brain.correct(draft, final, context={"domain": "sales", "task": "email_draft"})
brain.correct(draft, final, context={"domain": "engineering", "task": "code_review"})
```

## Embedding Updates

After adding new knowledge files, update embeddings:

```python
brain.embed()  # Delta: only changed files
```

Run this at the start of each session or after batch knowledge updates.
