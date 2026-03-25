# aios-brain

**AI that gets better the more you use it.** Not memory. Not fine-tuning. Behavioral adaptation that compounds.

Most AI tools forget everything between sessions. Memory tools store facts but never learn *how* you work. AIOS Brain is different: it watches how you correct AI output, graduates those corrections into behavioral rules, and proves the improvement with real data.

```
Session 1:   AI drafts email → you rewrite the subject line
Session 10:  AI notices the pattern → [INSTINCT] "Short subject lines preferred"
Session 50:  Pattern proven → [PATTERN] "Subject lines under 5 words"
Session 100: Rule locked → [RULE] "Subject = company name only. Always."
```

Your CLAUDE.md grows over time. A brain *shrinks* as behaviors graduate from written rules into proven patterns. That's the compound proof.

**Zero dependencies. One SQLite file. Works with any LLM.**

## Installation

```bash
pip install aios-brain              # zero deps, works instantly
pip install aios-brain[gemini]      # adds Gemini embeddings (free tier)
pip install aios-brain[all]         # full stack with vector search
```

Requires Python 3.11+. 605 tests passing.

## Quick Start

```python
from aios_brain import Brain

# Create a new brain
brain = Brain.init("./my-brain", domain="engineering")

# Log AI output (before user sees it)
brain.log_output("Here's the API design...", output_type="design_doc", self_score=7)

# Record correction (after user edits)
brain.correct(
    draft="Here's the API design with REST endpoints...",
    final="Here's the API design with gRPC endpoints..."
)
# Automatically: diffs, classifies edit (factual), extracts pattern, logs event

# Apply learned rules to next prompt
rules = brain.apply_brain_rules(task="design_doc", context={"audience": "backend_team"})
# Returns graduated PATTERN/RULE lessons scoped to this task type

# Search brain knowledge
results = brain.search("API design patterns")

# Check brain health
health = brain.health()
print(f"FDA: {health['first_draft_acceptance']}%")
print(f"Correction rate: {health['correction_rate']}")

# Agent graduation (agents learn too)
brain.agent_graduation.record_outcome("research", "found 3 papers", "approved")
brain.agent_graduation.record_outcome("writer", "draft was too formal", "edited",
                                       edits="Tone was wrong for this audience",
                                       task_type="email_draft")
print(brain.agent_graduation.format_dashboard())
```

## How It Works

```
User corrects AI output
    → Diff engine computes edit distance + severity
    → Edit classifier categorizes (tone/content/structure/factual/style)
    → Pattern extractor finds behavioral pattern
    → Pattern scoped to context (domain/task_type/audience/channel/stakes)
    → Confidence starts at 0.30 (INSTINCT)
    → Each session it survives: +0.10
    → Each session it's contradicted: -0.25
    → At 0.60: graduates to PATTERN (applied by default)
    → At 0.90: graduates to RULE (enforced)
    → Zero fires for 15+ sessions: killed (UNTESTABLE)

Same pipeline applies to agents:
    → Orchestrator evaluates agent output
    → Edits become agent-level corrections
    → Agent develops its own behavioral profile
    → Approval gate graduates: CONFIRM → PREVIEW → AUTO
    → Agent learnings distill upward to brain level
```

## CLI

Every SDK method has a CLI equivalent:

```bash
# Bootstrap a new brain
aios-brain init ./my-brain --domain Sales

# Search
aios-brain search "budget objections"
aios-brain search "competitor pricing" --mode semantic --top 10

# Embed files into vector store
aios-brain embed
aios-brain embed --full

# Generate brain.manifest.json
aios-brain manifest
aios-brain manifest --json

# Stats
aios-brain stats

# Data flow audit
aios-brain audit
aios-brain audit --json

# Export for marketplace
aios-brain export
aios-brain export --mode domain-only
```

Use `--brain-dir` / `-b` to point at a brain directory other than cwd:

```bash
aios-brain -b /path/to/brain search "query"
```

## Architecture

### Brain Directory Structure

```
my-brain/
├── brain.manifest.json      # Machine-readable brain spec
├── system.db                # SQLite — events, facts, metrics
├── .vectorstore/            # ChromaDB embeddings
├── .embed-manifest.json     # File hash tracking for delta embeds
├── loop-state.md            # Episodic state between sessions
├── VERSION.md
├── prospects/               # Per-prospect knowledge files
├── sessions/                # Session logs
├── personas/                # Buyer persona definitions
├── objections/              # Objection handling patterns
├── competitors/             # Competitive intelligence
├── emails/                  # Email patterns and templates
│   └── PATTERNS.md
├── learnings/               # Graduated lessons
├── metrics/                 # Session quality metrics
├── pipeline/                # Deal tracking
├── demos/                   # Demo prep and notes
├── vault/                   # Protected files
└── scripts/                 # Brain scripts (embed, query, etc.)
```

### Memory Types

Every file in the brain has a memory type, declared via frontmatter comment:

```markdown
<!-- memory_type: episodic -->
```

| Type | Purpose | Examples |
|------|---------|----------|
| **episodic** | What happened — session logs, interaction history | `sessions/`, `loop-state.md`, prospect timelines |
| **semantic** | What is known — facts, research, profiles | `prospects/`, `competitors/`, `personas/` |
| **procedural** | How to do things — workflows, scripts, patterns | `emails/PATTERNS.md`, `scripts/`, gate definitions |
| **strategic** | Why — positioning, lessons, quality rules | `learnings/`, quality rubrics, strategy docs |

### Event System

The brain logs structured events to `system.db`:

```python
# Emit
brain.emit("CORRECTION", "user", {
    "category": "ACCURACY",
    "detail": "Revenue figure was wrong"
})

# Query
events = brain.query_events(event_type="CORRECTION", last_n_sessions=3)
```

### Fact Store

Structured facts extracted from knowledge files:

```python
facts = brain.get_facts(prospect="Hassan Ali")
brain.extract_facts()  # Re-extract from all prospect files
```

### Context Compilation

Get relevant brain context for any user message:

```python
context = brain.context_for("draft a follow-up email to Hassan")
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BRAIN_DIR` | No | Default brain directory path |
| `GEMINI_API_KEY` | For semantic search | Gemini API key (free tier) |
| `PIPEDRIVE_API_KEY` | No | CRM sync |
| `INSTANTLY_API_KEY` | No | Email automation sync |

### brain.manifest.json

Machine-readable spec generated by `brain.manifest()`. Schema:

```json
{
  "schema_version": "1.0.0",
  "metadata": {
    "brain_version": "v2.0.0",
    "domain": "Sales",
    "maturity_phase": "INFANT",
    "sessions_trained": 34
  },
  "quality": {
    "correction_rate": null,
    "lessons_graduated": 63,
    "lessons_active": 20,
    "first_draft_acceptance": null
  },
  "memory_composition": {
    "episodic": 50,
    "semantic": 29,
    "procedural": 3,
    "strategic": 16
  },
  "rag": {
    "active": true,
    "provider": "gemini",
    "model": "gemini-embedding-2-preview",
    "dimensions": 768,
    "chunks_indexed": 226,
    "hybrid_search": true
  },
  "compatibility": {
    "python": ">=3.11",
    "chromadb": ">=0.5.0",
    "platform": "any"
  }
}
```

### Maturity Phases

Brains progress through maturity phases based on session count:

| Phase | Sessions | Description |
|-------|----------|-------------|
| INFANT | 0-50 | High tolerance, learning fast |
| ADOLESCENT | 50-100 | Patterns stabilizing |
| MATURE | 100-200 | Low tolerance, pruning begins |
| STABLE | 200+ | Minimal tolerance, aggressive pruning |

## Python API Reference

```python
Brain.init(path, domain="General") -> Brain   # Bootstrap new brain
Brain(path) -> Brain                           # Open existing brain

brain.search(query, mode=None, top_k=5)       # Search (keyword/semantic/hybrid)
brain.embed(full=False)                        # Embed files into ChromaDB
brain.emit(event_type, source, data, tags)     # Log event
brain.query_events(event_type, last_n_sessions)# Query events
brain.get_facts(prospect, fact_type)           # Query facts
brain.extract_facts()                          # Extract facts from files
brain.manifest()                               # Generate manifest
brain.export(output_path, mode="full")         # Export brain archive
brain.context_for(message)                     # Compile context for a message
brain.stats()                                  # Brain statistics dict
```

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make changes and add tests
4. Submit a PR against `main`

Brain layer code (`aios_brain/`) must stay runtime-agnostic. No dependencies on Claude Code, specific LLM providers, or host OS features. The SDK should work with any agent framework.

## License

MIT
