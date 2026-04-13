# Middleware

Middleware adapters wrap common LLM clients (OpenAI, Anthropic) and agent frameworks (LangChain, CrewAI) so Gradata can:

1. **Inject** graduated rules and meta-rules into the system prompt.
2. **Capture** the AI output for correction tracking.
3. **Observe** the conversation for fact extraction.

All adapters are non-destructive: they wrap the underlying client rather than subclass or monkeypatch it globally. If the brain directory is unavailable, adapters fall back to the original behavior — your app keeps working.

## OpenAI

`gradata.integrations.openai_adapter.patch_openai(client, brain_dir="./brain")`

```python
from openai import OpenAI
from gradata.integrations.openai_adapter import patch_openai

client = OpenAI()
client = patch_openai(client, brain_dir="./my-brain")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Draft an email to the CFO"}],
)
```

The patched `chat.completions.create()` automatically:

1. Calls `brain.apply_brain_rules(task)` with the user message as the task.
2. Prepends the resulting `<brain-rules>` block to the `messages` list as a system message.
3. Captures the conversation via `brain.observe()` for fact extraction.
4. Logs the assistant response via `brain.log_output()` so future corrections can be attributed.

## Anthropic

`gradata.integrations.anthropic_adapter.patch_anthropic(client, brain_dir="./brain")`

```python
from anthropic import Anthropic
from gradata.integrations.anthropic_adapter import patch_anthropic

client = Anthropic()
client = patch_anthropic(client, brain_dir="./my-brain")

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Draft an email to the CFO"}],
)
```

The patched `messages.create()` does the same three things. For Anthropic, brain rules are injected into the `system` parameter (not as a pseudo system message inside `messages`) so they count as proper system prompts.

## LangChain

`gradata.integrations.langchain_adapter.BrainMemory(brain_dir="./brain")`

Implements LangChain's `BaseMemory` interface.

```python
from langchain.chains import ConversationChain
from langchain_openai import ChatOpenAI
from gradata.integrations.langchain_adapter import BrainMemory

memory = BrainMemory(brain_dir="./my-brain")

chain = ConversationChain(
    llm=ChatOpenAI(model="gpt-4"),
    memory=memory,
)

chain.predict(input="Draft an email to the CFO")
```

`BrainMemory`:

- `memory_variables` — exposes `brain_rules` and `brain_facts` as prompt variables.
- `load_memory_variables(inputs)` — pulls relevant rules and facts for the current input.
- `save_context(inputs, outputs)` — logs the exchange and captures any implicit feedback.
- `clear()` — does not delete brain data, only clears in-memory cache.

## CrewAI

`gradata.integrations.crewai_adapter.BrainCrewMemory(brain_dir="./brain")`

Implements CrewAI's memory provider protocol.

```python
from crewai import Agent, Task, Crew
from gradata.integrations.crewai_adapter import BrainCrewMemory

memory = BrainCrewMemory(brain_dir="./my-brain")

researcher = Agent(
    role="Research Analyst",
    goal="Find relevant market data",
    backstory="Rigorous quantitative analyst",
    memory=memory,
)

crew = Crew(agents=[researcher], tasks=[...], memory=memory)
crew.kickoff()
```

`BrainCrewMemory`:

- `save(value, metadata=None, agent=None)` — persist an agent output.
- `search(query, limit=5)` — retrieve relevant memory entries.
- `reset()` — reset the in-memory cache.
- `get_rules(task, context=None)` — pull rules for a task (the injection call).

## MCP

For MCP-compatible hosts (Claude Code, Cursor, VS Code), use the MCP server directly instead of a Python adapter:

```bash
npx -y @gradata/mcp-installer --client claude
```

See [Claude Code Setup](../getting-started/claude-code.md).

## Custom integrations

If your LLM client is not supported, the pattern is the same for any wrapper:

```python
from gradata import Brain

brain = Brain("./my-brain")

def my_wrapped_call(user_message: str) -> str:
    # 1. Inject
    rules = brain.apply_brain_rules(user_message)
    system = f"{rules}\n\n{MY_BASE_SYSTEM_PROMPT}"

    # 2. Call your LLM
    response = llm.chat(system=system, user=user_message)

    # 3. Capture
    brain.log_output(response, output_type="chat")
    brain.observe([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": response},
    ])

    return response
```

When the user edits the response, call `brain.correct(draft=response, final=edited)` and the learning loop completes.

## Safety

All adapters:

- **Fail open.** If the brain is missing or corrupted, the underlying client runs normally. Errors are logged but not raised.
- **Are non-global.** `patch_openai(client)` patches the instance, not the module. Other OpenAI clients in the same process are untouched.
- **Respect PII scope.** The `observe()` pipeline honors the brain's taxonomy and drops fields tagged as PII.

See [Concepts → Corrections](../concepts/corrections.md) for what happens after capture.
