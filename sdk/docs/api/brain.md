# Brain Class API

The `Brain` class is the primary interface to the SDK. All operations go through it.

## Constructor

### `Brain(brain_dir)`

Open an existing brain.

```python
from aios_brain import Brain

brain = Brain("./my-brain")
```

**Args:**

- `brain_dir` (str | Path): Path to the brain directory. Must exist.

**Raises:** `BrainNotFoundError` if the directory doesn't exist.

### `Brain.init(brain_dir, *, domain, name, company, embedding, interactive)`

Bootstrap a new brain with the onboarding wizard.

```python
brain = Brain.init(
    "./my-brain",
    domain="Sales",
    name="My Sales Brain",
    company="Acme Corp",
    embedding="local",     # or "gemini"
    interactive=False,     # skip terminal prompts
)
```

**Returns:** `Brain` instance pointing at the new directory.

---

## Core Learning Loop

### `brain.log_output(text, output_type, prompt, self_score, scope, session)`

Log an AI-generated draft for tracking.

```python
brain.log_output(
    "Hi John, wanted to reach out...",
    output_type="email",
    self_score=7.0,
    session=1,
)
```

**Args:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | str | required | The AI-generated draft |
| `output_type` | str | `"general"` | Type: email, research, code, etc. |
| `prompt` | str | None | The user prompt that triggered this |
| `self_score` | float | None | AI's confidence rating (0-10) |
| `scope` | dict | None | Scope context dict |
| `session` | int | None | Session number (auto-detected) |

**Returns:** Event dict.

### `brain.correct(draft, final, category, context, session)`

Record a user correction. This is the primary learning signal.

```python
event = brain.correct(
    draft="Hi John, wanted to reach out...",
    final="John, saw your team is scaling ads. We cut creative testing time in half.",
    session=1,
)
```

Automatically:

1. Computes edit distance and severity
2. Classifies edits (tone/content/structure/factual/style)
3. Extracts behavioral patterns
4. Emits a CORRECTION event

**Returns:** Event dict with `diff`, `classifications`, and `patterns_extracted`.

### `brain.apply_brain_rules(task, context)`

Get graduated rules for a task, formatted for prompt injection.

```python
rules = brain.apply_brain_rules(
    "email_draft",
    {"audience": "executive", "domain": "sales"},
)
# Returns formatted string ready to inject into LLM prompt
```

---

## Search

### `brain.search(query, mode, top_k, file_type)`

Search the brain using FTS5 keyword search.

```python
results = brain.search("budget objections", top_k=5)
```

**Returns:** List of dicts with `source`, `text`, `score`, `confidence`.

---

## Embedding

### `brain.embed(full=False)`

Embed brain files into SQLite for semantic search.

```python
brain.embed()           # Delta (only changed files)
brain.embed(full=True)  # Full re-embed
```

Requires `pip install aios-brain[embeddings]`.

**Returns:** Number of chunks embedded.

---

## Events

### `brain.emit(event_type, source, data, tags, session)`

Emit an event to the brain's event log.

```python
brain.emit("CUSTOM_EVENT", "my_module", {"key": "value"}, ["tag:custom"])
```

### `brain.query_events(event_type, session, last_n_sessions, limit)`

Query events from the log.

```python
corrections = brain.query_events(event_type="CORRECTION", last_n_sessions=5)
```

---

## Facts

### `brain.get_facts(prospect, fact_type)`

Query structured facts extracted from knowledge files.

### `brain.extract_facts()`

Extract structured facts from all prospect files. Returns count of facts extracted.

---

## Manifest & Health

### `brain.manifest()`

Generate `brain.manifest.json` and return it.

```python
m = brain.manifest()
print(m["metadata"]["sessions_trained"])
```

### `brain.health()`

Generate a health report.

### `brain.stats()`

Return brain statistics (file counts, DB size, embedding status).

### `brain.success_conditions(window=20)`

Evaluate the six success conditions from the Build Directive.

---

## Patterns API

### `brain.classify(message)`

Classify a user message into intent, audience, and pattern.

### `brain.guard(text, direction="input")`

Run guardrail checks. `direction` is `"input"` or `"output"`.

### `brain.reflect(draft, checklist, evaluator, refiner, max_cycles=3)`

Run a generate-critique-refine loop.

### `brain.assess_risk(action, context=None)`

Classify risk level of an action.

### `brain.pipeline(*stages)`

Create a Pipeline with Stage instances.

### `brain.track_rule(rule_id, accepted, misfired, contradicted, session)`

Log a rule application event.

### `brain.register_task_type(name, keywords, domain_hint, prepend=False)`

Register a custom task type in the scope classifier.

---

## CARL Contracts

### `brain.register_contract(contract)`

Register a behavioral contract.

### `brain.get_constraints(task)`

Get applicable constraints for a task.

---

## Export

### `brain.export(output_path=None, mode="full")`

Export brain as a shareable archive.

**Modes:** `"full"` (everything), `"no-prospects"` (exclude prospect data), `"domain-only"` (patterns and rules only).

---

## Context

### `brain.context_for(message)`

Compile relevant brain context for a user message. Returns a formatted string suitable for prompt injection.
