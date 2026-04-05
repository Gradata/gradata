# Gradata Feature Matrix: Open SDK vs. Cloud

## Open SDK (AGPL-3.0 + Commercial License)

| Feature | Status | Description |
|---------|--------|-------------|
| `correct()` | Included | Record corrections, auto-classify severity |
| `auto_evolve()` | Included | Machine-speed correction generation |
| `apply_brain_rules()` | Included | Inject graduated rules into prompts |
| `export_rules_json()` | Included | Git-diffable JSON rule export |
| `export_rules_yaml()` | Included | Human-readable YAML rule export |
| `export_rules()` | Included | OpenSpace SKILL.md format export |
| `lineage()` | Included | Full correction-to-rule provenance |
| `rollback()` | Included | Disable any lesson with audit trail |
| `approve_lesson()` | Included | Human-in-the-loop approval gate |
| `health()` | Included | Brain health diagnostics |
| `manifest()` | Included | Brain capability fingerprint |
| `search()` | Included | FTS + embedding search across brain |
| `guard()` | Included | Input/output guardrails from rules |
| `track_rule()` | Included | Rule application logging |
| `assess_risk()` | Included | Action risk classification |
| `compare_output()` | Included | Before/after rule impact preview |
| `backfill_from_git()` | Included | Bootstrap brain from git history |
| `diagnose` CLI | Included | Free correction pattern diagnostic |
| Poisoning defense | Included | >40% contradiction rate blocks |
| Adversarial graduation | Included | 3-gate: dedup + contradiction + paraphrase |
| FSRS-inspired confidence | Included | Calibrated from 2992 events |
| Meta-rule synthesis | Included | Emerge from 3+ related RULE lessons |
| Zero dependencies | Included | `pip install gradata` — nothing else |
| Fully offline | Included | No network calls, no telemetry |
| Air-gapped deployment | Included | Works behind any firewall |

## Cloud Dashboard (gradata.ai — coming soon)

| Feature | Status | Description |
|---------|--------|-------------|
| Multi-brain analytics | Cloud only | Compare brains across teams |
| Team-level dashboards | Cloud only | Org-wide correction patterns |
| SSO / RBAC | Cloud only | Enterprise identity management |
| SLA-backed uptime | Cloud only | 99.9% with phone support |
| SOC 2 Type II | Cloud only | Compliance certification |
| Cross-brain learning | Cloud only | Patterns transfer between brains |
| Brain marketplace | Cloud only | Rent/share trained brains |
| Advanced scheduling | Cloud only | FSRS-optimized review timing |
| Hosted API | Cloud only | REST API for CI/CD integration |

## Key Principle

The SDK handles **90%+ of use cases** completely offline with zero dependencies.
Cloud features are genuinely differentiated (multi-tenant, compliance, cross-brain)
— not artificial gates on core functionality.
