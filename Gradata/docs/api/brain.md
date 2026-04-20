# Brain Class API

The `Brain` class is the primary interface to the SDK. All operations go through it.

## Constructor

### `Brain(brain_dir, working_dir=None, encryption_key=None)`

Open an existing brain.

```python
from gradata import Brain

brain = Brain("./my-brain")
```

**Args:**

- `brain_dir` (str | Path): Path to the brain directory. Must exist.
- `working_dir` (str | Path | None): Optional working directory for context.
- `encryption_key` (str | None): Encryption key for at-rest encryption. Also reads `GRADATA_ENCRYPTION_KEY` env var.

**Raises:** `BrainNotFoundError` if the directory doesn't exist.

### `Brain.init(brain_dir, *, domain, name, company, embedding, interactive)`

Bootstrap a new brain with the onboarding wizard.

```python
brain = Brain.init(
    "./my-brain",
    domain="Engineering",
    name="CodeReview Brain",
    interactive=False,
)
```

**Returns:** `Brain` instance pointing at the new directory.

---

## Properties

### `brain.session` → int

Current session number, auto-tracked from the event log. Falls back to `loop-state.md` if no events exist yet.

```python
print(f"Session {brain.session}")  # → "Session 42"
```

---

## Core Learning Loop

### `brain.correct(draft, final, category, context, session, agent_type, approval_required, dry_run, min_severity)`

Record a user correction. This is the primary learning signal.

```python
event = brain.correct(
    draft="We are pleased to inform you of our new product offering.",
    final="Hey, check out what we just shipped.",
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
rules = brain.apply_brain_rules("write an email")
# Returns formatted string ready to inject into LLM prompt
```

### `brain.end_session(session_corrections=None, session_type="full", machine_mode=None, skip_meta_rules=False)`

Run the full graduation sweep at end of session.

```python
result = brain.end_session()
print(result)
# → {"session": 42, "total_lessons": 15, "promotions": 2, "demotions": 0, ...}
```

Automatically:

1. Updates confidence for all lessons based on session corrections
2. Graduates lessons (INSTINCT → PATTERN → RULE)
3. Archives newly graduated RULE lessons
4. Discovers meta-rules from 3+ related graduated rules
5. Emits `SESSION_END` event with session metrics

**Returns:** Dict with session number, lesson counts, promotions, demotions, new rules.

### `brain.auto_evolve(output, task, agent_type, evaluator, dimensions, threshold)`

Evaluate output and auto-generate corrections for dimensions that score below threshold.

### `brain.detect_implicit_feedback(user_message, session)`

Detect implicit behavioral feedback in user prompts (e.g., "don't do that again").

---

## Human-in-the-Loop Approval

### `brain.review_pending()` → list

List lessons awaiting human approval.

### `brain.approve_lesson(approval_id)` → dict

Approve a pending lesson for graduation. `approval_id` is the integer ID from `review_pending()`.

### `brain.reject_lesson(approval_id, reason="")` → dict

Reject a pending lesson (prevents graduation). `approval_id` is the integer ID from `review_pending()`.

---

## Search

### `brain.search(query, mode, top_k, file_type)`

Search the brain using FTS5 keyword search.

```python
results = brain.search("code review patterns", top_k=5)
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

Requires `pip install gradata[embeddings]`.

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

**Event types emitted by the SDK:**
- `CORRECTION` — from `correct()`
- `SESSION_END` — from `end_session()`
- `GRADUATION` — when a lesson is promoted
- `RULE_APPLICATION` — from `track_rule()`

---

## Facts & Observation

### `brain.get_facts(prospect=None, fact_type=None)`

Query structured facts from the brain.

### `brain.observe(messages, user_id="default")`

Extract facts from a conversation without requiring corrections.

```python
facts = brain.observe([
    {"role": "user", "content": "I prefer short emails"},
    {"role": "assistant", "content": "Got it, keeping it brief."},
])
```

---

## Lesson Management

### `brain.forget(description=None, category=None)` → int

Delete specific lessons. Supports GDPR right-to-erasure.

### `brain.rollback(lesson_id=None, description=None, category=None)` → dict

Disable lessons with audit trail (soft delete). Returns `{rolled_back: True, lesson_index, category, description, previous_state, previous_confidence}` or `{rolled_back: False, error: ...}`.

### `brain.lineage(category=None, limit=50)` → list

Full correction-to-rule provenance chain.

---

## Manifest & Health

### `brain.manifest()`

Generate `brain.manifest.json` — mathematical proof the brain is improving.

```python
m = brain.manifest()
print(m["compound_score"])   # 0-100 quality score
print(m["metadata"]["sessions_trained"])
```

### `brain.health()`

Generate a health report with diagnostics.

### `brain.stats()`

Return brain statistics (file counts, DB size, embedding status).

---

## Patterns API

### `brain.guard(text, direction="input")`

Run guardrail checks. `direction` is `"input"` or `"output"`.

### `brain.reflect(draft, checklist, evaluator, refiner, max_cycles=3)`

Run a generate-critique-refine loop.

### `brain.pipeline(*stages)`

Create a Pipeline with Stage instances.

### `brain.track_rule(rule_id, accepted, misfired, contradicted, session)`

Log a rule application event.

### `brain.register_task_type(name, keywords, domain_hint, prepend=False)`

Register a custom task type in the scope classifier.

---

## Export

### `brain.export(output_path=None, mode="full")`

Export brain as a shareable archive.

**Modes:** `"full"` (everything), `"no-prospects"` (exclude personal data), `"domain-only"` (patterns and rules only).

### `brain.backfill_from_git(repo_path=".", lookback_days=90)`

Bootstrap a brain from git commit history.

---

## Context

### `brain.context_for(message)`

Compile relevant brain context for a user message. Returns a formatted string suitable for prompt injection.
