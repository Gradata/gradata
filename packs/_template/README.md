# [Profession] Pack — Template

Blank profession pack for the claude-reflect SDK. Copy this folder and customize
for any role that uses the reflect/log-outcome/session-audit workflow.

## Setup Checklist

1. **Copy this folder** to `packs/[your-profession]/`
2. **Define your routing targets** in `routing.md`
3. **Define your outcome schema** in `outcomes.md`
4. **Define your pattern categories** in `patterns.md`
5. **Update CLAUDE.md** with profession-specific rules

## Files to Create

### routing.md
Define where learnings get routed:
```
Route 1: Behavioral Rule → [your CLAUDE.md section]
Route 2: Specific Mistake → [your lessons file]
Route 3: Methodology Insight → [your review location]
```

### outcomes.md
Define your tactic→result types:
```
| Type | Description | Storage Location |
|------|------------|------------------|
| [type1] | [what it is] | [where it goes] |
| [type2] | [what it is] | [where it goes] |
```

### patterns.md
Define what patterns you track:
```
| Category | What To Track | Confidence Threshold |
|----------|--------------|---------------------|
| [cat1] | [description] | [min samples] |
```

## Commands Available (profession-agnostic)

These commands work regardless of profession:

| Command | Purpose |
|---------|---------|
| `/reflect` | Process corrections → route to rules or lessons |
| `/log-outcome` | Record any tactic→result pair |
| `/session-audit` | Full session close (reflect + log + summary + upgrade proposals) |
| `/view-queue` | See pending learnings |
| `/skip-reflect` | Discard queue |

## Hooks (automatic, no setup needed)

| Hook | Trigger | Action |
|------|---------|--------|
| UserPromptSubmit | Every prompt | Detect correction patterns, queue them |
| PreCompact | Context compaction | Backup queue before compression |
| PostToolUse (Bash) | Git commits | Remind to /reflect |
| SessionStart | Session begins | Show pending learnings count |
