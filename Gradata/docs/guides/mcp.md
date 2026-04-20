# MCP Integration

The SDK includes an MCP server that exposes brain operations to any MCP-compatible host.

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) is a standard for connecting AI tools to language model hosts. Claude Code, Cursor, VS Code Copilot Chat, and other tools support MCP.

## Starting the MCP Server

```bash
python -m gradata.mcp_server --brain-dir ./my-brain
```

The server communicates over stdin/stdout using JSON-RPC 2.0 with Content-Length framing.

## Exposed Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `brain_search` | `query`, `top_k` | Search brain knowledge |
| `brain_correct` | `draft`, `final` | Log a correction |
| `brain_log_output` | `text`, `output_type`, `self_score` | Log AI output |
| `brain_manifest` | (none) | Return quality manifest |
| `brain_health` | (none) | Return health report |

## Configuring in Claude Code

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "gradata": {
      "command": "python",
      "args": ["-m", "gradata.mcp_server", "--brain-dir", "/path/to/brain"]
    }
  }
}
```

Then in Claude Code, the brain tools appear as available MCP tools. The AI can search your brain, log corrections, and check health directly.

## Configuring in Cursor

Add to your Cursor MCP configuration:

```json
{
  "mcpServers": {
    "gradata": {
      "command": "python",
      "args": ["-m", "gradata.mcp_server", "--brain-dir", "/path/to/brain"]
    }
  }
}
```

## Protocol Details

The MCP server implements:

- **Protocol version**: 2024-11-05
- **Transport**: stdio (stdin/stdout)
- **Framing**: HTTP-style `Content-Length` headers
- **Lifecycle**: `initialize` → `notifications/initialized` → tool calls → `shutdown`

## Using the MCP Bridge Programmatically

```python
from gradata.patterns.mcp import MCPBridge

bridge = MCPBridge("my-brain")  # string name, not Brain instance

# Handle an MCP tool call
result = bridge.handle_call("brain_search", {"query": "email tone"})
```

## Example: Brain-Augmented AI Workflow

1. User asks AI to draft an email
2. AI calls `brain_search` to find relevant patterns
3. AI calls `brain_manifest` to check brain maturity
4. AI generates draft using brain context
5. User edits the draft
6. AI calls `brain_correct` with draft and final
7. Next time, `brain_search` returns the learned patterns
