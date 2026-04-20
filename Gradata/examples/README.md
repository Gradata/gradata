# Gradata Examples

Each example is self-contained, < 50 lines, and runnable.

## basic_usage.py

Core learning loop: correct → learn → converge.

```bash
pip install gradata
python examples/basic_usage.py
```

Run it multiple times to see lessons graduate from INSTINCT to PATTERN.

## with_openai.py

Wrap the OpenAI SDK so graduated rules inject into every
`chat.completions.create(...)` call.

```bash
pip install gradata openai
python examples/with_openai.py
```

## with_claude_code.py

Manual walkthrough of what the Claude Code plugin does automatically —
same `Brain.correct()` / `Brain.apply_brain_rules()` API the hooks call.

```bash
pip install gradata
python examples/with_claude_code.py
```

For the zero-code install, see [.claude-plugin/README.md](../.claude-plugin/README.md).
