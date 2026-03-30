# Gradata for Claude Code: One-Liner Install

## Quick Install

```bash
npx -y @gradata/mcp-installer --client claude
```

This single command:
1. Installs the Gradata MCP server (`pip install gradata` if not already installed)
2. Adds the server to Claude Code's MCP configuration (`~/.claude/mcp_servers.json`)
3. Detects or creates a brain directory at `./brain/` (or uses `$BRAIN_DIR`)
4. Verifies the connection with a health check

## What Gets Configured

After install, Claude Code's MCP config (`~/.claude/mcp_servers.json`) contains:

```json
{
  "gradata": {
    "command": "python",
    "args": ["-m", "gradata.mcp_server", "--brain-dir", "/path/to/your/brain"],
    "env": {}
  }
}
```

## What the MCP Server Exposes

Three tools become available to Claude Code automatically:

### `correct` -- Log a correction

When Claude produces a draft and you edit it, this tool captures the before/after for learning.

```
Tool: correct
Input: { "draft": "original text", "final": "your edited version", "category": "DRAFTING" }
Output: { "severity": "moderate", "edit_distance": 0.34, "category": "DRAFTING", "lesson_created": true }
```

Claude Code calls this automatically when it detects you've edited its output.

### `recall` -- Get relevant rules

Before generating output, Claude Code asks for rules relevant to the current task.

```
Tool: recall
Input: { "query": "write cold email to CTO", "max_rules": 5 }
Output: <brain-rules>[RULE:0.95] Never use 'revolutionize'...</brain-rules>
```

Rules are ranked by relevance and confidence. Only graduated rules (PATTERN 0.60+ and RULE 0.90+) are returned.

### `manifest` -- Show improvement proof

Returns the brain's quality metrics as machine-readable data.

```
Tool: manifest
Input: {}
Output: { "correction_rate": 0.12, "categories_extinct": ["FORMATTING"], "compound_score": 7.8, "rules_count": 14 }
```

## Manual Install

If the one-liner doesn't work, configure manually:

### Step 1: Install Gradata

```bash
pip install gradata
```

### Step 2: Initialize a brain (if you don't have one)

```bash
python -c "from gradata import Brain; Brain.init('./brain')"
```

### Step 3: Add to Claude Code MCP config

Edit `~/.claude/mcp_servers.json`:

```json
{
  "gradata": {
    "command": "python",
    "args": ["-m", "gradata.mcp_server", "--brain-dir", "./brain"]
  }
}
```

### Step 4: Restart Claude Code

The three tools (`correct`, `recall`, `manifest`) appear automatically.

## What Happens Automatically

Once installed, the Gradata MCP server works passively:

1. **Rule injection**: When Claude Code starts a task, it calls `recall` to get relevant rules. These shape its output before you see it.

2. **Correction capture**: When you edit Claude's output (accept with changes, rewrite, or explicitly correct), the `correct` tool logs the diff. Over time, corrections graduate into rules.

3. **Quality tracking**: The `manifest` tool provides a dashboard of improvement. Correction categories that stop recurring are marked as "extinct" -- proof the brain learned.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BRAIN_DIR` | `./brain` | Path to brain directory |
| `GRADATA_LOG` | (none) | Set to `DEBUG` for verbose logging |

## Verify Installation

```bash
# Check the MCP server starts correctly
python -m gradata.mcp_server --brain-dir ./brain <<< '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

You should see a JSON-RPC response with `protocolVersion` and `serverInfo`.

## Comparison with SuperMemory MCP

| Feature | SuperMemory | Gradata |
|---------|-------------|---------|
| Install | `npx install-mcp` | `npx @gradata/mcp-installer` |
| Tools | memory, recall, whoAmI | correct, recall, manifest |
| Learning | Stores memories | Graduates corrections into rules |
| Proof | None | brain.manifest.json |
| Open source | Partial | Full SDK (AGPL) |
