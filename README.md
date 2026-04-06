# Gradata

Procedural memory for AI agents. Corrections become behavioral rules that compound over time.

Your AI keeps making the same mistakes. Gradata fixes that.

```bash
pip install gradata
gradata init
```

Works with any LLM. Python 3.11+. Zero required dependencies.

## Quick Start

```python
from gradata import Brain

brain = Brain.init("./my-brain")

# Your AI produces output. You fix it.
brain.correct(
    draft="We are pleased to inform you of our new product offering.",
    final="Hey, check out what we just shipped."
)

# Brain learns. Next time, inject rules into the prompt:
rules = brain.apply_brain_rules("write an email")
# > "[RULE:0.92] TONE: Use casual, direct language..."

# Prove the brain is getting better:
manifest = brain.manifest()
```

## How It Works

```
Human corrects AI output
       |
brain.correct(draft, final)
       |
Diff computed > severity classified > lesson created
       |
Confidence grows with each reinforcement:
  0.40 = INSTINCT (new, unproven)
  0.60 = PATTERN  (seen enough to trust)
  0.90 = RULE     (injected into every prompt)
       |
3+ related rules > META-RULE (general principle)
       |
brain.apply_brain_rules() > AI stops making that mistake
```

## Nervous System (v0.3.0)

Gradata v0.3.0 introduces the **Event Bus** -- a central nervous system that wires all components together:

```python
# Every correction triggers the full pipeline automatically:
brain.correct(draft, final)
  # > EventBus emits "correction.created"
  #   > Embeddings subscriber embeds the lesson (async)
  #   > Session history records which rules were corrected
  #   > Tool findings check if this matched a lint/test failure

brain.end_session()
  # > EventBus emits "session.ended"
  #   > Graduation sweep promotes lessons
  #   > Session history computes rule effectiveness
  #   > Embeddings cluster related lessons for meta-rules
```

**Subscribe to any event:**
```python
brain.bus.on("correction.created", my_handler)
brain.bus.on("lesson.graduated", my_dashboard_push)
brain.bus.on("meta_rule.created", my_slack_notifier)
```

### Semantic Clustering

Meta-rules now form by **meaning**, not just keywords:

```python
# These lessons cluster automatically via embeddings:
# "validate email before upload"
# "verify addresses before campaign push"
# "check email format before send"
#   > META-RULE: "Always validate contact data before external operations"
```

Two-tier embeddings: lightweight local model (free) or cloud API (paid, higher quality).

### Rule Effectiveness Tracking

Rules that work get boosted. Rules that don't get demoted:

```python
# Rule "always validate email" injected > never corrected > effectiveness: HIGH > boost
# Rule "use formal tone" injected > corrected 3/5 sessions > effectiveness: LOW > demote
```

### Context-Aware Rule Ranking

Rules ranked by what you're actually working on, not just confidence:

```
30% scope match | 25% confidence | 20% context relevance | 15% recency | 10% fire count
```

## Features

**Core learning loop:**
- `brain.correct(draft, final)` -- capture corrections with automatic diff + severity classification
- `brain.apply_brain_rules(task)` -- inject graduated rules into prompts
- `brain.manifest()` -- mathematical proof the brain is improving (compound score)
- `brain.prove()` -- paired t-test showing correction rate decreased after graduation

**Event Bus (v0.3.0):**
- `brain.bus.on(event, handler)` -- subscribe to any event in the pipeline
- Built-in events: `correction.created`, `lesson.graduated`, `lesson.demoted`, `meta_rule.created`, `session.started`, `session.ended`, `rules.injected`, `tool.finding`
- Async handlers for non-blocking integrations
- Error isolation -- handler failures never break the pipeline

**Human-in-the-loop approval:**
- `brain.review_pending()` -- list lessons awaiting approval
- `brain.approve_lesson(id)` / `brain.reject_lesson(id)` -- pre-graduation veto gate
- `gradata review` CLI -- approve/reject from terminal

**Encryption at rest:**
- `pip install gradata[encrypted]` -- AES-128 via Fernet
- `Brain("./my-brain", encryption_key="...")` or `GRADATA_ENCRYPTION_KEY` env var

**Correction provenance:**
- Every lesson tracks which correction events created it
- Meta-rules link back to their source lessons
- Full audit trail: correction > lesson > rule > meta-rule

**23 optional agentic patterns** (`from gradata.contrib.patterns import ...`):
Pipeline, Guard, RAG, Reflection, Memory, MCP, Orchestrator, Q-Learning Router, and more.

## Works With Any LLM

```python
# OpenAI
from gradata.integrations.openai_adapter import patch_openai
client = patch_openai(openai_client, brain_dir="./my-brain")

# Anthropic
from gradata.integrations.anthropic_adapter import patch_anthropic
client = patch_anthropic(anthropic_client, brain_dir="./my-brain")

# LangChain
from gradata.integrations.langchain_adapter import BrainMemory
memory = BrainMemory(brain_dir="./my-brain")

# CrewAI
from gradata.integrations.crewai_adapter import BrainCrewMemory
crew = Crew(memory=BrainCrewMemory(brain_dir="./my-brain"))

# Any other LLM -- just call the API directly
brain.correct(draft=llm_output, final=user_edited_output)
rules = brain.apply_brain_rules(task_description)
```

## CLI

```bash
gradata init                          # Create a brain + scaffold hooks
gradata correct --draft "..." --final "..."  # Log a correction
gradata review                        # Approve/reject pending lessons
gradata stats                         # Brain health
gradata manifest --json               # Quality metrics
gradata search "topic"                # Search brain knowledge
gradata export                        # Package for sharing
gradata doctor                        # Diagnose issues
```

## MCP Server

Works with Claude Code, Cursor, Windsurf, and any MCP-compatible host:

```json
{
  "mcpServers": {
    "gradata": {
      "command": "python",
      "args": ["-m", "gradata.mcp_server"]
    }
  }
}
```

Or let `gradata init --mcp` generate the config for you.

## What Makes This Different

| System | Remembers | Learns from corrections | Graduates rules | Proves improvement | Event Bus |
|--------|-----------|------------------------|-----------------|-------------------|-----------|
| Mem0 | Yes | No | No | No | No |
| Letta (MemGPT) | Yes | No | No | No | No |
| LangChain Memory | Yes | No | No | No | No |
| **Gradata** | Yes | **Yes** | **Yes** | **Yes** | **Yes** |

Everyone else builds *declarative memory* -- "remember that I like short emails."

Gradata builds *procedural memory* -- "after 12 corrections on email tone, graduated a RULE at 0.92 confidence: use casual, direct language." That's a learned behavior with a proof trail.

## Pricing

| | Free | Pro | Team |
|---|---|---|---|
| **Price** | $0 | $9-29/mo | Contact |
| Local brain | Yes | Yes | Yes |
| Graduation pipeline | Basic | **Optimized (cloud)** | Optimized |
| Meta-rule synthesis | Keyword | **Semantic (embeddings)** | Semantic |
| Dashboard (gradata.ai) | Compound score only | **Full analytics** | Full + admin |
| Cross-brain learning | -- | -- | **Yes** |
| Rule effectiveness tracking | Local | **Cloud-synced** | Cloud-synced |
| Support | Community | Email | Dedicated |

Free tier is fully functional. Paid makes the brain learn faster and gives you analytics.

## Platform Support

- **OS:** Windows, macOS, Linux
- **Python:** 3.11+
- **LLMs:** OpenAI, Anthropic, LangChain, CrewAI, or any LLM via direct API
- **IDE Integration:** Claude Code, Cursor, Windsurf (via MCP)
- **Storage:** Local SQLite (zero infrastructure)

## Optional Extras

```bash
pip install gradata[encrypted]    # Encryption at rest (Fernet AES)
pip install gradata[embeddings]   # Local sentence-transformers
pip install gradata[all]          # Everything
```

## Architecture

```
src/gradata/
  brain.py              # Brain class (public API)
  events_bus.py         # Central event bus (v0.3.0)
  _core.py              # Correction pipeline + graduation
  _events.py            # Append-only event log (JSONL + SQLite)
  _types.py             # Lesson, LessonState, typed models
  enhancements/
    self_improvement.py   # Graduation pipeline
    meta_rules.py         # Meta-rule synthesis
    diff_engine.py        # Edit distance, severity
  rules/
    rule_engine.py        # Inject rules into prompts
    rule_ranker.py        # Context-aware ranking (v0.3.0)
    scope.py              # Task classification
  integrations/
    embeddings.py         # Two-tier embeddings (v0.3.0)
    session_history.py    # Rule effectiveness (v0.3.0)
    openai_adapter.py     # OpenAI integration
    anthropic_adapter.py  # Anthropic integration
    langchain_adapter.py  # LangChain integration
    crewai_adapter.py     # CrewAI integration
  hooks/
    auto_correct.py       # Automatic diff capture
    inject-brain-rules.js # Rule injection + QMD context
    tool-finding-capture.js # Lint/test findings to lessons
    session-history-sync.js # Cross-session effectiveness
  contrib/patterns/       # Optional agentic patterns
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

AGPL-3.0. Commercial license available for teams that need it.
