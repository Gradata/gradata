# Gradata — AI that learns your judgment

Every correction you make teaches your AI something. Gradata captures those corrections, extracts the behavioral instruction behind them, and graduates it into a rule. Over time, your AI stops needing corrections. It converges on your judgment.

Not generally more intelligent. Calibrated to you.

```bash
pip install gradata
```

Works with any LLM. Python 3.11+. Zero required dependencies.

## Quick Start

```python
from gradata import Brain

brain = Brain.init("./my-brain")

# Your AI produces output. You fix it. Brain learns.
brain.correct(
    draft="We are pleased to inform you of our new product offering.",
    final="Hey, check out what we just shipped."
)
# Brain extracts: "Write in a casual, direct tone — avoid formal business language"

# Next session — inject learned rules into the prompt:
rules = brain.apply_brain_rules("write an email")
# > "[RULE:0.92] TONE: Write in a casual, direct tone..."

# Prove the brain is converging:
manifest = brain.manifest()
```

## How It Works

```
You correct your AI
       |
brain.correct(draft, final)
       |
Behavioral instruction extracted:
  "We are pleased..." → "Hey, check this out"
  = "Write in a casual, direct tone"
       |
Confidence grows with reinforcement:
  INSTINCT (0.40) → PATTERN (0.60) → RULE (0.90)
       |
3+ related rules → META-RULE emerges
  "Use casual tone" + "No sign-offs" + "Short sentences"
  = "Match Oliver's direct communication style"
       |
Your AI converges on YOUR judgment
```

## Why This Works

**Corrections are signal.** Every time you edit an AI's output, you're encoding your expertise. Most systems throw that signal away. Gradata captures it, extracts what you meant, and turns it into a rule.

**Meta-rules are personalized intelligence.** When individual rules start clustering — your email tone preferences aligning with your code review style aligning with your process preferences — meta-rules emerge. The AI starts predicting your patterns across domains. To you, it just "gets it." That's not general intelligence. That's convergence on your judgment.

**Convergence is measurable.** Track corrections-per-session over time. When the curve flattens, the brain has learned your style. That curve is the product demo.

## Ablation Experiment Results

We ran a controlled experiment: 10 tasks scored with and without brain rules.

| Metric | Without Rules | With Rules | Delta |
|--------|--------------|------------|-------|
| Overall quality | 6.60 | 7.47 | **+13.2%** |
| Preference adherence | 5.40 | 6.90 | **+1.50** |
| Correctness | 7.50 | 7.80 | +0.30 |

The rules didn't make the AI generally smarter. They made it smarter **for that specific user** — matching their email style, prospecting workflow, code conventions, and session handoff format.

## Behavioral Extraction

Old approach (diff fingerprints — useless):
> `"Content change (added: getattr)"`

New approach (behavioral instructions — rentable):
> `"Use getattr() for safe attribute access on objects that may lack the attribute"`

Every correction now produces an actionable instruction through:
1. **Cache hit** — instant lookup of previously extracted instructions
2. **Template match** — pre-built instructions for common patterns
3. **LLM extraction** — Haiku call for novel corrections (~$0.001 each)

## What Makes This Different

Memory systems remember what you said. Gradata learns how you think.

| System | Remembers | Learns from corrections | Graduates rules | Proves convergence |
|--------|-----------|------------------------|-----------------|-------------------|
| Mem0 | Yes | No | No | No |
| Letta (MemGPT) | Yes | No | No | No |
| LangChain Memory | Yes | No | No | No |
| Fine-tuning | Permanent | Expensive, slow | No | No |
| System prompts | Static | Manual only | No | No |
| **Gradata** | Yes | **Yes** | **Yes** | **Yes** |

**vs Mem0:** Mem0 stores context. Gradata evolves behavior. You could use both.

**vs fine-tuning:** Fine-tuning is expensive, slow, and loses the original model. Gradata adapts at inference time — every correction takes effect immediately.

**vs system prompts:** System prompts are static. Gradata's rules are dynamic — they graduate, decay, and evolve based on your corrections.

## Rent Trained Brains (Coming Soon)

A sales leader trains a brain over 200 sessions. Their outreach patterns, objection handling, follow-up cadence — all encoded as graduated rules.

A new SDR rents that brain. Day one, they write emails in the leader's voice and follow the leader's prospecting workflow. The brain isn't smarter. It's calibrated to a specific human's judgment.

That trained brain is the rentable asset.

## Features

**Core learning loop:**
- `brain.correct(draft, final)` — captures corrections, extracts behavioral instructions, creates lessons
- `brain.apply_brain_rules(task)` — injects graduated rules into prompts
- `brain.manifest()` — mathematical proof the brain is converging
- `brain.prove()` — paired t-test showing correction rate decreased after graduation

**Event Bus (v0.3.0):**
- `brain.bus.on(event, handler)` — subscribe to any event in the pipeline
- Events: `correction.created`, `lesson.graduated`, `meta_rule.created`, `session.ended`

**Human-in-the-loop:**
- `brain.review_pending()` — list lessons awaiting approval
- `brain.approve_lesson(id)` / `brain.reject_lesson(id)` — pre-graduation veto
- `gradata review` CLI — approve/reject from terminal

**Integrations:**
- OpenAI, Anthropic, LangChain, CrewAI adapters
- MCP server for Claude Code, Cursor, Windsurf
- `gradata init --mcp` generates config automatically

## Pricing

| | Free | Pro | Team |
|---|---|---|---|
| **Price** | $0 | $9-29/mo | Contact |
| Local brain | Yes | Yes | Yes |
| Behavioral extraction | Templates | **LLM-powered** | LLM-powered |
| Graduation pipeline | Basic | **Cloud-optimized** | Cloud-optimized |
| Convergence dashboard | Score only | **Full analytics** | Full + admin |
| Brain rental | -- | -- | **Yes** |

Free tier is fully functional. Paid makes the brain learn faster and gives you convergence analytics.

## CLI

```bash
gradata init                          # Create a brain
gradata correct --draft "..." --final "..."  # Log a correction
gradata review                        # Approve/reject pending lessons
gradata stats                         # Brain health + convergence
gradata manifest --json               # Quality proof
gradata doctor                        # Diagnose issues
```

## Architecture

```
src/gradata/
  brain.py              # Brain class (public API)
  events_bus.py         # Central event bus
  _core.py              # Correction pipeline + behavioral extraction
  _events.py            # Append-only event log (JSONL + SQLite)
  enhancements/
    edit_classifier.py    # Classification + behavioral instruction extraction
    instruction_cache.py  # LLM extraction cache
    self_improvement.py   # Graduation pipeline
    diff_engine.py        # Edit distance, severity
    meta_rules.py         # Meta-rule synthesis
  rules/
    rule_engine.py        # Inject rules into prompts
    rule_ranker.py        # Context-aware ranking
  integrations/           # OpenAI, Anthropic, LangChain, CrewAI
  contrib/patterns/       # Optional agentic patterns
```

## License

AGPL-3.0. Commercial license available.
