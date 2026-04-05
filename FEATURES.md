# Gradata Feature Matrix: Open SDK vs. Cloud

## Open SDK (AGPL-3.0 + Commercial License)

| Feature | Status | Description |
|---------|--------|-------------|
| `correct()` | Included | Record corrections, auto-classify severity |
| `auto_evolve()` | Included | Machine-speed correction generation |
| `apply_brain_rules()` | Included | Inject graduated rules into prompts |
| `end_session()` | Included | Graduation sweep + SESSION_END event tracking |
| `brain.session` | Included | Auto-tracked session counter from event log |
| `export_rules_json()` | Included | Git-diffable JSON rule export |
| `export_rules()` | Included | Export rules in multiple formats |
| `lineage()` | Included | Full correction-to-rule provenance |
| `rollback()` | Included | Disable any lesson with audit trail |
| `approve_lesson()` | Included | Human-in-the-loop approval gate |
| `health()` | Included | Brain health diagnostics |
| `manifest()` | Included | Brain capability fingerprint + compound score |
| `search()` | Included | FTS + embedding search across brain |
| `guard()` | Included | Input/output guardrails from rules |
| `track_rule()` | Included | Rule application logging |
| `forget()` | Included | Delete specific lessons (GDPR right-to-erasure) |
| `backfill_from_git()` | Included | Bootstrap brain from git history |
| `observe()` | Included | Extract facts from conversations without corrections |
| `detect_implicit_feedback()` | Included | Detect behavioral feedback in user messages |
| `diagnose` CLI | Included | Free correction pattern diagnostic |
| Poisoning defense | Included | >40% contradiction rate blocks |
| Adversarial graduation | Included | 3-gate: dedup + contradiction + paraphrase |
| FSRS-inspired confidence | Included | Calibrated severity-weighted scoring |
| Meta-rule synthesis | Included | Emerge from 3+ related RULE lessons |
| 21 agentic patterns | Included | Pipeline, Guard, RAG, MCP, Orchestrator, etc. |
| Zero dependencies | Included | `pip install gradata` — nothing else |
| Fully offline | Included | No network calls, no telemetry |
| Air-gapped deployment | Included | Works behind any firewall |

## Cloud Dashboard (gradata.ai — coming soon)

| Feature | Status | Description |
|---------|--------|-------------|
| Brain analytics dashboard | Cloud only | "Fitness tracker for your AI" — session trends, compound score over time |
| Multi-brain comparison | Cloud only | Compare brains across teams or domains |
| Team-level dashboards | Cloud only | Org-wide correction patterns |
| Brain quality validation | Cloud only | Proprietary scoring engine for marketplace listing |
| Cross-brain learning | Cloud only | Patterns transfer between brains |
| Brain marketplace | Cloud only | Rent/share trained brains |
| SSO / RBAC | Cloud only | Enterprise identity management |
| Hosted API | Cloud only | REST API for CI/CD integration |
| SOC 2 Type II | Cloud only | Compliance certification |

## Key Principle

The SDK handles **90%+ of use cases** completely offline with zero dependencies.
Cloud features are genuinely differentiated (multi-tenant, compliance, cross-brain)
— not artificial gates on core functionality.

## Where Gradata Fits in Your Stack

```
┌─────────────────────────────────────────────┐
│  Your Agent (Claude Code, Hermes, etc.)     │
├─────────────────────────────────────────────┤
│  Episodic Memory (EverOS, Mem0, etc.)       │  ← "what happened"
├─────────────────────────────────────────────┤
│  Procedural Memory (Gradata)                │  ← "how to behave"
├─────────────────────────────────────────────┤
│  LLM (Claude, Gemma 4, GPT, etc.)          │
└─────────────────────────────────────────────┘
```

Gradata is the procedural memory layer. It doesn't replace your episodic memory
(EverOS, Mem0, Letta) — it complements it. Episodic memory recalls what happened.
Gradata teaches the agent how to behave based on accumulated corrections.
