# Brain Class

The `Brain` class is the primary interface to the SDK. All correction, graduation, search, and export operations go through it.

```python
from gradata import Brain
```

## Constructor

### `Brain(brain_dir, working_dir=None, encryption_key=None)`

Open an existing brain.

```python
brain = Brain("./my-brain")
```

**Args:**

- `brain_dir` (str | Path) — Path to the brain directory. Must exist.
- `working_dir` (str | Path | None) — Optional working directory for context.
- `encryption_key` (str | None) — At-rest encryption key. Also reads `GRADATA_ENCRYPTION_KEY`.

**Raises:** `BrainNotFoundError` if the directory doesn't exist.

### `Brain.init(brain_dir, *, domain=None, name=None, company=None, embedding=None, interactive=True)`

Bootstrap a new brain. Creates the directory, initializes SQLite, runs migrations, writes the initial manifest.

```python
brain = Brain.init(
    "./my-brain",
    domain="Engineering",
    name="Code Review Brain",
    interactive=False,
)
```

Returns a `Brain` instance pointing at the new directory.

---

## Properties

### `brain.session` → int

Current session number, auto-tracked from the event log.

```python
print(f"Session {brain.session}")
```

### `brain.dir` → Path

Absolute path to the brain directory.

### `brain.db_path` → Path

Absolute path to `system.db`.

---

## Core learning loop

### `brain.correct(draft, final, category=None, context=None, session=None, agent_type=None, approval_required=False, dry_run=False, min_severity=None)`

Record a correction. This is the primary learning signal.

```python
event = brain.correct(
    draft="We are pleased to inform you of our new product offering.",
    final="Hey, check out what we just shipped.",
)
print(event["severity"], event["classifications"])
```

Runs the full pipeline: edit distance → severity → classification → behavioral extraction → INSTINCT lesson → `CORRECTION` event.

Returns a dict with `diff`, `severity`, `classifications`, and `patterns_extracted`.

### `brain.apply_brain_rules(task, context=None)`

Get graduated rules for a task, formatted for prompt injection.

```python
rules = brain.apply_brain_rules("write an email to a prospect")
# Returns a formatted <brain-rules> string ready for LLM context.
```

### `brain.end_session(session_corrections=None, session_type="full", machine_mode=None, skip_meta_rules=False)`

Run the graduation sweep at end of session.

```python
result = brain.end_session()
# {"session": 42, "total_lessons": 15, "promotions": 2, "new_rules": 1, ...}
```

Updates confidence, graduates lessons, discovers meta-rules, emits `SESSION_END`.

### `brain.auto_evolve(output, task, agent_type=None, evaluator=None, dimensions=None, threshold=8.0)`

Evaluate output along multiple dimensions and auto-generate corrections for anything scoring below `threshold`.

### `brain.detect_implicit_feedback(user_message, session=None)`

Scan a user message for implicit pushback (e.g., "stop doing that"). Returns a dict describing any detected correction.

---

## Human-in-the-loop approval

### `brain.review_pending()` → list

List lessons awaiting human approval.

### `brain.approve_lesson(approval_id)` → dict

Approve a pending lesson for graduation.

### `brain.reject_lesson(approval_id, reason="")` → dict

Reject a pending lesson.

---

## Search

### `brain.search(query, mode="auto", top_k=5, file_type=None)`

Search the brain using FTS5 keyword search (and semantic search if embeddings are available).

```python
hits = brain.search("code review patterns", top_k=5)
for h in hits:
    print(f"[{h['confidence']:.2f}] {h['source']}: {h['text'][:80]}")
```

Returns a list of dicts with `source`, `text`, `score`, `confidence`.

---

## Embeddings

### `brain.embed(full=False)`

Embed brain files into SQLite for semantic search.

```python
brain.embed()           # Delta — only changed files.
brain.embed(full=True)  # Full re-embed.
```

Requires `pip install "gradata[embeddings]"`.

---

## Events

### `brain.emit(event_type, source, data, tags=None, session=None)`

Emit an event to the brain's append-only event log.

```python
brain.emit("CUSTOM_EVENT", "my_module", {"key": "value"}, ["tag:custom"])
```

### `brain.query_events(event_type=None, session=None, last_n_sessions=None, limit=None)`

Query events.

```python
corrections = brain.query_events(event_type="CORRECTION", last_n_sessions=5)
```

Built-in event types:

- `CORRECTION` — from `correct()`
- `SESSION_END` — from `end_session()`
- `GRADUATION` — when a lesson is promoted
- `RULE_APPLICATION` — from `track_rule()`

---

## Facts and observation

### `brain.get_facts(prospect=None, fact_type=None)`

Query structured facts from the brain.

### `brain.observe(messages, user_id="default")`

Extract facts from a conversation without requiring a correction.

```python
facts = brain.observe([
    {"role": "user", "content": "I prefer short emails"},
    {"role": "assistant", "content": "Got it, keeping it brief."},
])
```

---

## Lesson management

### `brain.forget(what="last")`

Delete specific lessons. Supports GDPR right-to-erasure.

### `brain.rollback(lesson_id=None, description=None, category=None)`

Disable a lesson with audit trail (soft delete). Returns the previous state and confidence for later restoration.

### `brain.patch_rule(rule_id, new_description)`

Edit a graduated rule's description in-place. Logged as a `RULE_PATCH` event.

### `brain.lineage(category=None, limit=50)` → list

Full correction-to-rule provenance chain.

---

## Manifest and health

### `brain.manifest()` → dict

Generate (or refresh) `brain.manifest.json` — mathematical proof the brain is improving.

```python
m = brain.manifest()
print(m["metadata"]["sessions_trained"])
print(m["quality"]["correction_rate"])
print(m.get("compound_score"))      # 0-100
```

### `brain.health()` → dict

Generate a health report with diagnostics.

### `brain.stats()` → dict

Brain statistics: file counts, DB size, embedding status.

### `brain.prove()` → dict

Return the compact "prove" object for public display (no raw corrections).

### `brain.convergence()` → dict

Corrections-per-session trend analysis.

### `brain.efficiency(*, estimate_time=False)` → dict

Ops efficiency metrics: rule hit rate, misfire rate, time saved.

---

## Patterns API

### `brain.guard(text, direction="input")`

Run guardrail checks. `direction` is `"input"` or `"output"`.

### `brain.reflect(draft, checklist, evaluator, refiner, max_cycles=3)`

Run a generate-critique-refine loop.

### `brain.pipeline(*stages)`

Create a Pipeline with Stage instances.

### `brain.plan(task, context=None)` → dict

Compile a plan for a task, applying relevant rules and meta-rules.

### `brain.track_rule(rule_id, accepted=False, misfired=False, contradicted=False, session=None)`

Log a rule application event.

### `brain.register_task_type(name, keywords, domain_hint=None, prepend=False)`

Register a custom task type in the scope classifier.

---

## Export and share

### `brain.export(output_path=None, mode="full")` → Path

Export brain as a shareable archive.

**Modes:**

- `"full"` — everything
- `"no-prospects"` — exclude personal data
- `"domain-only"` — patterns and rules only

### `brain.share()` → dict

Package the brain's graduated rules for sharing (no events, no raw data).

### `brain.absorb(package)` → dict

Install a brain package from another user, applying their graduated rules to this brain.

### `brain.export_rules(min_state="PATTERN", skill_name="")` → str

Export rules as markdown for cross-platform agent hosts (see [Rule-to-Hook](rule-to-hook.md)).

### `brain.backfill_from_git(repo_path=".", lookback_days=90)`

Bootstrap a brain from git commit history.

---

## Context

### `brain.context_for(message)` → str

Compile relevant brain context for a user message. Returns a formatted string suitable for prompt injection.

### `brain.log_output(text, output_type=None, self_score=None, session=None)`

Log an AI-generated output before a correction happens. Enables measurement of improvement over time.

---

## Scope classification

### `brain.scope(task=None, audience=None, **kwargs)` → dict

Classify a task into `(task_type, audience_tier, domain, stakes)`.

---

## Budget

### `brain.check_budget(api_name, count=1)` → dict

Check if an API call is within the daily budget.

### `brain.spend_budget(api_name, count=1)` → dict

Record an API call against the daily budget.

### `brain.budget_summary()` → list

Daily budget status for all tracked APIs.

---

## Context manager

```python
with Brain("./my-brain") as brain:
    brain.correct(draft=..., final=...)
    brain.end_session()
# auto-closes on exit
```

### `brain.close()`

Release DB handles. Idempotent.

---

## Errors

```python
from gradata import BrainError, BrainNotFoundError, ValidationError, ExportError

try:
    brain = Brain("/nope")
except BrainNotFoundError:
    ...
```

| Exception | Raised when |
|-----------|-------------|
| `BrainError` | Base class |
| `BrainNotFoundError` | Brain directory missing |
| `ValidationError` | Argument validation failed |
| `ExportError` | Export pipeline failed |
| `EmbeddingError` | Embedding provider failed |
| `EventPersistenceError` | Event log write failed |
| `TaxonomyError` | Tag taxonomy violation |

See [Middleware](middleware.md) for wrapping LLM APIs, and [Rule-to-Hook](rule-to-hook.md) for cross-platform export.
