# Cloud API Reference

## CloudClient

The cloud client handles all communication with Gradata Cloud.

### Constructor

```python
from gradata.cloud import CloudClient

client = CloudClient(
    brain_dir="./my-brain",
    api_key="pk_live_...",       # or set GRADATA_API_KEY env var
    endpoint="https://api.gradata.com/v1",  # default
)
```

You rarely construct this directly. Use `brain.connect_cloud()` instead.

### Methods

#### `client.connect()`

Authenticate and register the brain with the cloud. Returns `True` on success.

```python
success = client.connect()
```

#### `client.correct(draft, final, category, context, session)`

Send a correction to the cloud for server-side graduation.

```python
event = client.correct(
    draft="Original AI output...",
    final="User's edited version...",
    session=42,
)
```

Returns the same event dict format as local `Brain.correct()`.

#### `client.apply_rules(task, context)`

Get applicable rules from the cloud, enriched by cross-brain meta-learning.

```python
rules_text = client.apply_rules("email_draft", {"audience": "executive"})
```

Returns a formatted string for prompt injection.

#### `client.sync()`

Sync local brain state to cloud. Uploads new events since last sync.

```python
status = client.sync()
# {"status": "ok", "events_synced": 12, "rules_received": 3}
```

#### `client.marketplace_status()`

Check marketplace readiness.

```python
status = client.marketplace_status()
# {"eligible": True, "grade": "B+", "trust": "VERIFIED", "sessions": 87}
```

### Properties

#### `client.connected`

`True` if currently authenticated with the cloud.

---

## CloudConfig

Configuration management with 4-layer cascade.

```python
from gradata.cloud.config import CloudConfig

# Load config (merges all sources)
config = CloudConfig.load(brain_dir="./my-brain")

print(config.api_key)
print(config.endpoint)
print(config.auto_sync)

# Save config
config.save()                      # Global (~/.gradata/config.json)
config.save(brain_dir="./my-brain")  # Brain-local (.cloud.json)
```

### Config Resolution Order

1. Explicit arguments to `CloudClient()` (highest priority)
2. Environment variables (`GRADATA_API_KEY`, `GRADATA_ENDPOINT`)
3. Global config: `~/.gradata/config.json`
4. Brain-local config: `<brain_dir>/.cloud.json` (lowest priority)

### Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `api_key` | str | `""` | Gradata API key |
| `endpoint` | str | `https://api.gradata.com/v1` | Cloud API endpoint |
| `auto_sync` | bool | `true` | Sync at session boundaries |
| `sync_interval_minutes` | int | `30` | Background sync interval |
| `include_prospects` | bool | `false` | Sync prospect data to cloud |

---

## Brain Cloud Methods

These methods are added to the `Brain` class when the cloud module is available.

#### `brain.connect_cloud(api_key=None, endpoint=None)`

Connect to Gradata Cloud. Returns `self` for chaining.

```python
brain = Brain("./my-brain").connect_cloud()
```

#### `brain.cloud_connected`

Property. `True` if connected to the cloud.

---

## REST API Endpoints

The cloud client communicates with these endpoints:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/brains/connect` | Register brain + authenticate |
| POST | `/v1/brains/correct` | Submit correction for server-side graduation |
| POST | `/v1/brains/rules` | Get applicable rules (meta-learning enriched) |
| POST | `/v1/brains/sync` | Upload events, receive graduated rules |
| POST | `/v1/brains/marketplace-status` | Check listing eligibility |

All requests use `Bearer` token auth and JSON request/response bodies.
