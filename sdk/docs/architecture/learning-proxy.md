# Learning Proxy: Transparent Memory Router for Any LLM

**Status**: Design Doc
**Stolen from**: SuperMemory transparent proxy pattern
**Gradata twist**: Auto-detects corrections, injects graduated rules

## Overview

The Learning Proxy is a drop-in HTTP proxy that sits between any OpenAI-compatible client and any LLM provider. It intercepts conversations, detects corrections in real-time, and injects graduated rules into the system prompt. Zero code changes for the developer.

```
Developer's App                Learning Proxy              LLM Provider
      |                              |                          |
      |-- POST /v1/chat/completions ->|                         |
      |                              |-- detect corrections ----|
      |                              |-- inject rules ----------|
      |                              |-- POST /v1/chat/completions ->|
      |                              |<- response --------------|
      |<- response (unchanged) ------|                          |
```

## API Surface

### Drop-In Replacement

```python
# Before (direct OpenAI call):
client = OpenAI(base_url="https://api.openai.com/v1")

# After (learning proxy, one line changed):
client = OpenAI(base_url="http://localhost:6374/v1")
```

The proxy forwards all requests to the upstream provider, with two invisible additions:

1. **Rule injection**: Prepends graduated rules as a system message
2. **Correction detection**: Scans user messages for correction signals

### Proxy Configuration

```bash
# Minimal startup
gradata proxy --upstream https://api.openai.com/v1

# Full options
gradata proxy \
  --upstream https://api.openai.com/v1 \
  --brain-dir ./my-brain \
  --port 6374 \
  --max-rules 10 \
  --detect-corrections true \
  --api-key-passthrough true
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRADATA_UPSTREAM_URL` | `https://api.openai.com/v1` | Target LLM provider |
| `GRADATA_PROXY_PORT` | `6374` | Local proxy port |
| `BRAIN_DIR` | `./brain` | Brain directory path |
| `GRADATA_MAX_RULES` | `10` | Max rules injected per request |
| `GRADATA_DETECT_CORRECTIONS` | `true` | Enable passive correction detection |

## Request Flow (Detailed)

### 1. Intercept Request

```
Client -> POST /v1/chat/completions
{
  "model": "gpt-4",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Write me a cold email to a CTO"},
    {"role": "assistant", "content": "Subject: Revolutionize Your..."},
    {"role": "user", "content": "No, don't use 'revolutionize'. Make it shorter."}
  ]
}
```

### 2. Correction Detection (in proxy)

The proxy scans the latest user message for correction signals:

```python
# "No, don't use 'revolutionize'" matches:
#   - r"no[,.]?\s*(not\s+)?(that|this|like that)" -> partial
#   - r"don't\s+(do|use|include|add|write|say)"    -> MATCH (confidence 0.92)
#
# This is a correction of the previous assistant message.
# Draft = assistant's last message, Final = implied by user's instruction.
```

When a correction is detected:
- Extract the draft (previous assistant message)
- Log the correction event to the brain
- Compute edit distance / severity (deferred until final version arrives)

### 3. Rule Injection

Before forwarding, the proxy prepends graduated rules to the system message:

```
Original system message:
  "You are a helpful assistant."

Injected system message:
  "You are a helpful assistant.

  <brain-rules>
  [RULE:0.95] DRAFTING: Never use 'revolutionize', 'game-changing', or similar AI tells
  [RULE:0.92] FORMATTING: Use colons not em dashes in email prose
  [PATTERN:0.78] PROCESS: Always verify prospect identity before drafting
  </brain-rules>"
```

Rules are selected by:
1. Relevance to the current conversation topic (keyword matching against messages)
2. Confidence threshold (PATTERN 0.60+ and RULE 0.90+)
3. Max cap (default 10, configurable)

### 4. Forward to Upstream

The modified request (with rules injected) is forwarded to the upstream LLM provider. The response is returned to the client unmodified.

### 5. Response Logging

The proxy logs the assistant's response as an OUTPUT event for quality tracking.

## Correction Detection in the Proxy

The proxy uses `gradata.correction_detector.detect_correction()` to identify corrections in the conversation stream. Detection happens at two levels:

### Level 1: Single-Message Detection

Regex patterns match explicit correction language in the user's latest message. See `correction_detector.py` for the full signal list.

### Level 2: Conversational Context Detection

The proxy maintains a sliding window of the last 3 message pairs (user + assistant). It detects:

- **Rephrase corrections**: User restates what they want after the assistant got it wrong
- **Edit-and-resend**: User copies the assistant's output, modifies it, and sends it back (detected via high text similarity with edits)
- **Negation patterns**: "No", "Not like that", "Wrong" following an assistant message

### Deferred Correction Logging

Some corrections are implicit: the user says "make it shorter" but we don't have the final text yet. The proxy:

1. Logs a CORRECTION_SIGNAL event immediately (with confidence score)
2. When the next assistant response arrives, compares it to the original draft
3. If the new response differs significantly, logs a full CORRECTION with diff

## Deployment Options

### Local (Development)

```bash
pip install gradata
gradata proxy --upstream https://api.openai.com/v1 --brain-dir ./my-brain
```

Runs on localhost:6374. Best for individual developers.

### Docker (Team)

```dockerfile
FROM python:3.12-slim
RUN pip install gradata
ENV BRAIN_DIR=/data/brain
EXPOSE 6374
CMD ["gradata", "proxy", "--upstream", "https://api.openai.com/v1"]
```

Mount brain directory as a volume for persistence.

### Cloud (gradata.ai)

```bash
# One-liner setup: proxy runs in cloud, brain syncs automatically
gradata proxy --cloud --api-key grd_xxx
```

The cloud proxy:
- Runs on gradata.ai infrastructure (low latency, always-on)
- Syncs brain state bidirectionally
- Provides a dashboard at gradata.ai/dashboard
- Handles multi-user/team brains

### Sidecar (Kubernetes)

```yaml
containers:
  - name: app
    image: my-app:latest
    env:
      - name: OPENAI_BASE_URL
        value: "http://localhost:6374/v1"
  - name: gradata-proxy
    image: gradata/proxy:latest
    env:
      - name: GRADATA_UPSTREAM_URL
        value: "https://api.openai.com/v1"
      - name: BRAIN_DIR
        value: "/data/brain"
    volumeMounts:
      - name: brain-data
        mountPath: /data/brain
```

## Supported Endpoints

The proxy transparently forwards all OpenAI-compatible endpoints:

| Endpoint | Rule Injection | Correction Detection |
|----------|---------------|---------------------|
| `POST /v1/chat/completions` | Yes | Yes |
| `POST /v1/chat/completions` (streaming) | Yes | Yes (buffered) |
| `POST /v1/completions` | Yes (legacy) | No |
| `POST /v1/embeddings` | No (passthrough) | No |
| `*` (all other) | No (passthrough) | No |

## Streaming Support

For streaming responses (`stream: true`), the proxy:
1. Injects rules into the request before forwarding (no delay)
2. Streams the response back to the client in real-time (no buffering)
3. Accumulates the full response in background for correction detection
4. Logs the complete response after streaming finishes

## Security Considerations

- API keys are passed through to the upstream provider (never stored)
- Brain data stays local (unless `--cloud` mode is used)
- The proxy adds ~5ms latency per request (rule lookup + injection)
- No request/response data is sent to gradata.ai unless cloud mode is explicitly enabled

## Metrics Exposed

```
gradata_proxy_requests_total          # Total requests processed
gradata_proxy_corrections_detected    # Corrections auto-detected
gradata_proxy_rules_injected          # Rules injected per request (histogram)
gradata_proxy_latency_ms              # Proxy overhead latency
gradata_proxy_upstream_errors         # Upstream provider errors
```

## Comparison with SuperMemory Proxy

| Feature | SuperMemory | Gradata Learning Proxy |
|---------|-------------|----------------------|
| Drop-in proxy | Yes | Yes |
| Memory storage | Saves facts | Saves corrections + rules |
| Learning | Recall only | Graduation pipeline (INSTINCT -> RULE) |
| Context injection | Flat memory dump | Ranked rules with confidence scores |
| Contradiction detection | No | Yes (polarity, negation, sentiment) |
| Quality proof | No | brain.manifest.json with metrics |
| Multi-brain | No | Yes (A2A agent cards) |

## Implementation Plan

Phase 1: Core proxy with rule injection (2 days)
Phase 2: Correction detection in conversation stream (2 days)
Phase 3: Streaming support (1 day)
Phase 4: Cloud deployment option (3 days)
Phase 5: Dashboard integration (parallel with gradata.ai)
