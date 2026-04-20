# Claude Code Setup

Gradata ships with a hook installer for Claude Code. Once installed, hooks fire on `SessionStart`, `PreToolUse`, `PostToolUse`, `Stop`, `PreCompact`, and `UserPromptSubmit` events — so rules get injected, corrections get captured, and the session closes cleanly without manual glue.

## One-command install

```bash
gradata hooks install --profile standard
```

What this does:

1. Writes hook entries to `~/.claude/settings.json`.
2. Registers each hook under its event (`SessionStart`, `PreToolUse`, etc.).
3. Points every hook at `python -m gradata.hooks.<module>`.
4. Leaves your existing non-Gradata settings untouched.

Verify:

```bash
gradata hooks status
```

Uninstall:

```bash
gradata hooks uninstall
```

## Profiles

Three profiles ship out of the box. Pick the one that matches your comfort level.

| Profile | Scope | Hooks |
|---------|-------|-------|
| `minimal` | Capture only — no enforcement | `auto_correct`, `inject_brain_rules`, `session_close` |
| `standard` (default) | Capture + enforcement + agent graduation | Everything in `minimal` plus 10 more (see below) |
| `strict` | Maximum guardrails, including duplicate-file blocking and pushback detection | Everything in `standard` plus 4 more |

Install a non-default profile:

```bash
gradata hooks install --profile minimal
gradata hooks install --profile strict
```

## What each hook does

| Hook | Event | Purpose |
|------|-------|---------|
| `auto_correct` | `PostToolUse` on Edit/Write | Captures diffs as corrections |
| `inject_brain_rules` | `SessionStart` | Injects graduated rules at the top of the session |
| `session_close` | `Stop` | Emits `SESSION_END`, runs graduation sweep |
| `secret_scan` | `PreToolUse` on Write/Edit/MultiEdit | Blocks secrets in written content |
| `config_protection` | `PreToolUse` on Write/Edit/MultiEdit | Blocks weakening of linter/CI config |
| `rule_enforcement` | `PreToolUse` on Write/Edit/MultiEdit | Injects RULE reminders before edits |
| `agent_precontext` | `PreToolUse` on Agent | Injects rules into sub-agent prompts |
| `agent_graduation` | `PostToolUse` on Agent | Records agent outcomes for graduation |
| `tool_failure_emit` | `PostToolUse` on Bash | Tracks tool failures with backoff |
| `tool_finding_capture` | `PostToolUse` on Bash/Edit/Write | Bridges lint and test findings to corrections |
| `config_validate` | `SessionStart` | Validates `settings.json` integrity |
| `context_inject` | `UserPromptSubmit` | Injects brain context on user messages |
| `pre_compact` | `PreCompact` | Saves state before context compression |
| `duplicate_guard` | `PreToolUse` on Write (strict) | Blocks new files when a similar one exists |
| `brain_maintain` | `Stop` (strict) | FTS rebuild and brain maintenance |
| `session_persist` | `Stop` (strict) | Crash-safe session handoff |
| `implicit_feedback` | `UserPromptSubmit` (strict) | Detects pushback as implicit corrections |

## Manual install

If you need to configure hooks by hand, open `~/.claude/settings.json` and add:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "description": "Gradata: inject graduated rules at session start",
        "hooks": [
          {
            "type": "command",
            "command": "python -m gradata.hooks.inject_brain_rules",
            "timeout": 10000
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "description": "Gradata: capture corrections from edits",
        "hooks": [
          {
            "type": "command",
            "command": "python -m gradata.hooks.auto_correct",
            "timeout": 5000
          }
        ]
      }
    ],
    "Stop": [
      {
        "description": "Gradata: emit SESSION_END + run graduation sweep",
        "hooks": [
          {
            "type": "command",
            "command": "python -m gradata.hooks.session_close",
            "timeout": 15000
          }
        ]
      }
    ]
  }
}
```

Each hook module can be invoked standalone with `python -m gradata.hooks.<module>`.

## MCP server (alternative)

If you prefer MCP over hooks, Gradata also ships a Model Context Protocol server:

```bash
# One-liner install
npx -y @gradata/mcp-installer --client claude
```

This adds a `gradata` entry to `~/.claude/mcp_servers.json` exposing three tools: `correct`, `recall`, and `manifest`. Hooks give you proactive enforcement; MCP gives you reactive tool calls. You can run both.

See [SDK → Rule-to-Hook](../sdk/rule-to-hook.md) for how rules become hooks.
