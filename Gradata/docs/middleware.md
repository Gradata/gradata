# Runtime Middleware Adapters

Gradata's hooks only fire inside Claude Code. For direct-SDK agents
(raw OpenAI SDK, raw Anthropic SDK, LangChain, CrewAI), the
`gradata.middleware` subpackage provides runtime wrappers that inject
learned rules into system prompts and optionally enforce RULE-tier regex
patterns on outputs.

## Common behavior

All adapters share one rule source: the same `lessons.md` + brain
database Claude Code hooks use. Selection, confidence floor, and the
`<brain-rules>` XML format match `gradata.hooks.inject_brain_rules`.

- **Cap**: 10 rules per call (configurable via `RuleSource(max_rules=N)`).
- **Priority**: RULE > PATTERN, ties broken by confidence descending.
- **Strict mode**: `strict=False` (default) logs violations; `strict=True`
  raises `gradata.middleware.RuleViolation` so callers can retry.
- **Kill switch**: set `GRADATA_BYPASS=1` to disable all injection and
  enforcement.
- **Optional deps**: importing `AnthropicMiddleware`, `OpenAIMiddleware`,
  `LangChainCallback`, or `CrewAIGuard` without their respective third-party
  package raises a clear `ImportError` with an install hint.

## Anthropic

```python
from anthropic import Anthropic
from gradata.middleware import wrap_anthropic

client = wrap_anthropic(Anthropic(), brain_path="./brain")
# ... all client.messages.create(...) calls now get rules injected
resp = client.messages.create(
    model="claude-sonnet-4-5",
    messages=[{"role": "user", "content": "Write a short greeting"}],
    max_tokens=128,
)
```

The wrapper mutates only the `system` kwarg (string or content-block
list) and post-checks the response's text blocks.

## OpenAI

```python
from openai import OpenAI
from gradata.middleware import wrap_openai

client = wrap_openai(OpenAI(), brain_path="./brain")
resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a short greeting"}],
)
```

Rules land in the leading system message — extending it if present,
prepending a new one otherwise.

## LangChain

```python
from langchain_openai import ChatOpenAI
from gradata.middleware import LangChainCallback

llm = ChatOpenAI(callbacks=[LangChainCallback(brain_path="./brain")])
llm.invoke("Write a short greeting")
```

Implements `BaseCallbackHandler` with hooks on
`on_llm_start` / `on_chat_model_start` for injection and `on_llm_end` for
enforcement.

## CrewAI

```python
from crewai import Agent
from gradata.middleware import CrewAIGuard

guard = CrewAIGuard(brain_path="./brain", strict=True)
agent = Agent(
    role="Writer",
    goal="Draft clean prose",
    backstory="...",
    guardrails=[guard],
)
```

The guard returns `(True, output)` when clean and
`(False, "Gradata rule violation(s): ...")` when strict and a RULE-tier
pattern matches — CrewAI then retries.

## Advanced: custom rule source

If your lessons live somewhere other than `<brain_path>/lessons.md`,
construct a `RuleSource` directly:

```python
from gradata.middleware import RuleSource, wrap_anthropic
from anthropic import Anthropic

source = RuleSource(
    lessons=[
        {"state": "RULE", "confidence": 0.95, "category": "TONE",
         "description": "Never use em dashes in prose"},
    ],
)
client = wrap_anthropic(Anthropic(), source=source, strict=True)
```
