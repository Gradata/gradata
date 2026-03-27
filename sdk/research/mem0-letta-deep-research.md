# Deep Research: Mem0 and Letta (MemGPT)
## Competitive Intelligence for Behavioral Adaptation SDK
### Date: 2026-03-25

---

## PART 1: MEM0

### 1.1 Architecture

Mem0 is a **pluggable memory layer** that bolts onto any agent framework. It is NOT an agent runtime — it's middleware.

**Storage: Hybrid (Vector + Graph + Key-Value)**

The system writes to three backends in parallel via a thread pool:

| Backend | Purpose | Tech |
|---------|---------|------|
| Vector Store | Semantic similarity search | Any supported vector DB (Qdrant, Pinecone, Chroma, etc.) |
| Graph Store | Entity-relationship reasoning | Neo4j |
| Key-Value / History | Audit trail, temporal queries | Internal storage |

The graph layer (Mem0^g) represents memories as directed labeled graphs G = (V, E, L):
- **Nodes (V)**: Entities with type classification, embedding vector, and timestamp metadata
- **Edges (E)**: Relationship triplets (source, relation, destination)
- **Labels (L)**: Semantic types assigned to nodes

**Data model**: Natural language facts stored as text + embedding. NOT structured records. A memory is literally a string like "the researcher prefers colons over em dashes in emails" with a vector embedding alongside it.

### 1.2 Memory Extraction Algorithm

Two-phase pipeline: **Extraction** then **Update**.

**Extraction Phase:**
1. Takes the latest user-assistant exchange (m_{t-1}, m_t)
2. Constructs context from: (a) conversation summary S from DB, (b) last m=10 messages
3. LLM function phi extracts candidate memories omega = {omega_1, ..., omega_n}
4. This is passive — the developer calls `memory.add(messages)` and the system decides what matters

**Update Phase (the clever bit):**
For each extracted fact:
1. Retrieve top s=10 semantically similar existing memories via vector search
2. Present candidate fact + retrieved memories to LLM via function-calling
3. LLM chooses one of four operations:
   - **ADD**: New fact, no semantic equivalent exists
   - **UPDATE**: Fact augments existing memory with new info
   - **DELETE**: Fact contradicts existing memory (latest wins)
   - **NOOP**: Fact already well-represented

This is essentially what our `brain.correct()` does, but Mem0 does it for ALL memory, not just corrections.

### 1.3 Memory Types (Four Layers)

| Layer | Scope | Lifetime | Identifier |
|-------|-------|----------|------------|
| Conversation | In-flight messages in current turn | Ephemeral | N/A |
| Session | Short-lived facts for current task | Auto-expires | session_id |
| User | Long-lived knowledge tied to a person | Persistent | user_id |
| Organizational | Shared context across agents/teams | Persistent | org scope |

Multi-user/multi-agent scoping uses `user_id`, `agent_id`, and `run_id` parameters on every operation. Clean isolation without separate databases.

### 1.4 Retrieval Strategy

**Dual retrieval for graph memories:**
1. **Entity-Centric**: Identifies entities in query, finds corresponding nodes, traverses incoming/outgoing edges to build subgraph
2. **Semantic Triplet**: Encodes entire query as dense embedding, matches against all relationship triplets, returns those above relevance threshold

**For vector memories:**
Standard semantic similarity search with configurable limit parameter.

**Retrieval hierarchy**: User memories ranked first, then session notes, then raw history.

**What they DON'T do**: No multi-strategy retrieval with cross-encoder reranking. No hybrid BM25+vector. Their retrieval is actually simpler than it looks.

### 1.5 Conflict Resolution

- Vector memories: LLM decides ADD/UPDATE/DELETE/NOOP based on semantic similarity to existing facts
- Graph memories: Conflict Detector flags overlapping/contradictory nodes/edges, then LLM-powered Update Resolver decides whether to add, merge, invalidate, or skip
- Critical design choice: **Graph conflicts are marked as invalid, NOT deleted** — this preserves temporal reasoning ("the researcher used to prefer X, now prefers Y")
- This is genuinely smart. We should steal this temporal preservation approach.

### 1.6 API Surface

Minimal. ~10 lines to integrate:

```python
from mem0 import Memory
memory = Memory()

# Store
memory.add(messages, user_id="researcher")

# Retrieve
results = memory.search("budget objections", user_id="researcher")

# Get all
all_memories = memory.get_all(user_id="researcher")

# Delete
memory.delete(memory_id)

# History
memory.history(memory_id)
```

Python + JavaScript SDKs. MCP server available.

### 1.7 What Mem0 Does Well

1. **Dead simple API**: 3 methods cover 90% of use cases (add, search, get_all)
2. **Passive extraction**: Developer doesn't need to decide what to remember — the system handles it
3. **Graph + vector hybrid**: Entity relationships captured alongside semantic similarity
4. **Temporal preservation**: Invalid-marking instead of deletion for conflict resolution
5. **Research-backed**: Published paper with LOCOMO benchmark results (+26% over OpenAI memory)
6. **Token efficiency**: 7K tokens average per conversation vs competitors using 600K
7. **Framework agnostic**: Works with any agent framework, no lock-in
8. **LLM-as-judge for memory operations**: Using function-calling to decide ADD/UPDATE/DELETE is elegant

### 1.8 What Mem0 Does NOT Do (Our Opportunities)

1. **No behavioral adaptation**: Mem0 remembers facts but does NOT learn from corrections. If a user edits AI output, Mem0 doesn't extract the behavioral delta. This is our entire moat.
2. **No quality tracking**: No metrics on whether memories actually improve outcomes. No "did this memory help?" feedback loop.
3. **No pattern graduation**: Facts are either stored or not. There's no "this pattern appeared 5 times, promote it to a rule" mechanism.
4. **No diff-based learning**: Mem0 learns from conversations. We learn from the DIFFERENCE between AI drafts and user edits. Fundamentally different signal.
5. **No skill learning**: Can't learn new behaviors or procedures, only facts.
6. **Retrieval scoring is opaque**: You can't tune weighting between recency, semantic similarity, and confidence.
7. **No self-improvement loop**: Memories don't compound into behavioral rules. They're just retrieved facts.
8. **No manifest/proof system**: No way to demonstrate "this brain has learned X patterns with Y accuracy."

### 1.9 Pricing & Business Model

| Tier | Price | Key Features |
|------|-------|-------------|
| Hobby | Free | 10K memories, 1K retrieval/month |
| Starter | $19/month | 50K memories |
| Pro | $249/month | Unlimited, graph memory, analytics, HIPAA |
| Enterprise | Custom | On-prem, SOC 2, BYOK, SLA |

Revenue model: Usage-based (memory operations), not seat-based. The open source version is vector-only. Graph features are paywalled at $249/month.

---

## PART 2: LETTA (formerly MemGPT)

### 2.1 Architecture: Tiered Memory

Letta treats memory like a computer's memory hierarchy:

| Tier | Analogy | Location | Size | Access |
|------|---------|----------|------|--------|
| Core Memory | RAM | In context window | Small (2K chars/block) | Always present |
| Recall Memory | Disk cache | Searchable DB | Unbounded | Tool call to search |
| Archival Memory | Cold storage | Vector DB | Unbounded | Tool call to search |

**Core Memory** consists of labeled blocks (default: "persona" + "human") that are compiled into the system prompt at every agent step. The agent can modify these blocks directly using memory tools. This is the key innovation — the agent's identity and user knowledge live in mutable context.

**Recall Memory** logs all conversational history. Searchable by text and date. The agent queries it via `conversation_search()` and `conversation_search_date()`.

**Archival Memory** is a vector DB table for long-running memories and external data. Accessed via `archival_memory_insert()` and `archival_memory_search()`.

### 2.2 Learning SDK

The learning SDK is a **drop-in wrapper** that adds memory to ANY LLM call:

```python
from letta_learning import learning

with learning(agent="my_agent", memory=["customer", "preferences"]):
    response = client.chat.completions.create(...)
```

**Three-phase operation:**
1. **Interception**: Patches HTTP APIs (OpenAI, Anthropic, Gemini) or transport layers (Claude Agent SDK)
2. **Capture**: Extracts user/assistant messages, sends to Letta's memory backend
3. **Retrieval & Injection**: Before each LLM call, semantically searches past conversations and injects into prompt

Supports: OpenAI, Anthropic, Claude Agent SDK, Gemini, Vercel AI SDK, CrewAI, LangChain.

This is essentially a man-in-the-middle proxy for LLM calls that adds memory transparently. Very clever distribution mechanism.

### 2.3 Memory Management: Agent Self-Editing

This is Letta's core differentiator. The LLM itself decides what to remember using tool calls during inference:

**Memory tools available to the agent:**
- `memory_replace(label, old_str, new_str)`: Edit a core memory block
- `memory_insert(label, content)`: Add to a core memory block
- `memory_rethink(label, new_value)`: Replace entire block content
- `memory_finish_edits()`: Signal editing complete
- `archival_memory_insert(content)`: Store in long-term
- `archival_memory_search(query)`: Search long-term
- `conversation_search(query)`: Search chat history
- `conversation_search_date(start, end)`: Search by date range

At every agent step: blocks compile into system prompt -> agent reasons -> if agent calls memory tool -> block updated in DB -> next iteration gets fresh system prompt with updated memory.

### 2.4 Agent State Persistence

Agents persist across sessions via:
- Core memory blocks stored in DB
- Archival memory in vector DB
- Recall memory (full conversation log)
- Agent metadata (model, tools, settings)

Each agent has a unique ID. State survives server restarts. The agent is a long-lived entity, not a per-session construct.

### 2.5 Context Repositories (New, 2026)

Git-backed memory for coding agents:
- Every memory change automatically versioned with commit messages
- Multiple subagents work in isolated git worktrees simultaneously
- Changes merge back through standard git conflict resolution
- Hierarchical memory structure with progressive disclosure
- `system/` directory for permanently-loaded context
- Background "sleep-time" reflection that periodically reviews conversation history

This is genuinely innovative. Memory treated as a codebase with version control.

### 2.6 Skill Learning

Two-stage process:
1. **Reflection**: Evaluates agent trajectory — did it solve the task? Sound reasoning? Edge cases? Repetitive patterns?
2. **Creation**: Learning agent generates skills as markdown files containing "potential approaches, common pitfalls, verification strategies"

**Results on Terminal Bench 2.0:**
- +21.1% relative improvement with trajectory-only skills
- +36.8% relative improvement with feedback-enriched skills
- -15.7% cost reduction (fewer tokens needed)
- -10.4% fewer tool calls

Skills stored as `.md` files. Portable across agents. Version controlled.

### 2.7 Self-Editing

Yes, agents can modify their own instructions and personality:
- The "persona" core memory block is the agent's self-concept
- Agent can call `memory_replace("persona", old, new)` to evolve its identity
- System instructions (immutable) vs persona memory (mutable) creates stable-but-adaptive behavior
- This enables personality drift — which is both a feature and a risk

### 2.8 What Letta Does Well

1. **Agent-managed memory**: The LLM itself decides what to remember, creating contextually intelligent curation
2. **Three-tier hierarchy**: Elegant separation of hot (core), warm (recall), and cold (archival) memory
3. **Self-editing personality**: Agents can evolve their behavior over time
4. **Context repositories**: Git-backed memory with version control is brilliant
5. **Skill learning from trajectories**: Agents learn procedures, not just facts
6. **Sleep-time compute**: Background consolidation between active sessions
7. **Token-space learning theory**: Compelling argument that context updates > weight updates
8. **Learning SDK as trojan horse**: Wrap any LLM call with memory in one line

### 2.9 What Letta Does NOT Do (Our Opportunities)

1. **No correction tracking**: Letta learns from trajectories and self-reflection, but NOT from user edits/corrections. No diff-based signal.
2. **LLM-dependent quality**: Memory curation quality depends entirely on the underlying model's judgment. Bad model = bad memory management.
3. **No quality verification**: No metrics proving memories improve outcomes. No compound quality score.
4. **No pattern graduation**: No mechanism to promote observations to rules based on frequency/confidence.
5. **Runtime lock-in**: You must use Letta's agent runtime. Can't bolt it onto existing frameworks easily (learning SDK partially addresses this).
6. **No marketplace/brain trading**: No concept of packaging learned behavior for others to use.
7. **No organizational learning**: Each agent learns in isolation. No cross-agent knowledge transfer mechanism.
8. **Expensive inference**: Agent self-editing consumes tokens at every step for memory management.
9. **No manifest/proof**: No machine-readable proof of what an agent has learned.

### 2.10 Pricing & Business Model

| Tier | Price | Key Features |
|------|-------|-------------|
| Personal | Free-ish | Usage quotas, individual use |
| Cloud | $20-200/month | Managed hosting, API access |
| Self-hosted | Free | Full open source |
| Enterprise | Custom | Undisclosed |

Revenue: $1.4M as of June 2025 with 13-person team.

---

## PART 3: BUSINESS MODEL & GROWTH COMPARISON

### 3.1 Origin Stories

| | Mem0 | Letta |
|---|------|-------|
| Founded | January 2024 | September 2024 (stealth exit) |
| Founders | Taranjeet Singh (7th startup, ex-Khatabook PM) + Deshraj Yadav (ex-Tesla Autopilot AI) | Charles Packer + Sarah Wooders (Berkeley PhD students, Sky Lab) |
| Origin | Pivoted from Embedchain (RAG framework, 2M+ downloads) after meditation app users complained "it doesn't remember" | Academic paper MemGPT went viral, spun out from Berkeley's Sky Computing Lab (same lab as Databricks, Anyscale) |
| Accelerator | Y Combinator S24 | Berkeley Sky Lab lineage (Ion Stoica advisor) |

### 3.2 Funding

| | Mem0 | Letta |
|---|------|-------|
| Seed | $3.9M (Kindred Ventures) | $10M (Felicis) |
| Series A | $20M (Basis Set Ventures) | Not yet raised |
| Total | $24M | $10M |
| Valuation | Undisclosed | $70M (at seed) |
| Notable Angels | Dharmesh Shah (HubSpot), CEOs of Datadog, Supabase, PostHog, ex-GitHub, W&B | Jeff Dean (Google DeepMind), Clem Delangue (HuggingFace), CEOs of Runway, MotherDuck, dbt Labs |

### 3.3 Growth & Distribution

| | Mem0 | Letta |
|---|------|-------|
| GitHub Stars | ~48K (as of March 2026) | ~13K (as of March 2026) |
| PyPI Downloads | 13M+ total | Not disclosed |
| API Calls | 186M/quarter (Q3 2025), 30% MoM growth | Not disclosed |
| Revenue | Not disclosed | $1.4M (June 2025) |
| Team Size | Not disclosed | 13 people |
| Community | Large Discord, extensive integrations | Forum + Discord, academic credibility |

### 3.4 Distribution Strategies

**Mem0's GTM (what worked):**
- Open source first, massive GitHub star accumulation
- Dead simple API (3 methods) lowered barrier to zero
- Chrome extension for ChatGPT/Perplexity/Claude — brilliant distribution
- Integrations with every framework (LangChain, CrewAI, AutoGen, Google ADK)
- Research paper for credibility
- YC network for enterprise introductions
- Usage-based pricing aligned with value

**Letta's GTM (what worked):**
- Viral academic paper gave instant credibility
- Berkeley brand (same lab as Databricks) attracted top angels
- "Letta Code" CLI tool — install and use immediately
- Learning SDK as trojan horse — wraps existing LLM calls
- DeepLearning.AI course for education/awareness
- Model leaderboard drives traffic

### 3.5 What to Steal from Their GTM

From **Mem0**:
1. **Chrome extension pattern**: A browser extension that captures corrections across ChatGPT/Claude/Perplexity would be a phenomenal distribution vector for our brain
2. **Framework integration blitz**: Be everywhere. LangChain, CrewAI, AutoGen, Google ADK, Semantic Kernel — every integration is a distribution channel
3. **Research paper**: Publish our correction-to-rule pipeline results on arXiv. Academic credibility matters.
4. **Usage-based pricing**: Align cost with value delivered, not seats

From **Letta**:
1. **Learning SDK wrapper pattern**: Their `learning()` context manager that wraps any LLM call is genius distribution. We should build the same for our correction tracking
2. **CLI-first onboarding**: `npx @our-sdk` -> running in 30 seconds
3. **Model leaderboard**: "Which models learn best from corrections?" — drives traffic and establishes authority
4. **DeepLearning.AI course equivalent**: Educational content that teaches the concept while selling the tool

---

## PART 4: COMPARISON WITH OUR MODEL (GRADATA)

### 4.1 Side-by-Side Business Model Comparison

| Dimension | Mem0 | Letta | Us (Gradata) |
|-----------|------|-------|---------------|
| **Open Source** | Vector memory (graph paywalled) | Full agent runtime | Full SDK, zero deps |
| **Cloud Tier** | $19-249/month | $20-200/month | Freemium (planned) |
| **Enterprise** | SOC 2, HIPAA, on-prem | Custom | Not yet |
| **Revenue Model** | Usage-based (memory ops) | Cloud hosting fees | Marketplace 80/20 split |
| **Distribution** | PyPI + Chrome ext + integrations | CLI + Learning SDK | MCP server (planned) |
| **Moat** | Network effects (more users = better extraction) | Academic credibility + runtime lock-in | Correction tracking + graduation + quality proof |
| **Current Revenue** | Not disclosed (186M API calls/qtr) | $1.4M (June 2025) | $0 |
| **Funding** | $24M | $10M | $0 |
| **Team** | Unknown | 13 | 1 (the researcher) |

### 4.2 Harsh Assessment of Our Model

**Where we are STRONGER:**

1. **Unique signal source**: Neither Mem0 nor Letta learns from the diff between AI draft and user edit. This is genuinely novel and a real moat. No one else is doing correction-to-rule graduation.
2. **Quality proof**: brain.manifest.json that proves compound learning over time. Neither competitor can show "this brain improved from X to Y accuracy over N sessions."
3. **Zero dependency design**: Our SDK works with SQLite locally. Mem0 needs a vector DB. Letta needs its runtime. We win on simplicity.
4. **Marketplace vision**: Brain-as-a-product is novel. Neither competitor has a marketplace concept.
5. **BYOK model**: Lower cost floor than either competitor's hosted offerings.

**Where we are WEAKER (be honest):**

1. **No memory layer at all**: Mem0 has sophisticated fact extraction + graph memory + vector search. We have FTS5 keyword search and planned sqlite-vec. We're behind on basic retrieval.
2. **No passive memory extraction**: When we process a conversation, we only learn from corrections. We don't extract facts, preferences, or entity relationships from normal conversation. Mem0 does this automatically.
3. **No framework integrations**: Mem0 works with LangChain, CrewAI, AutoGen, ADK, etc. Letta has a learning SDK that wraps any LLM call. We have... an MCP server. That's one integration point.
4. **No research validation**: Mem0 has a published paper with benchmarks. Letta has the MemGPT paper. We have nothing published.
5. **No community**: 48K stars (Mem0) vs 13K (Letta) vs... our private repo. Zero external validation.
6. **Marketplace is premature**: Letta's stress test finding ("marketplace is wrong first product") applies to us too. No one will rent a brain they can't verify.
7. **Single-person risk**: Both competitors have funded teams. We have the researcher. Bus factor = 1.
8. **No enterprise story**: No SOC 2, no HIPAA, no on-prem deployment guides. Enterprise buyers won't touch us.

**Mistakes we're making that they've already figured out:**

1. **Building marketplace before memory**: Mem0 proved that great memory is the product. Get retrieval right FIRST. Our marketplace vision is Phase 4 material being discussed in Phase 1.
2. **Not publishing**: Both competitors used research papers as distribution. We should write up the correction-graduation pipeline NOW.
3. **Not wrapping other frameworks**: Letta's learning SDK proves you can add memory to anything with a context manager. We should build `with brain.observe():` that wraps any LLM call and captures corrections.
4. **Ignoring graph memory**: Mem0's entity-relationship extraction is genuinely useful. "the researcher works at Sprites" -> "Sprites is an AI company" -> multi-hop reasoning. We store flat facts.

### 4.3 Pricing Model Comparison

| Feature | Mem0 Hobby (Free) | Mem0 Pro ($249) | Letta Cloud ($200) | Us (Planned Free) | Us (Planned Cloud) |
|---------|-------------------|-----------------|--------------------|--------------------|---------------------|
| Memory storage | 10K memories | Unlimited | Unlimited | Unlimited (local) | Unlimited |
| Graph memory | No | Yes | No (different arch) | No | Planned |
| Correction tracking | No | No | No | Yes | Yes |
| Quality metrics | No | Analytics | No | Yes | Dashboard |
| Brain export | N/A | N/A | N/A | Yes | Yes |
| Marketplace | N/A | N/A | N/A | No | Yes |

Our free tier is actually more generous than Mem0's because it's local. That's a real advantage. But "unlimited local" only matters if the local experience is good.

---

## PART 5: WHAT TO STEAL — SPECIFIC RECOMMENDATIONS

### 5.1 From Mem0: Passive Fact Extraction Pipeline

**What**: Mem0's two-phase extract-then-update pipeline that automatically identifies what to remember from any conversation.

**How to implement**: Add a `brain.observe(messages)` method that:
1. Sends conversation to LLM with fact extraction prompt
2. For each extracted fact, searches existing facts via FTS5/sqlite-vec
3. LLM decides ADD/UPDATE/DELETE/NOOP
4. Stores as events in our event-sourced system

**Why**: We currently only learn from corrections. Adding passive fact extraction means we capture ALL useful information, not just behavioral deltas. The two systems (fact memory + correction learning) are complementary.

**Effort**: Medium. We already have `_fact_extractor.py`. Extend it with the update-phase logic.

### 5.2 From Mem0: Temporal Conflict Preservation

**What**: Mark conflicting facts as invalid instead of deleting them, preserving temporal reasoning.

**How to implement**: Add an `invalidated_at` timestamp and `superseded_by` foreign key to our facts table. When a new fact contradicts an old one, the old fact is marked invalid but retained.

**Why**: This enables "the researcher used to prefer X but now prefers Y" reasoning, which is critical for behavioral adaptation that evolves over time.

**Effort**: Small. Schema change + query filter.

### 5.3 From Mem0: Memory Scoping with Composite Keys

**What**: Mem0's `user_id` + `agent_id` + `run_id` scoping system.

**How to implement**: Our events already have session context. Extend with explicit `user_id` and `agent_id` fields. This is critical for marketplace — a brain serving multiple users needs isolation.

**Effort**: Small. Already partially implemented via session tracking.

### 5.4 From Letta: Agent Self-Editing Core Memory

**What**: Mutable context blocks that the agent reads/writes during inference.

**How to implement**: Define labeled memory blocks (persona, user, task) that compile into the system prompt. Expose `memory_replace()`, `memory_insert()`, `memory_rethink()` as tools the agent can call. Persist blocks in system.db.

**Why**: Our correction system is passive (user edits, we learn). Adding active self-editing means the agent can also update its own understanding during a conversation, not just between sessions.

**Effort**: Medium. New module `_core_memory.py` with block CRUD + system prompt compiler.

### 5.5 From Letta: Learning SDK Wrapper Pattern

**What**: A context manager that wraps any LLM call and transparently adds memory.

**How to implement**:
```python
from gradata import brain_context

with brain_context(brain="./my-brain", user="researcher"):
    # Any LLM call inside here gets:
    # 1. Relevant memories injected into context
    # 2. Conversation captured for fact extraction
    # 3. If user edits response, correction tracked
    response = openai.chat.completions.create(...)
```

Patch HTTP clients (OpenAI, Anthropic) to intercept requests/responses. Extract messages. Inject memory context. Capture for learning.

**Why**: This is the single best distribution mechanism either competitor has built. One line of code to add behavioral adaptation to ANY agent.

**Effort**: Large. Requires HTTP interception layer. But highest ROI of any feature.

### 5.6 From Letta: Git-Backed Memory Versioning

**What**: Context repositories with git-based versioning of memory changes.

**How to implement**: Our brain already IS a directory. Add git init on `Brain.init()`. Auto-commit on memory changes with descriptive messages. Enable diffing memory state across time.

**Why**: Version control for memory is elegant and solves several problems: rollback bad learning, audit trail, branching for experimentation, merging multiple agents' learnings.

**Effort**: Medium. Git operations are simple. The hard part is meaningful commit messages.

### 5.7 From Letta: Sleep-Time Compute / Background Reflection

**What**: Background process that periodically reviews conversation history and consolidates important information.

**How to implement**: We already have the concept (see AutoDream consolidation pattern in memory). Implement as a post-session hook:
1. After session ends, background agent reviews all corrections and conversations
2. Identifies patterns that haven't been graduated yet
3. Proposes rule promotions
4. Consolidates redundant facts
5. Updates brain.manifest.json

**Why**: This is how human learning works — consolidation during downtime. Our correction pipeline currently only fires during active sessions.

**Effort**: Medium. We have the pieces (fact extractor, pattern extractor, rule engine). Need orchestration.

### 5.8 From Letta: Skill Learning from Trajectories

**What**: Agents reflect on task trajectories and generate reusable skill documents.

**How to implement**: After a successful task completion:
1. Reflection agent analyzes the trajectory
2. Extracts "what worked, what failed, common pitfalls"
3. Stores as a skill markdown file in the brain
4. Future tasks retrieve relevant skills via semantic search

**Why**: We currently learn behavioral preferences (how to write emails). Adding skill learning means we also capture procedural knowledge (how to research a prospect, how to prepare for a demo).

**Effort**: Medium. New module. Leverages existing pattern extraction.

### 5.9 NEW IDEA (Neither Has This): Correction-Aware Memory

**What**: Memory entries that track their own accuracy — memories that know how often they've been validated vs corrected.

**How to implement**: Each memory/fact/rule gets:
- `applied_count`: How many times this memory was used in context
- `correction_count`: How many times output using this memory was corrected
- `accuracy_score`: 1 - (correction_count / applied_count)
- Auto-demote memories with low accuracy scores

**Why**: Neither Mem0 nor Letta tracks whether their memories actually help. We can. This is the quality proof that makes brain.manifest.json meaningful.

**Effort**: Medium. Requires tracking which memories were in context when corrections occur.

---

## PART 6: PRIORITY RANKING

Based on impact, effort, and competitive differentiation:

| Priority | Feature | Source | Impact | Effort | Why First |
|----------|---------|--------|--------|--------|-----------|
| 1 | Learning SDK wrapper (`brain_context()`) | Letta | Extreme | Large | Distribution is everything. One-line integration wins. |
| 2 | Passive fact extraction pipeline | Mem0 | High | Medium | We're blind to non-correction information. |
| 3 | Correction-aware memory scoring | Novel | High | Medium | This IS our moat. Neither competitor has it. |
| 4 | Temporal conflict preservation | Mem0 | Medium | Small | Quick win, elegant design. |
| 5 | Sleep-time background reflection | Letta | High | Medium | Compounds all other learning. |
| 6 | Git-backed memory versioning | Letta | Medium | Medium | Natural fit — brain is already a directory. |
| 7 | Memory scoping (user_id/agent_id) | Mem0 | Medium | Small | Required for marketplace. |
| 8 | Core memory blocks (self-editing) | Letta | Medium | Medium | Enables active adaptation, not just passive. |
| 9 | Skill learning from trajectories | Letta | Medium | Medium | Extends learning beyond style to procedure. |
| 10 | Graph memory / entity relationships | Mem0 | Medium | Large | Nice-to-have, not core to our moat. |

---

## PART 7: KEY TAKEAWAYS

1. **Mem0 is a memory layer. Letta is an agent runtime. We are a behavioral adaptation engine.** These are three different products. Our moat is NOT memory — it's learning from corrections and graduating patterns into rules with quality proof.

2. **Both competitors ignore the correction signal.** Neither Mem0 nor Letta extracts behavioral deltas from user edits. This is our unique advantage. Protect it.

3. **We need passive memory extraction yesterday.** Only learning from corrections means we miss 90% of useful information from conversations. Mem0's extraction pipeline should be adapted immediately.

4. **Distribution > features.** Mem0 has 48K stars because `memory.add()` is dead simple. Letta's learning SDK wraps any LLM call in one line. Our MCP server is not enough. Build the wrapper.

5. **Publish or perish.** Both competitors leveraged research papers for credibility and distribution. We need to write up the correction-graduation pipeline and publish it.

6. **Marketplace is Phase 4, not Phase 1.** Both competitors are still proving their core memory product. We should focus on making the SDK undeniably good before building marketplace infrastructure.

7. **Neither competitor has quality proof.** No one can show "this brain learned X patterns and improved accuracy by Y%." brain.manifest.json with correction-aware memory scoring would be genuinely novel.

---

Sources:
- [Mem0 Research Paper](https://arxiv.org/abs/2504.19413)
- [Mem0 Graph Memory Docs](https://docs.mem0.ai/open-source/features/graph-memory)
- [Mem0 Memory Types](https://docs.mem0.ai/core-concepts/memory-types)
- [Mem0 Series A Announcement](https://techcrunch.com/2025/10/28/mem0-raises-24m-from-yc-peak-xv-and-basis-set-to-build-the-memory-layer-for-ai-apps/)
- [Mem0 Pricing](https://mem0.ai/pricing)
- [Mem0 Architecture Deep Dive (Medium)](https://medium.com/@parthshr370/from-chat-history-to-ai-memory-a-better-way-to-build-intelligent-agents-f30116b0c124)
- [Letta MemGPT Concepts](https://docs.letta.com/concepts/memgpt/)
- [Letta Memory Management](https://docs.letta.com/advanced/memory-management/)
- [Letta Learning SDK](https://github.com/letta-ai/learning-sdk)
- [Letta Skill Learning Blog](https://www.letta.com/blog/skill-learning)
- [Letta Context Repositories Blog](https://www.letta.com/blog/context-repositories)
- [Letta Continual Learning Blog](https://www.letta.com/blog/continual-learning)
- [Letta Founding / TechCrunch](https://techcrunch.com/2024/09/23/letta-one-of-uc-berkeleys-most-anticipated-ai-startups-has-just-come-out-of-stealth/)
- [Letta Revenue Data](https://getlatka.com/companies/letta.com)
- [Mem0 vs Letta Comparison](https://vectorize.io/articles/mem0-vs-letta)
- [AI Agent Memory Systems 2026 Comparison](https://yogeshyadav.medium.com/ai-agent-memory-systems-in-2026-mem0-zep-hindsight-memvid-and-everything-in-between-compared-96e35b818da8)
- [Mem0 Graph Memory DeepWiki](https://deepwiki.com/mem0ai/mem0/4-graph-memory)
