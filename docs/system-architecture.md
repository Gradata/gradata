# Gradata System Architecture

## High-Level Overview

```mermaid
graph TB
    subgraph Entry["Entry Points"]
        USER[User Prompt]
        SESSION[Session Start]
        STOP[Session End]
        COMPACT[Context Compact]
    end

    subgraph Config["Configuration Layer"]
        CLAUDE[CLAUDE.md]
        DOMAIN[domain/DOMAIN.md]
        SOUL[domain/soul.md]
        CARL[.carl/global]
        GATES[domain/gates/]
        RUBRICS[.claude/quality-rubrics.md]
        WATERFALL[.claude/action-waterfall.md]
        PLAYBOOKS[domain/playbooks/]
    end

    subgraph Hooks["Hook Layer — Node Dispatchers + Mixed Hooks"]
        direction TB
        H_START["SessionStart (3 hooks, 23s)"]
        H_PRE["PreToolUse (7 hooks, 19s, BLOCKING)"]
        H_POST["PostToolUse (12 hooks, 113s)"]
        H_PROMPT["UserPrompt (7 hooks, 30s)"]
        H_STOP["Stop (4 hooks, 55s)"]
        H_COMPACT["PreCompact (2 hooks, 13s)"]
    end

    subgraph SDK["SDK Layer (sdk/src/gradata/)"]
        direction TB
        BRAIN[brain.py — Core API + Mixins]
        PATTERNS[patterns/ — 17 modules]
        ENHANCE[enhancements/ — 24 modules]
    end

    subgraph Persist["Brain Vault"]
        EVENTS[events.jsonl — 7 writers]
        LESSONS[lessons.md — 2 writers, 2 readers]
        SYSDB[system.db]
        PROSPECTS[prospects/ — 1 writer, 5 readers]
        SESSIONS[sessions/]
    end

    subgraph External["External Integrations (MCP + API)"]
        PIPE[Pipedrive]
        APOLLO[Apollo]
        GMAIL[Gmail]
        GCAL[Calendar]
        INSTANTLY[Instantly]
        FIRE[Fireflies]
    end

    USER --> H_PROMPT
    SESSION --> H_START
    STOP --> H_STOP
    COMPACT --> H_COMPACT

    H_PROMPT --> Config
    H_START --> Config
    H_PRE --> SDK
    H_POST --> SDK
    H_STOP --> SDK

    SDK --> Persist
    H_START --> External
    H_PROMPT --> External

    BRAIN --> EVENTS
    BRAIN --> LESSONS
    BRAIN --> SYSDB
    ENHANCE --> LESSONS
    ENHANCE --> EVENTS
    PATTERNS --> LESSONS
```

## Learning Pipeline Flow

```mermaid
graph LR
    A[User Edits Draft] --> B[auto_correct.py]
    B --> C[edit-distance.py]
    C --> D[edit-classifier.py]
    D --> E[CORRECTION Event]
    E --> F[events.jsonl]

    F --> G[capture-session-corrections.py]
    G --> H["lessons.md — INSTINCT"]

    H --> I{"Confidence threshold met?<br/>Sufficient applications"}
    I -->|Yes| J[PATTERN]
    I -->|No| H

    J --> K{"Higher threshold met?<br/>More applications required"}
    K -->|Yes| L[RULE]
    K -->|No| J

    L --> M{"Related rules cluster?"}
    M -->|Yes| N["META-RULE (Cloud)"]
    M -->|No| L

    N --> O[agent-precontext.js]
    O --> P[Injected into Next Session]

    style A fill:#f9f,stroke:#333
    style N fill:#ff9,stroke:#333
    style P fill:#9f9,stroke:#333
```

## Tool Coverage Matrix

```mermaid
graph TD
    subgraph PreTool["PreToolUse — BLOCKING"]
        W_PRE["Write: quality-gate, brain-recall,<br/>rule-enforcement, secret-scan, config-protection"]
        E_PRE["Edit: rule-enforcement, secret-scan,<br/>config-protection"]
        A_PRE["Agent: agent-precontext"]
        M_PRE["MCP: mcp-health"]
        R_PRE["Read: (none)"]
        B_PRE["Bash: (none)"]
    end

    subgraph PostTool["PostToolUse — NON-BLOCKING"]
        W_POST["Write: obsidian-autolink, output-event,<br/>qwen-lint, arch-review,<br/>delta-auto-tag, behavior-triggers"]
        E_POST["Edit: obsidian-autolink, output-event,<br/>qwen-lint, arch-review,<br/>delta-auto-tag, behavior-triggers,<br/>auto_correct.py"]
        A_POST["Agent: agent-graduation"]
        M_POST["MCP: tool-failure-emit"]
        R_POST["Read: gate-emit"]
        B_POST["Bash: post_commit_reminder,<br/>behavior-triggers"]
    end

    style R_PRE fill:#fcc,stroke:#900
    style B_PRE fill:#fcc,stroke:#900
    style R_POST fill:#cfc,stroke:#090
    style W_PRE fill:#cfc,stroke:#090
```

## Hook Execution — Write Operation

```mermaid
sequenceDiagram
    participant U as User/Claude
    participant PRE as PreToolUse (13s budget)
    participant W as Write Tool
    participant POST as PostToolUse (63s budget)

    U->>PRE: Write requested
    Note over PRE: BLOCKING — can deny
    PRE->>PRE: quality-gate.js (3s)
    PRE->>PRE: brain-recall.js (5s)
    PRE->>PRE: rule-enforcement.js (2s)
    PRE->>PRE: secret-scan.js (3s) — can BLOCK
    PRE->>PRE: config-protection.js (3s)

    PRE->>W: Approved
    W->>W: File written to disk

    W->>POST: Write complete
    Note over POST: NON-BLOCKING — silent failures
    POST->>POST: obsidian-autolink.js (3s)
    POST->>POST: output-event.js (5s) — creates manifest
    POST->>POST: qwen-lint.js (15s)
    POST->>POST: arch-review.js (30s)
    POST->>POST: delta-auto-tag.js (5s) — consumes manifest
    POST->>POST: suggest-compact.js (3s)
    POST->>POST: behavior-triggers.js (5s)
```

## Hook Execution — Full Session Lifecycle

```mermaid
sequenceDiagram
    participant U as User
    participant SS as SessionStart
    participant UP as UserPrompt
    participant PT as PreToolUse
    participant T as Tool
    participant PO as PostToolUse
    participant ST as Stop
    participant PC as PreCompact

    U->>SS: Session begins
    SS->>SS: session_start_reminder.py (10s)
    SS->>SS: session-init-data.js (10s)
    SS->>SS: config-validate.js (3s)

    U->>UP: Sends message
    UP->>UP: session-start-reminder.js (5s)
    UP->>UP: capture_learning.py (8s)
    UP->>UP: context-inject.js (5s)
    UP->>UP: gate-inject.js (3s)
    UP->>UP: prospect-autoload.js (3s)
    UP->>UP: implicit-feedback.js (3s)
    UP->>UP: skill-router.js (3s)

    UP->>PT: Tool called
    Note over PT: See Write/Edit/Agent detail above
    PT->>T: Execute tool
    T->>PO: Tool completes
    Note over PO: See Write/Edit/Agent detail above

    Note over PC: On context window pressure
    PC->>PC: check_learnings.py (10s)
    PC->>PC: post-compact.js (3s)

    U->>ST: Session ends
    ST->>ST: cost-tracking.js (5s)
    ST->>ST: session-persist.js (5s)
    ST->>ST: session-close-data.js (15s)
    ST->>ST: brain-maintain.js (30s)
```

## Data Flow — Shared State

```mermaid
graph LR
    subgraph Writers["Writers"]
        GE[gate-emit.js]
        OE[output-event.js]
        TFE[tool-failure-emit.js]
        SSR[session_start_reminder.py]
        SCD[session-close-data.js]
        CT[cost-tracking.js]
        IF[implicit-feedback.js]
        MB[memory-bridge.py]
        CL[capture_learning.py]
        OA[obsidian-autolink.js]
        AG[agent-graduation.js]
    end

    subgraph State["Shared State"]
        EV["events.jsonl<br/>(7 writers)"]
        LM["lessons.md<br/>(2 writers, 2 readers)"]
        PR["prospects/<br/>(1 writer, 5 readers)"]
        MH[".mcp-health.json<br/>(circuit breaker)"]
        AO["agents/outcomes.jsonl"]
    end

    subgraph Readers["Readers"]
        AP[agent-precontext.js]
        RE[rule-enforcement.js]
        BR[brain-recall.js]
        DAT[delta-auto-tag.js]
        PA[prospect-autoload.js]
        MHP[mcp-health.js]
        BM[brain-maintain.js]
    end

    GE --> EV
    OE --> EV
    TFE --> EV
    SSR --> EV
    SCD --> EV
    CT --> EV
    IF --> EV

    MB --> LM
    CL --> LM
    LM --> AP
    LM --> RE

    OA --> PR
    PR --> BR
    PR --> DAT
    PR --> PA
    PR --> OE
    PR --> SSR

    TFE --> MH
    MH --> MHP

    AG --> AO
    EV --> BM
```

## SDK Module Map

```mermaid
graph TD
    subgraph Core["Core Brain (Mixin Architecture)"]
        B[brain.py — composes mixins]
        BE[_brain_events.py — BrainEventsMixin]
        BL[_brain_learning.py — BrainLearningMixin]
        BQ[_brain_quality.py — BrainQualityMixin]
        BM[_brain_manifest.py — BrainManifestMixin]
        BS[_brain_search.py — BrainSearchMixin]
    end

    subgraph Patterns["patterns/ — 17 modules"]
        OR[orchestrator.py]
        PL[pipeline.py]
        RE[rule_engine.py]
        MEM[memory.py]
        RAG[rag.py]
        REF[reflection.py]
        GR[guardrails.py]
        SA[sub_agents.py]
        QL[q_learning_router.py]
    end

    subgraph Enhancements["enhancements/ — 24 modules"]
        DE[diff_engine.py]
        EC[edit_classifier.py]
        QG[quality_gates.py]
        MR[meta_rules.py — 1568 LOC]
        RV[rule_verifier.py]
        SI[self_improvement.py]
        TP[truth_protocol.py]
        LP[learning_pipeline.py]
        PI[pattern_integration.py]
        RC[rule_canary.py — dormant until 50+ rules]
        CD[contradiction_detector.py — advisory signal]
    end

    B --> BE
    B --> BL
    B --> BQ
    B --> BM
    B --> BS

    BL --> DE
    BL --> EC
    BL --> LP
    LP --> SI
    LP --> MR
    LP --> RV

    OR --> PL
    OR --> RE
    OR --> DE
    RE --> MEM
    RE --> RAG

    SI --> CD
    MR -.-> RC

    style RC fill:#ffe,stroke:#990
    style CD fill:#ffe,stroke:#990
```

## External Integration Map

```mermaid
graph LR
    subgraph Access["Access Methods"]
        MCP[MCP Tools]
        API[Direct API]
        SYNC[api_sync.py]
    end

    subgraph CRM["Sales Stack"]
        PD[Pipedrive — Deals/Contacts]
        AP[Apollo — Enrichment]
        IN[Instantly — Cold Email]
        ZB[ZeroBounce — Validation]
    end

    subgraph Comms["Communication"]
        GM[Gmail — Threads]
        GC[Google Calendar]
        FF[Fireflies — Transcripts]
    end

    subgraph Research["Research"]
        NB[NotebookLM]
        CL[Clay — Enrichment]
    end

    MCP --> PD
    MCP --> AP
    MCP --> IN
    MCP --> GM
    MCP --> GC
    MCP --> FF
    API --> ZB
    API --> CL
    SYNC --> PD
    SYNC --> GM
    SYNC --> GC
    SYNC --> FF
    SYNC --> IN
```
