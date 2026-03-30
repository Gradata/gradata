# Gradata SDK Launch Strategy

**Version:** 1.0
**Date:** 2026-03-27
**Owner:** Oliver
**Status:** Draft

---

## 1. Developer Experience (DX) Spec

### 1.1 Installation

```bash
pip install gradata        # Zero deps. Python 3.11+.
uv add gradata             # Or with uv.
```

No binary dependencies. No Rust compilation. No Docker. The package is pure Python + stdlib. Sentence-transformers is optional and only needed if the developer wants local embeddings.

### 1.2 First 5 Minutes

The developer's first interaction follows this exact sequence:

```python
from gradata import Brain

# Step 1: Create a brain (one command, one directory)
brain = Brain.init("./my-brain", domain="Engineering")
# Creates: ./my-brain/system.db, brain.manifest.json
# Prints: "Brain initialized at ./my-brain (domain: Engineering)"

# Step 2: Log an AI output
brain.log_output(
    "Here is the REST API design...",
    output_type="design_doc",
    self_score=7
)
# Returns: event dict with timestamp, session number

# Step 3: Record a correction (the core learning signal)
brain.correct(
    draft="Here is the REST API design with SQL queries inline...",
    final="Here is the REST API design with a repository layer..."
)
# Returns: {
#   "severity": "moderate",
#   "edit_distance": 0.34,
#   "classifications": [{"category": "structure", "severity": "moderate"}],
#   "patterns_extracted": 1
# }

# Step 4: See what the brain learned
rules = brain.apply_brain_rules("write API design")
print(rules)
# "<brain-rules>
#   <rule state="INSTINCT" confidence="0.30">
#     Use repository pattern instead of inline SQL in API designs
#   </rule>
# </brain-rules>"
```

What happens under the hood at each step:

| Step | Visible to developer | Internal |
|------|---------------------|----------|
| `Brain.init()` | Directory created, one-line confirmation | SQLite schema migrated, manifest skeleton written |
| `log_output()` | Event dict returned | OUTPUT event stored in system.db, session auto-detected |
| `correct()` | Severity + classifications returned | Diff engine computes edit distance + compression distance, edit classifier categorizes into tone/content/structure/factual/style, CORRECTION event stored, pattern extractor runs |
| `apply_brain_rules()` | XML rules string for prompt injection | Scope built from task context, lessons filtered by relevance, formatted as XML for LLM consumption |

### 1.3 After 10 Corrections

The developer has been using the brain for a few hours across 2-3 sessions. They have corrected 10 outputs.

```python
# What they see:
manifest = brain.manifest()
print(manifest["learning"]["lessons_total"])        # 10
print(manifest["learning"]["lessons_by_state"])     # {"INSTINCT": 10}
print(manifest["learning"]["correction_rate"])      # ~0.5 per output
print(manifest["quality"]["adaptation_score"])      # 0.15

# The brain has learned patterns but nothing has graduated yet.
# All 10 lessons are INSTINCT (confidence 0.30).
# The brain injects them into prompts but they are low-confidence.

rules = brain.apply_brain_rules("write email to CTO")
# Returns 3-4 relevant INSTINCT rules scoped to the task.
# The developer sees their corrections reflected, but tentatively.
```

Dashboard view at 10 corrections (what gradata.ai shows):

```
Adaptation Score: 0.15 / 1.00
Lessons:  10 total | 10 INSTINCT | 0 PATTERN | 0 RULE
Categories: DRAFTING (4) | ACCURACY (3) | PROCESS (2) | TONE (1)
Correction trend: establishing baseline (need 20+ outputs)
```

### 1.4 After 50 Corrections (Graduation)

The developer has used the brain for 20+ sessions over several days. Lessons have been applied, tested, and reinforced.

```python
manifest = brain.manifest()
print(manifest["learning"]["lessons_by_state"])
# {"INSTINCT": 12, "PATTERN": 8, "RULE": 5, "KILLED": 3, "UNTESTABLE": 2}

print(manifest["quality"]["adaptation_score"])      # 0.62
print(manifest["learning"]["correction_rate"])      # 0.08 per output

# 5 lessons have graduated to RULE (confidence >= 0.90).
# These survived 5+ applications without contradiction.
# 3 lessons were killed (contradicted or untestable).

rules = brain.apply_brain_rules("write API docs")
# Returns RULE-state lessons first (high confidence),
# then PATTERN-state (medium confidence).
# INSTINCT-state lessons are deprioritized.
# KILLED/UNTESTABLE lessons are excluded.

# The developer can inspect what graduated:
for lesson in brain.rules:
    print(f"[{lesson.state.value}] {lesson.confidence:.2f} - {lesson.description[:80]}")
# [RULE] 0.94 - Always use repository pattern in API designs, never inline SQL
# [RULE] 0.92 - Include error response schemas in API documentation
# [RULE] 0.91 - Use active voice in technical writing, avoid passive constructions
# [PATTERN] 0.72 - Add rate limiting section to every API endpoint doc
# [PATTERN] 0.65 - Include curl examples alongside code samples
```

Dashboard view at 50 corrections:

```
Adaptation Score: 0.62 / 1.00
Lessons:  30 active | 12 INSTINCT | 8 PATTERN | 5 RULE | 3 KILLED | 2 UNTESTABLE
Categories: 3 of 5 categories showing declining correction rates
Correction trend: 0.5/output (S1) -> 0.08/output (S20) = 84% reduction

GRADUATED RULES:
  1. Repository pattern in API designs        conf: 0.94  fires: 8  misfires: 0
  2. Error response schemas in docs           conf: 0.92  fires: 6  misfires: 0
  3. Active voice in technical writing         conf: 0.91  fires: 7  misfires: 1
  4. Rate limiting in endpoint docs            conf: 0.72  fires: 4  misfires: 0  (PATTERN)
  5. Curl examples with code samples           conf: 0.65  fires: 3  misfires: 0  (PATTERN)

KILLED:
  - "Use British spelling" (contradicted at session 12, confidence dropped to 0.0)
  - "Always include changelog" (untestable for 20+ sessions, auto-killed)
```

### 1.5 Dashboard Integration (gradata.ai)

```python
# Connect to cloud for server-side graduation + dashboard
brain.connect_cloud()  # Reads GRADATA_API_KEY from env

# Now correct() and apply_brain_rules() route to the cloud API.
# Local mode continues to work as fallback if cloud is unreachable.

# The dashboard at gradata.ai shows:
# - Real-time adaptation score
# - Correction trend over sessions
# - Category extinction tracking (which error types stopped recurring)
# - Graduation pipeline visualization
# - Brain health report
# - Export/share controls
```

Connection flow:

```
Developer                    gradata.ai
    |                            |
    |-- pip install gradata ---->|
    |                            |
    |-- brain.connect_cloud() -->|
    |   (GRADATA_API_KEY env)    |
    |<-- 200 OK, sync started --|
    |                            |
    |-- brain.correct(d, f) --->|  (cloud runs full graduation pipeline)
    |<-- event + graduation ----|
    |                            |
    |-- GET /dashboard -------->|  (browser: gradata.ai/brain/my-brain)
    |<-- adaptation score, -----.
    |   correction trends,      |
    |   graduated rules         |
```

### 1.6 MCP Server Setup (Claude Code / Cursor)

```json
{
  "mcpServers": {
    "gradata": {
      "command": "python",
      "args": ["-m", "gradata.mcp_server", "--brain-dir", "./my-brain"]
    }
  }
}
```

This exposes five tools to the LLM host:

| Tool | Purpose |
|------|---------|
| `brain_search(query)` | Search brain knowledge |
| `brain_correct(draft, final)` | Log a correction |
| `brain_log_output(text, type, score)` | Log AI output |
| `brain_manifest()` | Return quality manifest |
| `brain_health()` | Return health report |

The MCP server is the zero-integration path. The developer does not write any Python code. They add the JSON config to their editor, and the LLM host calls brain tools automatically. Corrections flow through the same pipeline as the Python API.

---

## 2. Correction Learning Benchmark (CLB)

### 2.1 Purpose

Prove, reproducibly, that correction-based learning works. No competitor has published a benchmark for this. Mem0 benchmarks retrieval accuracy. Letta benchmarks context window management. Neither measures whether their system stops repeating mistakes.

The CLB measures one thing: does an AI agent make the same mistake after being corrected?

### 2.2 Scenario Categories (20 each, 100 total)

**Category 1: Code Style (CS-001 through CS-020)**

Corrections to naming conventions, formatting patterns, and code organization.

Example scenario (CS-001):
```yaml
id: CS-001
name: "Variable naming: camelCase to snake_case"
setup:
  prompt: "Write a Python function to validate email addresses"
  expected_wrong: "def validateEmail(emailStr):"  # camelCase
correction:
  original: "def validateEmail(emailStr):"
  corrected: "def validate_email(email_str):"
  category: "style"
  severity: "minor"
test_prompts:
  session_5: "Write a Python function to parse phone numbers"
  session_10: "Write a Python function to normalize addresses"
  session_20: "Write a Python class for user authentication"
transfer_test:
  prompt: "Write a JavaScript function to validate URLs"
  expected_behavior: "Should NOT apply snake_case (wrong language)"
```

Example scenario (CS-012):
```yaml
id: CS-012
name: "Import ordering: stdlib before third-party"
setup:
  prompt: "Write a script that fetches JSON from an API and logs to file"
  expected_wrong: |
    import requests
    import json
    import logging
correction:
  original: "import requests\nimport json\nimport logging"
  corrected: "import json\nimport logging\n\nimport requests"
  category: "style"
  severity: "minor"
test_prompts:
  session_5: "Write a script that reads CSV and uploads to S3"
  session_10: "Write a CLI tool that parses YAML config"
  session_20: "Write a data pipeline with pandas and SQLAlchemy"
```

**Category 2: Factual Errors (FE-001 through FE-020)**

Corrections to wrong API calls, deprecated methods, incorrect parameters.

Example scenario (FE-001):
```yaml
id: FE-001
name: "Python datetime: strftime vs strptime"
setup:
  prompt: "Parse this date string '2026-03-27' into a datetime object"
  expected_wrong: "datetime.strftime('2026-03-27', '%Y-%m-%d')"
correction:
  original: "datetime.strftime('2026-03-27', '%Y-%m-%d')"
  corrected: "datetime.strptime('2026-03-27', '%Y-%m-%d')"
  category: "factual"
  severity: "moderate"
test_prompts:
  session_5: "Parse the timestamp '14:30:00' into a time object"
  session_10: "Convert '03/27/2026' to ISO format"
  session_20: "Parse a list of date strings from a CSV column"
transfer_test:
  prompt: "Format a datetime object as 'March 27, 2026'"
  expected_behavior: "Should use strftime (formatting), not strptime"
```

**Category 3: Tone/Voice (TV-001 through TV-020)**

Corrections to formality, audience awareness, and communication style.

Example scenario (TV-001):
```yaml
id: TV-001
name: "Email tone: too formal for internal team"
setup:
  prompt: "Draft a Slack message to engineering about the deploy delay"
  expected_wrong: "Dear Engineering Team, I am writing to inform you..."
correction:
  original: "Dear Engineering Team, I am writing to inform you that the deployment scheduled for this afternoon has been postponed."
  corrected: "Heads up: deploy pushed to tomorrow. The staging tests caught a race condition in the payment flow. Fix is in review."
  category: "tone"
  severity: "major"
test_prompts:
  session_5: "Write a Slack message about the new CI pipeline"
  session_10: "Draft a standup update for the team channel"
  session_20: "Write an internal announcement about the hackathon"
transfer_test:
  prompt: "Draft an email to a potential enterprise customer"
  expected_behavior: "Should NOT apply casual tone (different audience)"
```

**Category 4: Process (PR-001 through PR-020)**

Corrections to skipped steps, wrong ordering, missing verifications.

Example scenario (PR-001):
```yaml
id: PR-001
name: "Deploy process: forgot to run tests before pushing"
setup:
  prompt: "Walk me through deploying this service to production"
  expected_wrong: "1. Build image 2. Push to registry 3. Update k8s manifest"
correction:
  original: "1. Build image\n2. Push to registry\n3. Update k8s manifest"
  corrected: "1. Run test suite\n2. Build image\n3. Run smoke tests\n4. Push to registry\n5. Update k8s manifest\n6. Verify health check"
  category: "process"
  severity: "major"
test_prompts:
  session_5: "How do I deploy the auth service?"
  session_10: "Write a deploy checklist for the new microservice"
  session_20: "Create a CI/CD pipeline config for this project"
transfer_test:
  prompt: "How do I deploy a static site to Netlify?"
  expected_behavior: "Should include verification, but adapt to the platform"
```

**Category 5: Domain-Specific (DS-001 through DS-020)**

Corrections related to industry terminology, compliance rules, and domain best practices.

Example scenario (DS-001):
```yaml
id: DS-001
name: "HIPAA: PHI in log statements"
setup:
  prompt: "Add logging to the patient appointment endpoint"
  expected_wrong: "logger.info(f'Appointment created for {patient.name}')"
correction:
  original: "logger.info(f'Appointment created for {patient.name}')"
  corrected: "logger.info(f'Appointment created: id={appointment.id}')"
  category: "domain"
  severity: "major"
test_prompts:
  session_5: "Add error logging to the patient records endpoint"
  session_10: "Create a debug logging module for the healthcare API"
  session_20: "Write an audit trail for prescription changes"
transfer_test:
  prompt: "Add logging to the billing endpoint"
  expected_behavior: "Should avoid PII in logs (same domain, different entity)"
```

### 2.3 Test Protocol

Each scenario runs through this exact sequence:

```
Phase 1: Baseline
  - Present setup prompt to agent without any brain
  - Record output (confirm the mistake occurs naturally)
  - Score: does the output contain the expected error?

Phase 2: Correction
  - Feed correction to brain via brain.correct(draft, final)
  - Verify CORRECTION event stored with correct severity + category
  - Verify lesson created at INSTINCT state

Phase 3: Retention Tests (same domain)
  - Session +5: Present test_prompt_5, check if mistake recurs
  - Session +10: Present test_prompt_10, check if mistake recurs
  - Session +20: Present test_prompt_20, check if mistake recurs

Phase 4: Transfer Test (adjacent domain)
  - Present transfer_test prompt
  - Check if fix transfers correctly (should apply) or incorrectly (should NOT apply)
  - Score: correct transfer = 1.0, incorrect application = -0.5, missed transfer = 0.0

Phase 5: Graduation Check
  - After all tests: verify lesson state progression
  - Lessons that prevented mistakes should gain confidence
  - Lessons that misfired should lose confidence
```

### 2.4 Scoring

Four metrics, each reported per-category and aggregate:

**Repeat Rate (RR)** -- lower is better
```
RR = (corrections that recurred at session +N) / (total corrections tested)

Reported at: +5 sessions, +10 sessions, +20 sessions
Target: RR < 0.10 at +20 sessions (90% of corrections stick)
```

**Corrections-to-Fix (CTF)** -- lower is better
```
CTF = average number of corrections before a mistake stops recurring

Measured by: re-testing at +1, +2, +3... until 3 consecutive clean tests
Target: CTF < 2.0 (most mistakes fixed in 1-2 corrections)
```

**Transfer Score (TS)** -- higher is better
```
TS = (correct transfers + correct non-transfers) / (total transfer tests)

Correct transfer: fix applied to similar situation where it should apply
Correct non-transfer: fix NOT applied where it should not (different domain/context)
Target: TS > 0.70 (70%+ transfer accuracy)
```

**Decay Resistance (DR)** -- higher is better
```
DR = (fixes that hold at session +30) / (fixes that held at session +5)

Measures long-term retention vs short-term.
Target: DR > 0.85 (85%+ of early fixes persist long-term)
```

### 2.5 Comparison Framework

The benchmark includes a head-to-head protocol for running the same 100 scenarios against:

| System | What it tests |
|--------|--------------|
| Gradata (full) | Correction logging + graduation + rule injection |
| Gradata (logging only) | Correction logging without graduation (ablation) |
| Mem0 | Memory storage + retrieval (their correction equivalent) |
| Letta | Archival memory + core memory updates |
| System prompt only | Manual rules written in CLAUDE.md (human baseline) |
| No memory | Raw LLM with no persistence (lower bound) |

Each system gets the same 100 scenarios, same correction inputs, same test prompts. The only variable is how corrections are stored and retrieved.

### 2.6 Publication Plan

**Repository:** `gradata-systems/correction-learning-benchmark`

Structure:
```
correction-learning-benchmark/
  scenarios/
    code_style/       CS-001.yaml through CS-020.yaml
    factual_errors/   FE-001.yaml through FE-020.yaml
    tone_voice/       TV-001.yaml through TV-020.yaml
    process/          PR-001.yaml through PR-020.yaml
    domain_specific/  DS-001.yaml through DS-020.yaml
  harness/
    runner.py         Execute scenarios against any system
    scorer.py         Compute RR, CTF, TS, DR metrics
    adapters/
      gradata.py      Adapter for Gradata Brain
      mem0.py         Adapter for Mem0
      letta.py        Adapter for Letta
      baseline.py     No-memory baseline
  results/
    gradata_v0.1.json
    comparison.json
  README.md
  METHODOLOGY.md
```

**Blog post:** "Your AI Keeps Making the Same Mistakes. We Measured It."
- Open with the problem (everyone has experienced this)
- Show the benchmark design (transparent methodology)
- Present results (Gradata vs competitors vs baseline)
- Invite competitors to run the same benchmark and publish results

**Challenge:** Publish the harness with adapter interfaces. Anyone can write an adapter for their system and submit results via PR. The benchmark becomes a community standard.

---

## 3. API Surface Design

### 3.1 Public API (developers use directly)

```python
from gradata import Brain

# ── Lifecycle ──────────────────────────────────────────────
brain = Brain.init("./my-brain", domain="Engineering")    # Create new brain
brain = Brain("./my-brain")                                # Open existing brain

# ── Core Learning Loop ─────────────────────────────────────
brain.log_output(text, output_type="email", self_score=7)  # Log what AI produced
brain.correct(draft, final)                                 # Record a correction
brain.apply_brain_rules("task description")                 # Get rules for injection

# ── Observation (passive, no correction needed) ────────────
brain.observe(messages=[{"role": "user", "content": "..."}])

# ── Implicit Feedback (novel signal) ──────────────────────
brain.detect_implicit_feedback("are you sure about that?")

# ── Search & Retrieval ─────────────────────────────────────
brain.search("budget objections", top_k=5)

# ── Inspection ─────────────────────────────────────────────
brain.rules                     # List of graduated Lesson objects
brain.score                     # Float: adaptation score (0.0 - 1.0)
brain.stats()                   # Dict: file count, db size, embedding status
brain.manifest()                # Dict: full machine-readable brain spec
brain.health()                  # Dict: health report with issues

# ── Export / Import ────────────────────────────────────────
brain.export("./my-brain.zip")  # Package for sharing or backup
# Brain.init() from an exported zip is the import path

# ── Cloud ──────────────────────────────────────────────────
brain.connect_cloud()           # Route to gradata.ai for full graduation
brain.cloud_connected           # Bool: is cloud active?
```

**Properties to add** (not yet implemented):

```python
@property
def rules(self) -> list[Lesson]:
    """Return all lessons at PATTERN or RULE state, sorted by confidence descending."""
    lessons = parse_lessons(self._load_lessons_text())
    return sorted(
        [l for l in lessons if l.state in (LessonState.PATTERN, LessonState.RULE)],
        key=lambda l: l.confidence,
        reverse=True,
    )

@property
def score(self) -> float:
    """Return the brain's adaptation score (0.0 - 1.0)."""
    m = self.manifest()
    return m.get("quality", {}).get("adaptation_score", 0.0)
```

### 3.2 Internal API (hidden behind defaults)

These modules exist but developers should never call them directly. They are implementation details that the public API composes.

| Module | What it does | Why it's internal |
|--------|-------------|-------------------|
| `_diff_engine` | Levenshtein + compression distance | Developer calls `correct()`, not `compute_diff()` |
| `_edit_classifier` | 5-category classification | Runs inside `correct()` automatically |
| `_self_improvement` | Confidence math, graduation thresholds | Developer sees results via `brain.rules` |
| `_rule_engine` | Scope filtering, prompt formatting | Developer calls `apply_brain_rules()` |
| `_pattern_extractor` | Extract patterns from classified edits | Runs inside `correct()` automatically |
| `_scope` | Domain/task/audience/channel/stakes | Built automatically from context |
| `_events` | SQLite event storage | Developer calls `emit()` or higher-level methods |
| `_brain_manifest` | Manifest generation | Developer calls `brain.manifest()` |
| `_embed` | Sentence-transformers embedding | Developer calls `brain.embed()` |
| `_migrations` | SQLite schema evolution | Runs automatically on `Brain()` init |
| `_config` | Brain configuration loading | Handled by `Brain()` constructor |
| `_paths` | BrainContext DI container | Internal plumbing for path resolution |
| `_tag_taxonomy` | Category/tag management | Internal classification support |
| `_fact_extractor` | Structured fact extraction | Developer calls `brain.observe()` |
| `_failure_detectors` | Regression alerts | Runs inside `health()` automatically |
| `_stats` | Metric computation | Developer calls `brain.stats()` |
| `_validator` | Input validation | Runs before all public methods |

### 3.3 Pattern API (advanced, opt-in)

The 15 agentic patterns are public but secondary. They are building blocks for developers who want to compose custom agent architectures. Most developers will never import them directly.

```python
# These exist but are not part of the "first 5 minutes" experience:
from gradata import Pipeline, Stage, ParallelBatch
from gradata import InputGuard, OutputGuard
from gradata import SmartRAG, NaiveRAG
from gradata import EpisodicMemory, SemanticMemory
from gradata import reflect, EMAIL_CHECKLIST
from gradata import assess_risk, HumanLoopGate
from gradata import classify_scope, AudienceTier
from gradata import orchestrate, Delegation
from gradata import MCPBridge, MCPServer
from gradata import RuleApplication
```

### 3.4 API Design Principles

1. **One import, one object.** `from gradata import Brain` is the entire getting-started surface.
2. **Verbs match the user's mental model.** `correct()` not `record_edit()`. `observe()` not `extract_facts()`. `search()` not `query_fts5()`.
3. **Underscore prefix = internal.** Every module that starts with `_` is an implementation detail. If it does not start with `_`, it is a public contract.
4. **Zero required deps.** The base package is pure Python + stdlib. Optional features (embeddings, cloud) are extras.
5. **Fallback gracefully.** If an optional module is not installed, the method returns an empty result instead of crashing. ImportErrors are caught and handled at every boundary.
6. **Event-sourced.** Every state change is an immutable event in SQLite. The brain directory is the complete state. Copy it, back it up, version control it.

---

## 4. README.md (Competition-Grade)

The following README is designed to compete with Mem0 (48K stars) for developer attention. It is under 200 lines. Every line earns its place.

---

```markdown
# Gradata

Your AI keeps making the same mistakes. Gradata fixes that.

Gradata is a Python SDK that makes AI agents learn from corrections. When you fix your AI's output, Gradata captures the correction, classifies what went wrong, and graduates fixes into permanent behavioral rules. Over time, your agent stops repeating the same errors.

```python
from gradata import Brain

brain = Brain.init("./my-brain")
brain.correct(draft="inline SQL in the API...", final="repository pattern in the API...")
rules = brain.apply_brain_rules("write API design")  # remembers, permanently
```

## The Problem

You correct your AI. It forgets. You correct it again. You build a system prompt full of rules you wrote by hand. That works until you have 50 rules and no idea which ones matter.

**Memory tools remember. Gradata learns.**

| | Memory (Mem0, Zep) | Learning (Gradata) |
|---|---|---|
| Stores corrections | Yes | Yes |
| Retrieves past context | Yes | Yes |
| Knows which corrections matter | No | Yes (confidence scoring) |
| Stops applying bad rules | No | Yes (misfire demotion) |
| Proves improvement over time | No | Yes (adaptation score) |
| Kills rules that never fire | No | Yes (auto-kill after 20 idle sessions) |

## How It Works

```
You correct AI output
        |
        v
brain.correct(draft, final)
        |
        v
Diff engine computes edit distance + severity
Edit classifier categorizes: tone / content / structure / factual / style
        |
        v
Lesson created at INSTINCT (confidence 0.30)
        |
        v
Lesson applied to future prompts via brain.apply_brain_rules()
If it prevents the mistake: confidence increases
If it causes a new mistake: confidence drops (misfire penalty)
        |
        v
INSTINCT (0.30) --[3+ applications]--> PATTERN (0.60) --[5+ applications]--> RULE (0.90)
        |                                                                        |
        v                                                                        v
  Killed (contradicted                                              Permanent behavioral rule
   or idle 20+ sessions)                                         (your agent has genuinely learned)
```

All data is event-sourced in a single SQLite file. Your brain is a directory. Copy it, back it up, move it between machines.

## Install

```bash
pip install gradata
```

Zero required dependencies. Python 3.11+. Pure stdlib.

```bash
pip install gradata[embeddings]  # local sentence-transformers
pip install gradata[all]         # everything
```

## Quick Start

```python
from gradata import Brain

# Create a brain
brain = Brain.init("./my-brain", domain="Engineering")

# Log AI output
brain.log_output("Here is the API design...", output_type="design_doc")

# Record a correction
result = brain.correct(
    draft="REST endpoints with inline SQL...",
    final="REST endpoints with repository pattern..."
)
print(result["severity"])  # "moderate"

# Get rules for the next prompt
rules = brain.apply_brain_rules("write API design")
# Inject into your LLM's system prompt or tool context

# See the brain's health
print(brain.manifest())
```

## MCP Server (Claude Code, Cursor, VS Code)

```json
{
  "mcpServers": {
    "gradata": {
      "command": "python",
      "args": ["-m", "gradata.mcp_server", "--brain-dir", "./my-brain"]
    }
  }
}
```

Zero code required. Your editor calls brain tools automatically.

## CLI

```bash
gradata init ./my-brain --domain Sales
gradata search "budget objections"
gradata stats
gradata manifest --json
gradata doctor
gradata export
```

## What's Inside

**Core:** correction logging, event storage (append-only SQLite), FTS5 search, brain manifest, export/import.

**15 agentic patterns** (pure Python, zero deps): pipeline, parallel, RAG, reflection, guardrails, human-in-the-loop, scope classification, sub-agents, evaluator loops, memory (episodic/semantic/procedural), MCP bridge, rule tracking.

**Integrations:** Anthropic, OpenAI, LangChain, CrewAI adapters.

## Graduation Pipeline

The core innovation. Not just storage, but a confidence system that separates signal from noise.

| State | Confidence | Meaning |
|-------|-----------|---------|
| INSTINCT | 0.00 - 0.59 | New lesson, tentative |
| PATTERN | 0.60 - 0.89 | Applied 3+ times, gaining confidence |
| RULE | 0.90+ | Applied 5+ times, proven behavioral rule |
| KILLED | 0.00 | Contradicted or idle, removed from injection |

Confidence moves on evidence:
- **Survival bonus:** lesson applied, no contradiction = +0.03 to +0.12 (scaled by severity)
- **Misfire penalty:** lesson applied, caused new error = -0.02 to -0.20 (scaled by severity)
- **Idle kill:** lesson not applied for 20+ relevant sessions = auto-killed

## Real Results

From a single-user study (N=1, 71 sessions, 9 days). Multi-user validation pending.

| Metric | Value | Source |
|---|---|---|
| Correction rate | 5.0 to 0.004 per output | event log (CORRECTION + OUTPUT counts) |
| Error categories eliminated | 13 of 14 stopped recurring | event log (category grouping) |
| Lessons graduated to rules | 48 of 107 (45%) | lessons.md status counts |

## Cloud Dashboard

Connect to [gradata.ai](https://gradata.ai) for server-side graduation, quality dashboards, and brain export.

```python
brain.connect_cloud()  # reads GRADATA_API_KEY from env
```

## API at a Glance

```python
brain = Brain.init("./my-brain")          # Create
brain = Brain("./my-brain")               # Open
brain.correct(draft, final)               # Learn from correction
brain.log_output(text, type, score)       # Track AI output
brain.apply_brain_rules("task")           # Get rules for prompt
brain.observe(messages)                   # Passive fact extraction
brain.search("query")                     # Full-text search
brain.manifest()                          # Quality proof
brain.export("brain.zip")                 # Package for sharing
brain.connect_cloud()                     # Enable cloud graduation
```

## Caveats

- v0.1.0. API will change.
- Results above are N=1. Your mileage will vary.
- Full graduation engine coming to open source via cloud sync.
- Local-only by default. Cloud is opt-in.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

AGPL-3.0. You can use Gradata in any project. If you modify the SDK itself and distribute it, those modifications must be open source. Your application code and brain data are yours. See [LICENSE](LICENSE).
```

---

## 5. Implementation Priorities

What needs to be built before launch, in dependency order.

### Phase 0: API Surface Polish (pre-launch, 1 week)

Add the two missing convenience properties to `brain.py`:

1. `brain.rules` -- property that returns graduated lessons sorted by confidence
2. `brain.score` -- property that returns adaptation score as a float

These are trivial to implement (10 lines each) but they make the "after 50 corrections" experience work without the developer touching internals.

### Phase 1: Benchmark Repository (week 1-2)

1. Write 20 scenarios per category (100 total) in YAML
2. Build the test harness (`runner.py`, `scorer.py`)
3. Build the Gradata adapter
4. Run the benchmark against Gradata
5. Build the baseline adapter (no memory)
6. Run the benchmark against baseline
7. Compute and publish results
8. Write the blog post

### Phase 2: README + PyPI (week 2)

1. Replace existing README with the competition-grade version above
2. Verify `pip install gradata` works from clean environment
3. Test MCP server setup with Claude Code
4. Test CLI commands
5. Publish v0.1.0 to PyPI

### Phase 3: Benchmark Publication (week 3)

1. Build Mem0 adapter (their `add` + `search` API)
2. Run benchmark against Mem0
3. Publish `gradata-systems/correction-learning-benchmark` repo
4. Publish blog post
5. Post to Hacker News, r/MachineLearning, AI Twitter

### Phase 4: Cloud Dashboard MVP (week 4-6)

1. gradata.ai landing page
2. API endpoint for `connect_cloud()`
3. Dashboard: adaptation score, correction trends, graduated rules
4. Brain sync (local events pushed to cloud)

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| N=1 results don't replicate with other users | Medium | Critical | Benchmark design includes multi-system comparison. Blog post is transparent about N=1. Early adopters provide N=2-10 before claims scale. |
| Mem0 copies the graduation pipeline | Medium | High | First-mover on benchmark. The benchmark itself becomes the standard. Implementation complexity is 9 months of iteration, not something copyable in a sprint. |
| Developers don't understand "correction-based learning" | High | High | README leads with the problem ("your AI keeps making the same mistakes"), not the solution. Quick start is 3 lines. MCP server is zero-code. |
| AGPL license scares enterprise users | Medium | Medium | README explains clearly: your app code and brain data are yours. AGPL only applies to SDK modifications. Consider dual license later. |
| Benchmark scenarios are too synthetic | Low | Medium | Scenarios based on real corrections from 71 sessions of production use. Include methodology document explaining provenance. |
| Cloud dashboard delays launch | High | Low | SDK launches independently. Cloud is additive. Local-only mode is the complete product. |

---

## 7. Competitive Positioning

### One-line positioning

"Mem0 remembers. Gradata learns."

### Detailed positioning

| Dimension | Mem0 | Letta | Zep | Gradata |
|-----------|------|-------|-----|---------|
| Core model | Memory graph | Stateful agents | Temporal memory | Correction graduation |
| Learning signal | Explicit `add()` calls | Core memory edits | Conversation context | Draft-to-final diffs |
| Confidence tracking | No | No | No | Yes (0.0 - 1.0 per lesson) |
| Misfire detection | No | No | No | Yes (penalty on contradiction) |
| Idle rule cleanup | No | No | No | Yes (auto-kill after 20 sessions) |
| Quality proof | No | No | No | Yes (brain.manifest.json) |
| Benchmark | Retrieval accuracy | Agent completion | Context recall | CLB (correction retention) |
| Dependencies | chromadb, qdrant | postgres, docker | postgres | Zero (pure stdlib) |
| License | Apache 2.0 | Apache 2.0 | Apache 2.0 | AGPL-3.0 |

The competitors store information. Gradata evaluates whether stored information is working. That is the fundamental difference: a feedback loop on the feedback loop.

---

## 8. Success Metrics for Launch

| Metric | Target (30 days) | Target (90 days) |
|--------|------------------|-------------------|
| PyPI installs | 500 | 5,000 |
| GitHub stars | 200 | 2,000 |
| CLB forks/adapters | 5 | 20 |
| gradata.ai signups | 50 | 500 |
| Blog post views | 5,000 | 25,000 |
| N=2+ validation (users reporting correction rate drops) | 3 | 20 |

The single most important metric at launch is **N=2+ validation**: at least 3 users who independently confirm that Gradata reduced their correction rates. Everything else (stars, installs, signups) is vanity until the core claim replicates.
