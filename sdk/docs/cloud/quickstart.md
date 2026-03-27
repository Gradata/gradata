# Cloud Quick Start

Connect your brain to Gradata Cloud in under 2 minutes.

## 1. Get an API Key

Sign up at [gradata.com](https://gradata.com) and generate an API key from the dashboard.

## 2. Set Your Key

Option A: environment variable (recommended):

```bash
export GRADATA_API_KEY="pk_live_..."
```

Option B: global config file:

```bash
mkdir -p ~/.gradata
echo '{"api_key": "pk_live_..."}' > ~/.gradata/config.json
```

## 3. Connect Your Brain

```python
from gradata import Brain

brain = Brain("./my-brain")
brain.connect_cloud()

print(brain.cloud_connected)  # True
```

That's it. Now `brain.correct()` and `brain.apply_brain_rules()` route through the cloud automatically. If the cloud is unreachable, they fall back to local mode.

## 4. Verify Connection

```python
# Check cloud status
print(brain.cloud_connected)

# Sync manually (auto-sync happens at session start/end)
status = brain._cloud.sync()
print(status)

# Check marketplace readiness
readiness = brain._cloud.marketplace_status()
print(readiness)
```

## What Changes

| Operation | Before connect | After connect |
|-----------|---------------|---------------|
| `brain.correct()` | Local diff + classify | Cloud graduation + meta-learning |
| `brain.apply_brain_rules()` | Local lesson parsing | Cloud rules (enriched by cross-brain patterns) |
| `brain.search()` | No change | No change (always local) |
| `brain.emit()` | No change | No change (always local) |
| `brain.manifest()` | No change | No change (always local) |

Search, events, and manifest generation always run locally. Only the graduation pipeline and rule application route to the cloud.

## Configuration

Fine-tune sync behavior with a brain-local config:

```json
// .cloud.json in your brain directory
{
  "auto_sync": true,
  "sync_interval_minutes": 30,
  "include_prospects": false
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `auto_sync` | `true` | Sync at session start and end |
| `sync_interval_minutes` | `30` | Background sync interval |
| `include_prospects` | `false` | Whether to sync prospect data to cloud |

## MCP + Cloud

If you use the MCP server, connect to cloud in the server config:

```json
{
  "mcpServers": {
    "gradata": {
      "command": "python",
      "args": ["-m", "gradata.mcp_server", "--brain-dir", "/path/to/brain", "--cloud"],
      "env": {
        "GRADATA_API_KEY": "pk_live_..."
      }
    }
  }
}
```

The MCP server handles cloud connection automatically when `--cloud` is passed and the API key is set.
