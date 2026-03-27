# Domain-Agnostic Core Patterns: How Production Frameworks Do It

**Researched:** 2026-03-24
**Confidence:** MEDIUM-HIGH (primary sources verified for 6/7 frameworks)
**Purpose:** Inform how Gradata separates generic engine from domain-specific behaviors

---

## Executive Summary

Every production agent framework solves the domain-agnostic problem the same way at the structural level: **the core engine is a typed execution loop that knows nothing about domains; domain knowledge enters through injection points.** The injection mechanisms differ, but converge on three patterns:

1. **Declarative config files** (CrewAI, Google ADK) -- domain vocabulary lives in YAML/JSON, core reads it at runtime
2. **Typed schemas as contracts** (PydanticAI, Atomic Agents, LangGraph) -- domain entities are Pydantic/TypedDict models, core is generic over type parameters
3. **Plugin registries** (Semantic Kernel, VS Code, WordPress) -- domain capabilities register into named slots, core discovers and dispatches

The "prospect vs candidate vs customer" problem is universally solved by **not hardcoding entity types into the core.** Every framework treats entities as opaque typed data that flows through a generic pipeline. The domain layer defines what "prospect" means; the core layer only knows it's a dict/model with a schema.

**Key finding for Gradata:** Our current `_tag_taxonomy.py` and `_config.py` hardcode sales concepts (`prospect`, `angle`, `persona`, `framework`) directly into the SDK core. This is the #1 thing that prevents domain-agnosticism. Every framework studied avoids this.

---

## Framework-by-Framework Analysis

### 1. Google ADK (Agent Development Kit)

**Source:** [ADK Docs](https://google.github.io/adk-docs/), [Agent Config](https://google.github.io/adk-docs/agents/config/)

**How domain config is stored:**
YAML files per agent. Each agent definition is a standalone YAML document:

```yaml
name: sales_agent
model: gemini-2.5-flash
description: "Handles outbound prospecting"
instruction: "You are a sales development representative for {company}..."
tools:
  - name: crm_lookup
  - name: email_sender
sub_agents:
  - config_path: research_agent.yaml
  - config_path: qualifier_agent.yaml
```

**How the core stays generic:**
- Core runtime is an event-driven loop that processes `Event` objects
- Agents are class instances (`LlmAgent`, `SequentialAgent`, `ParallelAgent`, `LoopAgent`)
- Domain enters ONLY through `instruction` strings and `tools` lists
- The runtime doesn't know or care what domain the agent operates in
- `{var}` placeholders in instructions are resolved from session state at runtime

**How taxonomy is made configurable:**
- No built-in taxonomy system. Tools define their own input/output schemas
- Domain vocabulary lives entirely in instruction text and tool parameter descriptions
- Agent hierarchies (sub_agents) provide domain decomposition

**Entity problem:**
- ADK has no concept of "entity." Everything is a tool parameter or session state value
- A sales agent's "prospect" and a recruiting agent's "candidate" are both just dicts passed to tools

**Confidence:** HIGH (verified against official docs)

---

### 2. LangGraph / LangChain

**Source:** [LangGraph Docs](https://docs.langchain.com/oss/python/langgraph/graph-api), [LangChain Blog](https://blog.langchain.com/building-langgraph/)

**How domain config is stored:**
Python TypedDict or Pydantic BaseModel defines the state schema. No YAML -- it's code-first:

```python
class SalesState(TypedDict):
    leads: list[Lead]
    current_stage: str
    messages: Annotated[list[BaseMessage], add_messages]

class RecruitingState(TypedDict):
    candidates: list[Candidate]
    pipeline_stage: str
    messages: Annotated[list[BaseMessage], add_messages]
```

**How the core stays generic:**
- `StateGraph` is generic over any TypedDict/BaseModel
- The graph runtime manages nodes, edges, and state transitions
- It has zero knowledge of what's in the state -- just that it's a typed dict
- `context_schema` (new in 2025) separates runtime dependencies from state

**How taxonomy is made configurable:**
- No taxonomy system. The state schema IS the domain vocabulary
- Each graph defines its own state type, which implicitly defines the domain language
- Configurable parameters pass through `config.configurable` dict at runtime

**Entity problem:**
- Entities are whatever your state schema says they are
- `StateGraph[SalesState]` vs `StateGraph[RecruitingState]` -- same engine, different types
- The graph never references "prospect" or "candidate" -- it references `state["leads"]` or `state["candidates"]`

**Key pattern:** `Annotated[list[X], reducer_fn]` -- state fields declare their own merge strategy. This is how multi-step pipelines accumulate results without the core knowing the domain.

**Confidence:** HIGH (verified against official docs + GitHub)

---

### 3. CrewAI

**Source:** [CrewAI Docs](https://docs.crewai.com/en/concepts/agents), [YAML Config](https://deepwiki.com/crewAIInc/crewAI/8.2-yaml-configuration)

**How domain config is stored:**
Two YAML files in `config/` directory:

```yaml
# config/agents.yaml
sales_researcher:
  role: "Senior Sales Researcher for {industry}"
  goal: "Find and qualify prospects matching ICP"
  backstory: "Expert at identifying buying signals..."
  tools:
    - linkedin_scraper
    - company_enricher

# config/tasks.yaml
research_prospect:
  description: "Research {prospect_name} and find pain points related to {product}..."
  expected_output: "Structured prospect profile with qualification score"
  agent: sales_researcher
  context:
    - enrich_company  # task dependency
```

**How the core stays generic:**
- `@CrewBase` decorator auto-loads YAML and maps to Python objects
- The Crew orchestrator manages task delegation, doesn't know about sales/recruiting/etc
- `{variable}` interpolation injects domain context from `main.py`
- Same orchestration loop for any domain -- only YAML content changes

**How taxonomy is made configurable:**
- No formal taxonomy. Role + goal + backstory in YAML define domain vocabulary
- Tools are registered by name and discovered at runtime
- Delegation happens based on role descriptions, not hardcoded categories

**Entity problem:**
- Entities are implicit in task descriptions and tool outputs
- A "prospect" crew and a "candidate" crew use the same CrewAI engine
- Entity types are defined by the tools and output schemas, not by the framework

**Confidence:** HIGH (verified against official docs)

---

### 4. PydanticAI

**Source:** [PydanticAI Docs](https://ai.pydantic.dev/), [Agent API](https://ai.pydantic.dev/agent/)

**How domain config is stored:**
Python classes with Pydantic models. Fully typed, no YAML:

```python
# Domain-specific dependencies
@dataclass
class SalesDeps:
    crm: CRMClient
    enrichment: EnrichmentAPI
    prospect_db: ProspectDatabase

# Domain-specific output
class ProspectProfile(BaseModel):
    name: str
    company: str
    qualification_score: float
    pain_points: list[str]

# Generic agent typed over domain
agent = Agent[SalesDeps, ProspectProfile](
    model='claude-sonnet-4-20250514',
    system_prompt='You are a sales research assistant...',
)
```

**How the core stays generic:**
- `Agent[DepsType, OutputType]` is generic over two type parameters
- The runtime manages tool calling, retries, and validation
- `RunContext[DepsType]` flows through every tool function
- Domain logic lives in tools and system prompts, not the agent runtime

**How taxonomy is made configurable:**
- Type parameters ARE the configuration
- `Agent[SalesDeps, ProspectProfile]` vs `Agent[RecruitingDeps, CandidateProfile]`
- Same engine, different types, validated at definition time

**Entity problem:**
- Pydantic models define entity schemas explicitly
- `ProspectProfile` and `CandidateProfile` are both just BaseModel subclasses
- The agent runtime doesn't know or care which one it's dealing with

**Key pattern:** Dependency injection via `RunContext` -- domain services (CRM client, database, etc.) are injected at runtime, not imported at module level. This is the cleanest separation found across all frameworks.

**Confidence:** HIGH (verified against official docs)

---

### 5. Semantic Kernel (Microsoft)

**Source:** [SK Plugins](https://learn.microsoft.com/en-us/semantic-kernel/concepts/plugins/), [Agent Skills Blog](https://devblogs.microsoft.com/semantic-kernel/give-your-agents-domain-expertise-with-agent-skills-in-microsoft-agent-framework/)

**How domain config is stored:**
Plugins are Python/C#/Java classes with decorated methods. Skills are markdown files with YAML frontmatter:

```markdown
---
name: sales-prospecting
description: Qualifies leads and generates outreach emails
license: MIT
---

## Instructions
1. Research the prospect using the CRM tool
2. Score against ICP criteria: company size > 50, industry in [SaaS, fintech]...
```

**How the core stays generic:**
- The Kernel is a service container: `kernel.add_plugin(SalesPlugin(), "Sales")`
- LLM uses function calling to invoke plugin methods
- Each Agent gets its own Kernel instance with different plugins
- The Kernel itself has zero domain knowledge -- it just dispatches function calls

**How taxonomy is made configurable:**
- Plugin names and function descriptions are the taxonomy
- `@kernel_function` decorator + `@Description()` annotation = semantic metadata
- No closed vocabulary -- the LLM reads descriptions and picks functions

**Entity problem:**
- Plugin parameters define entity schemas
- `get_prospect(id: int)` vs `get_candidate(id: int)` -- same dispatch mechanism
- The Kernel doesn't have a "prospect" concept; the SalesPlugin does

**Key pattern: Progressive skill disclosure.** Skills advertise name + description (~100 tokens). Full instructions load only on `load_skill` call (<5,000 tokens). Resources load on demand. This keeps context windows lean while providing deep domain knowledge.

**Confidence:** HIGH (verified against official docs + blog post)

---

### 6. AutoGen (Microsoft Agent Framework)

**Source:** [AutoGen GitHub](https://github.com/microsoft/autogen), [Agent Framework Overview](https://learn.microsoft.com/en-us/agent-framework/overview/)

**How domain config is stored:**
Python class instantiation with system messages:

```python
sales_agent = AssistantAgent(
    name="SalesRep",
    system_message="You are a sales development rep. Qualify leads by...",
    llm_config={"model": "gpt-4o"},
)

recruiter_agent = AssistantAgent(
    name="Recruiter",
    system_message="You are a technical recruiter. Screen candidates by...",
    llm_config={"model": "gpt-4o"},
)
```

**How the core stays generic:**
- Three-layer architecture: Core (message passing) -> AgentChat (multi-agent patterns) -> Extensions
- Core layer handles async event-driven message routing
- AgentChat provides team patterns (RoundRobin, Selector, Swarm) that are domain-agnostic
- Domain enters through system_message and tools only

**How taxonomy is made configurable:**
- No taxonomy system. Teams are composed programmatically
- Agent names and system messages define domain roles
- Shared group chat context means agents can reference each other's outputs

**Entity problem:**
- Same as ADK -- entities are opaque data in messages
- The framework never references specific entity types

**Confidence:** MEDIUM (primarily from docs/GitHub, limited code-level verification)

---

### 7. Atomic Agents

**Source:** [Medium Analysis](https://medium.com/@mingyang.heaven/atomic-agents-framework-capability-analysis-report-60fa36d7ed47), [GitHub](https://github.com/BrainBlend-AI/atomic-agents)

**How domain config is stored:**
Pydantic input/output schemas per agent:

```python
class ProspectInput(BaseIOSchema):
    company_name: str
    industry: str

class QualifiedProspect(BaseIOSchema):
    company_name: str
    score: float
    pain_points: list[str]

qualifier = AtomicAgent(
    input_schema=ProspectInput,
    output_schema=QualifiedProspect,
    system_prompt="You are a lead qualification specialist...",
)
```

**How the core stays generic:**
- Every agent is `AtomicAgent(input_schema, output_schema, system_prompt)`
- Pipeline composition: `AgentA.output_schema == AgentB.input_schema` means compatible
- Incompatible schemas fail at DEFINITION time, not runtime
- The core only knows about BaseIOSchema -- never about specific domain models

**Key pattern: Schema chaining as type-safe composition.** If two agents have matching output->input schemas, they compose. If not, they don't. The framework enforces this at definition time. This is the most rigorous domain-agnostic pattern found.

**Confidence:** MEDIUM (limited official docs, verified via GitHub source)

---

## Cross-Cutting: Event-Sourced Systems

### How CQRS/ES Handles Multi-Domain Schemas

**Source:** [Martin Fowler CQRS](https://martinfowler.com/bliki/CQRS.html), [Axon Framework](https://docs.axoniq.io/)

**Pattern: Bounded Contexts with Shared Event Bus**

```
Context A (Sales)          Context B (Recruiting)
  - ProspectCreated          - CandidateCreated
  - DealStageChanged         - InterviewScheduled
  - ProposalSent             - OfferExtended

         |                          |
         v                          v
    ┌──────────────────────────────────┐
    │     Generic Event Store          │
    │  (append-only, schema-free)      │
    │  Each event has: type, data,     │
    │  timestamp, aggregate_id,        │
    │  context_name                    │
    └──────────────────────────────────┘
```

**Key insights for Gradata:**

1. **Events are typed but the store is generic.** The event store doesn't know what `ProspectCreated` means. It stores `{type: "ProspectCreated", data: {...}, context: "sales"}`. This is exactly what `_events.py` should do -- but currently our event types are hardcoded.

2. **Bounded contexts own their own schemas.** Axon Framework uses `context` property to separate domains. Each context has its own event types, command handlers, and read models. The infrastructure (event bus, command bus, query bus) is shared.

3. **Multi-tenancy via context isolation.** Axon Server EE creates separate storage per context. Each context gets its own event stream, its own projections, its own aggregate roots. The server infrastructure is shared; the data is isolated.

**Direct mapping to Gradata:**
| ES Concept | Gradata Equivalent |
|-----------|----------------------|
| Bounded Context | Domain package (e.g., `gradata-sales`) |
| Event Type | `event_type` in `_events.py` |
| Aggregate Root | Brain instance |
| Event Store | `system.db` events table |
| Read Model | Compiled context / query results |
| Context name | Domain identifier in config |

---

## Cross-Cutting: Plugin Architectures

### VS Code Extension Model

**Source:** [VS Code Extension Host](https://code.visualstudio.com/api/advanced-topics/extension-host)

**Pattern: Process-Isolated Plugin Host**

```
┌─────────────────┐     IPC      ┌────────────────────┐
│   Core Editor    │◄───────────►│   Extension Host    │
│ (domain-agnostic)│   (JSON)    │ (runs all plugins)  │
│ - text buffer    │             │ - Python extension   │
│ - render engine  │             │ - Git extension      │
│ - command system │             │ - Sales CRM ext.     │
└─────────────────┘             └────────────────────┘
```

**What makes it work:**
1. **Contribution points** -- extensions declare what they contribute (commands, views, languages) in `package.json`. The core reads this manifest and creates slots.
2. **Activation events** -- extensions load lazily, only when their trigger fires (e.g., `onLanguage:python`). Parallel to SK's progressive disclosure.
3. **API surface control** -- extensions can only call the public API. No DOM access, no internal state. The core is completely protected from plugin misbehavior.
4. **Manifest-driven discovery** -- `package.json` declares capabilities. No runtime introspection needed.

**Direct mapping to Gradata:**
| VS Code Concept | Gradata Equivalent |
|----------------|----------------------|
| package.json contributes | `brain.manifest.json` domain section |
| Contribution points | Tag prefixes, event types, entity schemas |
| Activation events | Domain-specific pipeline triggers |
| Extension Host | Domain plugin loaded via entry_points |

### WordPress Hooks Model

**Pattern: Action/Filter Hook System**

```python
# Core defines hooks (domain-agnostic)
do_action("before_entity_save", entity)
result = apply_filters("entity_display_name", raw_name, entity)

# Domain plugin registers handlers
add_action("before_entity_save", validate_prospect_fields)
add_filter("entity_display_name", format_prospect_name)
```

This is the simplest domain-agnostic pattern: the core emits named events at key points, and domain code registers handlers. The core never imports or references domain code.

---

## Cross-Cutting: Knowledge Base Portability

**Finding:** No published standard exists for portable AI knowledge formats as of March 2026.

**What exists:**
- **MCP (Model Context Protocol)** -- Standardizes tool/resource access, not knowledge format
- **A2A (Agent-to-Agent Protocol)** -- Standardizes agent communication, not knowledge storage
- **GGUF / safetensors** -- Model weight formats, not knowledge
- **RAG pipelines** -- Everyone builds their own chunk + embed + store pipeline
- **brain.manifest.json** (ours) -- Closest thing to a knowledge quality declaration format

**Implication:** There is a genuine gap here. Our `brain.manifest.json` could become the standard for declaring what a knowledge base contains, its quality metrics, and its domain scope. But this only works if the manifest format itself is domain-agnostic (which it currently isn't -- it has sales-specific fields).

---

## Synthesis: The Seven Patterns That Work

### Pattern 1: Generic Core, Typed Boundaries
**Used by:** PydanticAI, LangGraph, Atomic Agents
**How:** Core engine is parameterized by type variables (`Agent[DepsType, OutputType]`). Domain types are defined outside the core and injected.
**Apply to Gradata:** Make `Brain` generic over a `DomainConfig` type. `Brain[SalesConfig]` vs `Brain[RecruitingConfig]`.

### Pattern 2: YAML/JSON Declarative Domain Config
**Used by:** CrewAI, Google ADK
**How:** Domain roles, goals, tools, and vocabulary live in config files. Core reads them at runtime.
**Apply to Gradata:** Move taxonomy, entity types, and event vocabularies to a `domain.yaml` file loaded at brain init.

### Pattern 3: Plugin Registry with Entry Points
**Used by:** Semantic Kernel, VS Code, pytest (via pluggy)
**How:** Domain packages register via entry points / contribution points. Core discovers and loads them.
**Apply to Gradata:** `pip install gradata-sales` registers via `pyproject.toml` entry point. Core discovers domain config, taxonomy, tools.

### Pattern 4: Dependency Injection for Domain Services
**Used by:** PydanticAI (`RunContext[DepsType]`), Semantic Kernel (constructor injection)
**How:** Domain-specific services (CRM client, database, API keys) are injected at runtime, not imported at module level.
**Apply to Gradata:** Replace direct imports of domain services with a DI container passed through the pipeline.

### Pattern 5: Schema-Driven Entity Definitions
**Used by:** Atomic Agents, PydanticAI, LangGraph
**How:** Entities (prospect, candidate, customer) are Pydantic BaseModel subclasses. The core only knows about BaseModel.
**Apply to Gradata:** Define a `DomainEntity` protocol. Sales domain provides `Prospect(DomainEntity)`. Recruiting provides `Candidate(DomainEntity)`. Core references `DomainEntity` only.

### Pattern 6: Progressive Disclosure for Domain Knowledge
**Used by:** Semantic Kernel Agent Skills
**How:** Advertise capabilities cheaply (name + description). Load full instructions only on demand.
**Apply to Gradata:** `brain.manifest.json` advertises domain capabilities. Full domain knowledge loads into context only when relevant query hits.

### Pattern 7: Bounded Context Event Isolation
**Used by:** Axon Framework, EventStoreDB
**How:** Each domain gets its own event types, its own aggregate roots, its own projections. The infrastructure is shared.
**Apply to Gradata:** Events table adds a `domain` column. Each domain package declares its own event types. Core event bus routes by domain.

---

## What Gradata Must Change

### Current State (Hardcoded Sales Domain)

These files embed sales concepts directly in the SDK core:

| File | Sales-Specific Content | Fix |
|------|----------------------|-----|
| `_tag_taxonomy.py` | `prospect`, `angle`, `persona`, `framework`, `tone` values | Move to `domain.yaml` loaded at init |
| `_config.py` | `FILE_TYPE_MAP` with `prospects`, `emails`, `personas` | Make configurable via domain config |
| `_config.py` | `DOMAIN_COLLECTIONS = {"sprites": "domain_sprites"}` | Domain packages register their own collections |
| `_events.py` | Event types like `OUTPUT`, `CORRECTION` with sales-specific validation | Keep generic event types, move domain-specific validation to domain package |
| `brain.manifest.json` | Sales-specific quality metrics | Make manifest schema extensible |

### Target State (Domain-Agnostic Core)

```
gradata/                          # Core SDK (domain-agnostic)
  _events.py                         # Generic: emit(type, source, data, tags)
  _tag_taxonomy.py                   # Generic: load_taxonomy(domain_config)
  _config.py                         # Generic: BrainConfig(domain=DomainConfig)
  domain.py                          # DomainConfig protocol + registry
  patterns/                          # Generic execution patterns

gradata-sales/                    # Domain package (pip installable)
  domain.yaml                        # Tag taxonomy, entity types, event types
  entities.py                        # Prospect, Deal, Company models
  tools.py                           # CRM tools, enrichment tools
  validators.py                      # Sales-specific validation rules

gradata-recruiting/               # Another domain package
  domain.yaml
  entities.py                        # Candidate, Position, Interview models
  tools.py
  validators.py
```

### Recommended Implementation

```python
# Core SDK -- domain.py
from typing import Protocol, Any

class DomainConfig(Protocol):
    """What every domain package must provide."""
    name: str
    entity_types: dict[str, type]      # {"prospect": Prospect, "deal": Deal}
    tag_taxonomy: dict[str, dict]      # Tag prefixes + allowed values
    event_types: list[str]             # Domain-specific event types
    file_type_map: dict[str, str]      # Directory -> type mapping
    validators: dict[str, Callable]    # Domain-specific validation hooks

def load_domain(name: str = "default") -> DomainConfig:
    """Load domain config from entry_points or YAML file."""
    # 1. Check entry_points for installed domain packages
    # 2. Fall back to domain.yaml in brain directory
    # 3. Fall back to minimal default config
    ...
```

```yaml
# domain.yaml (in brain directory or domain package)
name: sales
version: "1.0"

entities:
  prospect:
    fields:
      name: {type: str, required: true}
      company: {type: str, required: true}
      tier: {type: str, values: [T1, T2, T3]}
  deal:
    fields:
      value: {type: float}
      stage: {type: str, values: [discovery, proposal, negotiation, closed]}

tags:
  prospect:
    desc: "Prospect name"
    mode: dynamic
    required_on: [OUTPUT, CORRECTION]
  angle:
    desc: "Sales angle used"
    mode: closed
    values: [direct, pain-point, roi, social-proof, custom]
  persona:
    desc: "Buyer persona"
    mode: closed
    values: [founder, cmo, vp-marketing, growth-lead, other]

event_types:
  - PROSPECT_RESEARCHED
  - EMAIL_SENT
  - DEAL_STAGE_CHANGED
  - MEETING_BOOKED

file_types:
  prospects: prospect
  sessions: session
  emails: email_pattern
  pipeline: pipeline
```

---

## Migration Path (Minimal Disruption)

**Phase 1: Extract** (1 session)
- Create `domain.py` with `DomainConfig` protocol
- Create `domain.yaml` from current hardcoded values in `_tag_taxonomy.py` and `_config.py`
- `_tag_taxonomy.py` reads from `domain.yaml` instead of hardcoded dict
- `_config.py` reads `FILE_TYPE_MAP` from `domain.yaml`
- Zero behavior change -- same values, different source

**Phase 2: Generify** (1-2 sessions)
- Remove all sales-specific imports from core modules
- Event types become domain-declared, not core-declared
- Add `domain` column to events table
- brain.manifest.json gets `domain` field

**Phase 3: Package** (1 session)
- Extract sales config into `gradata-sales` package
- Register via entry_points in pyproject.toml
- Core discovers installed domain packages
- `pip install gradata && pip install gradata-sales` = current behavior

---

## Sources

### Primary (Official Documentation)
- [Google ADK Docs](https://google.github.io/adk-docs/) -- Agent config, tools, custom agents
- [Google ADK Agent Config](https://google.github.io/adk-docs/agents/config/) -- YAML format
- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) -- State schema
- [LangGraph Design Blog](https://blog.langchain.com/building-langgraph/) -- Architecture rationale
- [CrewAI Docs](https://docs.crewai.com/en/concepts/agents) -- Agent configuration
- [PydanticAI Docs](https://ai.pydantic.dev/) -- Agent API, typed dependencies
- [Semantic Kernel Plugins](https://learn.microsoft.com/en-us/semantic-kernel/concepts/plugins/) -- Plugin architecture
- [SK Agent Skills Blog](https://devblogs.microsoft.com/semantic-kernel/give-your-agents-domain-expertise-with-agent-skills-in-microsoft-agent-framework/) -- Progressive disclosure
- [AutoGen GitHub](https://github.com/microsoft/autogen) -- Multi-agent architecture
- [VS Code Extension Host](https://code.visualstudio.com/api/advanced-topics/extension-host) -- Plugin isolation

### Secondary (Architecture References)
- [Martin Fowler CQRS](https://martinfowler.com/bliki/CQRS.html) -- Pattern definition
- [Axon Framework Multi-Context](https://docs.axoniq.io/axon-server-reference/v2024.1/axon-server/administration/multi-context/) -- Bounded context separation
- [Axon Multi-Tenancy Extension](https://github.com/AxonFramework/extension-multitenancy) -- Per-tenant isolation

### Tertiary (Community Analysis)
- [Atomic Agents Analysis](https://medium.com/@mingyang.heaven/atomic-agents-framework-capability-analysis-report-60fa36d7ed47) -- Schema chaining
- [New Stack ADK Tour](https://thenewstack.io/what-is-googles-agent-development-kit-an-architectural-tour/) -- Architecture overview
