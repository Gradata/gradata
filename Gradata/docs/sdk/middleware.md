# Middleware

Gradata's hooks only fire inside Claude Code. For direct-SDK agents (raw OpenAI, raw Anthropic, LangChain, CrewAI) the `gradata.middleware` subpackage provides runtime wrappers that:

1. **Inject** graduated rules and meta-rules into the system prompt.
2. **Enforce** RULE-tier patterns on outputs via `check_output`.
3. **Fail open** — if the brain is unavailable or `GRADATA_BYPASS=1` is set, the underlying client runs normally.

All wrappers share a common `RuleSource` that reads the same `lessons.md` + brain database the Claude Code hooks use, so behaviour is consistent across environments.

## OpenAI

```python
from openai import OpenAI
from gradata.middleware import wrap_openai

client = wrap_openai(OpenAI(), brain_path="./my-brain")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Draft an email to the CFO"}],
)
```

`wrap_openai` patches the instance (not the module) so other OpenAI clients in the same process are untouched. Brain rules are prepended to `messages` as a system message, and the assistant response is passed through `check_output` before being returned.

## Anthropic

```python
from anthropic import Anthropic
from gradata.middleware import wrap_anthropic

client = wrap_anthropic(Anthropic(), brain_path="./my-brain")

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Draft an email to the CFO"}],
)
```

For Anthropic, brain rules are injected into the `system` parameter so they count as proper system prompts.

## LangChain

```python
from langchain_openai import ChatOpenAI
from gradata.middleware import LangChainCallback

callback = LangChainCallback(brain_path="./my-brain")

llm = ChatOpenAI(model="gpt-4", callbacks=[callback])
llm.invoke("Draft an email to the CFO")
```

`LangChainCallback` implements `BaseCallbackHandler` — attach it to any LangChain chain, agent, or LLM.

## CrewAI

```python
from crewai import Agent, Task, Crew
from gradata.middleware import CrewAIGuard

guard = CrewAIGuard(brain_path="./my-brain")

researcher = Agent(
    role="Research Analyst",
    goal="Find relevant market data",
    guardrail=guard,
)
```

`CrewAIGuard` plugs into CrewAI's standard guardrail protocol.

## MCP

For MCP-compatible hosts (Claude Code, Cursor, VS Code), use the MCP server directly instead of a Python wrapper:

```bash
npx -y @gradata/mcp-installer --client claude
```

See [Claude Code Setup](../getting-started/claude-code.md).

## Custom integrations

If your LLM client is not supported, the pattern is the same for any wrapper:

```python
from gradata import Brain
from gradata.middleware import RuleSource, check_output, build_brain_rules_block

brain = Brain("./my-brain")
source = RuleSource(brain_path="./my-brain")

def my_wrapped_call(user_message: str) -> str:
    rules = build_brain_rules_block(source.rules_for(user_message))
    system = f"{rules}\n\n{MY_BASE_SYSTEM_PROMPT}"

    response = llm.chat(system=system, user=user_message)

    check_output(response, source=source)  # raises RuleViolation on breach
    brain.log_output(response, output_type="chat")
    return response
```

When the user edits the response, call `brain.correct(draft=response, final=edited)` and the learning loop completes.

## Environment overrides

- `GRADATA_BYPASS=1` — disables all injection and enforcement (emergency kill switch).

## Optional dependencies

| Wrapper | Requires |
|---|---|
| `wrap_anthropic` / `AnthropicMiddleware` | `anthropic` |
| `wrap_openai` / `OpenAIMiddleware` | `openai` |
| `LangChainCallback` | `langchain-core` |
| `CrewAIGuard` | works with plain CrewAI guardrails |

Importing a wrapper without its optional dep raises a clear `ImportError` with the install hint.

See [Concepts → Corrections](../concepts/corrections.md) for what happens after capture.
