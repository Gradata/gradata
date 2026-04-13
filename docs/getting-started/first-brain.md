# Your First Brain

This walks you through the full Gradata loop in Python: create a brain, log an output, record a correction, graduate a rule, and inject it back into the next prompt.

## 1. Create a brain

```python
from gradata import Brain

brain = Brain.init(
    "./my-brain",
    domain="Engineering",
    name="Code Review Brain",
    interactive=False,
)
```

`Brain.init()` creates the directory, initializes SQLite, runs migrations, and writes the initial `brain.manifest.json`. Re-opening an existing brain is identical but without `init()`:

```python
brain = Brain("./my-brain")
```

## 2. Log an AI output (optional)

Logging outputs gives the brain context to measure improvement. It is optional — corrections alone are enough learning signal.

```python
brain.log_output(
    "Hi John, I wanted to reach out about our AI platform.",
    output_type="email",
    self_score=7.0,
)
```

## 3. Record your first correction

The `correct()` call is the primary learning signal. Supply what the AI produced (`draft`) and what you ended up shipping (`final`):

```python
event = brain.correct(
    draft="We are pleased to inform you of our new product offering.",
    final="Hey, check out what we just shipped.",
)

print(event["severity"])          # e.g. "major"
print(event["classifications"])   # ["TONE", "STYLE"]
```

Under the hood, `correct()` computes edit distance, classifies the edit (tone / content / structure / factual / style), extracts a behavioral instruction, creates an INSTINCT-tier lesson, and emits a `CORRECTION` event.

## 4. Add a rule manually (optional)

You can also add a rule directly without waiting for a correction:

```python
# Manual rules start as INSTINCT and must earn their way up like any other lesson.
brain.correct(
    draft="Let's circle back on the deliverables.",
    final="What's blocking shipping?",
    category="TONE",
)
```

There is no separate `add_rule()` — every rule enters the system through a correction, real or synthetic. This keeps provenance intact: every rule has a traceable origin.

## 5. Graduate lessons

After a session's worth of corrections (3+ similar ones), run:

```python
result = brain.end_session()
print(result)
# {
#   "session": 1,
#   "total_lessons": 4,
#   "promotions": 1,     # lessons graduated to PATTERN or RULE
#   "demotions": 0,
#   "new_rules": 1,
#   ...
# }
```

`end_session()`:

1. Updates confidence for all lessons based on survival/contradiction.
2. Graduates lessons that cross the PATTERN (0.60) or RULE (0.80) thresholds.
3. Discovers meta-rules from 3+ related graduated rules.
4. Emits a `SESSION_END` event with metrics.

## 6. Apply rules to the next draft

Before generating AI output, pull the relevant rules:

```python
rules = brain.apply_brain_rules("write an email to a prospect")
print(rules)
```

Output (formatted for prompt injection):

```xml
<brain-rules>
  [RULE:0.92] TONE: Write casually and directly. Avoid formal business language.
  [PATTERN:0.68] STRUCTURE: Lead with the news, not the pleasantries.
</brain-rules>
```

Inject that string into your LLM system prompt.

## 7. Inspect the manifest

```python
m = brain.manifest()

print(m["metadata"]["sessions_trained"])   # 1
print(m["quality"]["correction_rate"])     # 0.75 (this session)
print(m["quality"]["rules_active"])        # 1
print(m.get("compound_score"))             # 0-100 quality score
```

The manifest regenerates from event data every session. It's the brain's resume: cryptographically grounded evidence of training without exposing raw corrections.

## 8. Search

```python
hits = brain.search("email tone", top_k=3)
for h in hits:
    print(f"[{h['confidence']:.2f}] {h['source']}: {h['text'][:80]}")
```

Keyword (FTS5) search is always available. Semantic search requires `pip install "gradata[embeddings]"` and one call to `brain.embed()`.

## 9. Close

```python
brain.close()
# or use a context manager:
with Brain("./my-brain") as brain:
    ...
```

---

## What you have now

After this tutorial your brain contains:

- One `CORRECTION` event
- One INSTINCT lesson
- A manifest with `sessions_trained=1`

Run the loop 10 more times with similar corrections and you will see your first RULE graduate. Run it 30 times across different corrections and you will see your first meta-rule.

Next:

- [Claude Code Setup](claude-code.md) — wire the brain into your editor
- [Concepts → Corrections](../concepts/corrections.md) — what counts as a correction
- [SDK → Brain](../sdk/brain.md) — the full API reference
