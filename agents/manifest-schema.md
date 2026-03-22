# Agent Manifest Schema — AIOS Standard

> The second universal standard. Score governs output quality. Manifest governs agent authority.
> Every agent gets a manifest. Every manifest follows this schema. No exceptions.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (kebab-case) | Unique agent identifier |
| `name` | string | Human-readable name |
| `status` | enum: active / dormant / paused | Current operational state |
| `version` | date (YYYY-MM-DD) | Last updated |
| `department` | enum: sales / systems / domain / core | Which layer this agent operates in |
| `description` | string | What the agent does (one line) |
| `instruction_file` | path | Markdown file loaded as system prompt |

## Permission Fields

| Field | Type | Description |
|-------|------|-------------|
| `tools_allowed` | list | Whitelist — ONLY these tools available. If set, overrides everything else. |
| `tools_denied` | list | Blacklist — these tools always excluded, even if in allowed list |
| `write_paths` | glob list | Where this agent can write files. Outside paths = blocked. |

**Enforcement:** If an agent attempts a tool outside its allowlist or inside its denylist, the action is blocked and a `TOOL_DENIED` signal is emitted to the neural bus.

## Context Fields

| Field | Type | Description |
|-------|------|-------------|
| `bootstrap_files` | path list | Shared context loaded after instructions |
| `bootstrap_limit` | string | Max chars per file / total. Default: 12000/file, 30000 total |
| `warmup` | path list | Files loaded before execution for situational awareness |
| `scope_tags` | list | Bus signal tags this agent reads/writes (used by Agent Distillation) |
| `scope_paths` | glob list | Brain paths this agent owns (used by Agent Distillation) |

## Trust Fields

| Field | Type | Description |
|-------|------|-------------|
| `trust_level` | enum: config-only / config+instructions / config+instructions+code | What this agent is allowed to change |
| `correction_rate` | float (0.0–1.0) | Rolling 5-session correction rate. Updated at wrap-up. |
| `consecutive_rejections` | int | Current streak. Reset on accepted output. |
| `auto_pause_threshold` | int | Consecutive rejections before auto-pause. Default: 3. |

**Trust mechanics:**
- `config-only` — can modify settings, manifests, configuration files
- `config+instructions` — above + can modify instruction files, skills, CARL rules
- `config+instructions+code` — above + can modify scripts, hooks, infrastructure

**Promotion:** correction_rate < 0.10 over 5 sessions → eligible for trust level increase. Requires Oliver approval.
**Demotion:** correction_rate > 0.25 OR consecutive_rejections hits threshold → automatic trust level decrease + SYSTEM_PAUSE signal.

## Changelog

Append-only. One line per change.

```
- YYYY-MM-DD: [what changed]
```

---

## How Manifests Wire Into the Nervous System

| Connection | Signal | Direction |
|------------|--------|-----------|
| Tool violation | `TOOL_DENIED` | Manifest → Neural Bus |
| Trust demotion | `SYSTEM_PAUSE` | Manifest → Neural Bus |
| Correction received | `CORRECTION` | Neural Bus → Manifest (updates correction_rate) |
| Agent created | `AGENT_CREATED` | Scaffold skill → Neural Bus |
| Escalation triggered | `ESCALATION_TRIGGERED` | Escalation protocol → Neural Bus |

| Cross-Wire | What it does |
|------------|-------------|
| CW-10: Tool Violation → Manifest Fix | If TOOL_DENIED fires, check if allowlist needs updating or if agent overstepped |
| CW-11: Correction Rate → Autonomy Scope | Track correction rate → adjust trust_level up or down |
| CW-12: Escalation → Lessons | Every REDUCE_SCOPE or STOP escalation auto-generates a lesson |

## Agent-Local Rules (Independent Evolution)

> Source: Netflix Full Cycle Developers / Spotify Squad Model. Agents at trust >= 2 can develop specialized rules.

Agents with `trust_level` >= `config+instructions` may propose **agent-local rules** — behavioral rules that apply only within their scope. This enables specialization without polluting the global rule system.

| Field | Type | Description |
|-------|------|-------------|
| `local_rules` | list of rules | Agent-specific behavioral rules (same format as CARL) |
| `local_rule_cap` | int | Max agent-local rules. Default: 5. |
| `local_rule_lifecycle` | same as lessons | [INSTINCT:0.30] → [PATTERN] → graduated to domain CARL |

**Lifecycle:**
1. Agent proposes a local rule based on corrections or outcomes within its scope
2. Rule is `[INSTINCT:0.30]` — confidence tracked within agent scope (see self-improvement.md pipeline)
3. If effective (confidence reaches 0.60+): promoted to `[PATTERN]`
4. If confirmed and generalizable: graduated to domain CARL rule (e.g., domain/carl/demo-prep)
5. If confidence drops below 0.00: auto-retired

**Safeguards:**
- Agent-local rules CANNOT contradict system CARL, safety rules, or the Rule Constitution
- Agent-local rules cannot expand the agent's own permissions or trust level
- Oliver can veto any agent-local rule at any time

**Tracking:** Agent-local rule count, promotion rate, and correction rate on local vs system rules — logged in agent brain updates.

## Creating New Agents

Use the `/agent-scaffold` skill. It generates a manifest from this schema plus an instruction file template.

## Validation

At session start, any loaded manifest is checked:
1. All required fields present
2. `tools_allowed` and `tools_denied` don't conflict
3. `trust_level` matches current `correction_rate`
4. `write_paths` are valid globs
5. `status` is not `paused` (paused agents don't load)

If validation fails → `LAUNCH_CHECK` signal with details.
