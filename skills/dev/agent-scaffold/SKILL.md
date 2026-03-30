---
name: agent-scaffold
description: Generate a new agent following the Gradata manifest schema. Use when the user mentions "new agent", "create agent", "add agent", "scaffold agent", "agent manifest", "subagent", "spawn agent", or needs to create specialized subagents with scoped permissions, bootstrap files, and trust levels.
---

# /agent-scaffold — Create New Agent with Manifest

> Generates a new agent following the Gradata manifest schema.
> Produces manifest.md + instructions.md + wires into registry and component map.

## Trigger
When: creating a new agent, adding an agent, scaffolding an agent
Keywords: "new agent", "create agent", "add agent", "scaffold agent"

## Inputs
Ask for (if not provided):
1. **Agent ID** — kebab-case identifier (e.g., `research-agent`)
2. **Department** — sales / systems / domain / core
3. **Description** — one-line purpose
4. **Tools needed** — what tools should it have access to?
5. **Write paths** — where can it write in brain/?

## Steps

### Step 1: Generate Manifest
Create `agents/{id}/manifest.md` following [[agents/manifest-schema.md]]:

```markdown
# Agent: {id}

## Identity
- id: {id}
- name: {human-readable name}
- status: active
- version: {today's date}
- department: {department}
- description: {description}
- instruction_file: agents/{id}/instructions.md

## Permissions
- tools_allowed: [{tools list}]
- tools_denied: [{inverse of allowed, based on department defaults}]
- write_paths: [{paths}]

## Context
- bootstrap_files: [{department-appropriate defaults}]
- bootstrap_limit: 12000 chars/file, 30000 total
- warmup: [{relevant brain/ files}]
- scope_tags: [{derive from department and description}]
- scope_paths: [{derive from write_paths}]

## Trust
- trust_level: config-only
- correction_rate: 0.00
- consecutive_rejections: 0
- auto_pause_threshold: 3

## Changelog
- {today}: Created via /agent-scaffold
```

**Default trust:** New agents always start at `config-only`. They earn higher trust through low correction rates.

### Step 2: Generate Instructions
Create `agents/{id}/instructions.md` with:
- Role description
- Key responsibilities
- What this agent does NOT do (hard boundaries)
- Reference to manifest for permissions

### Step 3: Wire Into Registry
Add entry to `agents/registry.md`:
```markdown
## {id}
- **Manifest:** [[agents/{id}/manifest.md]]
- **Brain path:** agents/{id}/brain/updates/
- **Scope tags:** [{tags}]
- **Scope paths:** [{paths}]
```

### Step 4: Wire Into Component Map
Add row to `.claude/component-map.md` under appropriate section.

### Step 5: Create Brain Directory
Create `agents/{id}/brain/updates/` for Agent Distillation output.

### Step 6: Bus Signal
Write to neural bus: `[HH:MM] [agent-scaffold] AGENT_CREATED agent={id} department={department} trust=config-only`

### Step 7: Confirm
Show Oliver the manifest and ask for approval before committing.

## Department Defaults

| Department | Default tools_denied | Default bootstrap_files | Default warmup |
|---|---|---|---|
| sales | [Edit .claude/*, Write .carl/*, Bash destructive] | [domain/DOMAIN.md, domain/soul.md] | [brain/loop-state.md, domain/pipeline/startup-brief.md] |
| systems | [Apollo, Gmail, Fireflies, Pipedrive, Instantly] | [.claude/component-map.md, .claude/self-improvement.md] | [brain/system-patterns.md, brain/events.jsonl] |
| domain | [Edit .claude/*, Bash destructive] | [domain/DOMAIN.md] | [brain/loop-state.md] |
| core | [] | [CLAUDE.md] | [brain/system-patterns.md] |
