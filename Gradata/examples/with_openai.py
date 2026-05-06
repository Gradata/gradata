"""Using Gradata with the raw OpenAI SDK via the middleware adapter.

`wrap_openai` transparently injects your graduated brain rules into every
`client.chat.completions.create(...)` call as a system message. Corrections
still flow through `brain.correct(...)` the usual way — the middleware is
read-only at call time.

Requires:  pip install gradata openai
"""

from pathlib import Path

from openai import OpenAI

from gradata.brain import Brain
from gradata.middleware import wrap_openai

# 1. A brain directory — same lessons.md + system.db that Claude Code hooks use.
brain_dir = Path("./demo-brain")
brain_dir.mkdir(exist_ok=True)
(brain_dir / "lessons.md").touch()
brain = Brain(str(brain_dir))

# Seed one correction so there's at least one rule to inject.
brain.correct(
    draft="We are pleased to inform you of our decision.",
    final="Hey, here's what we decided.",
)

# 2. Wrap an OpenAI client. No other code changes.
client = wrap_openai(OpenAI(), brain_path=str(brain_dir))

# 3. Use the client normally. Rules are injected as a system message.
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Draft a two-line update to the team."}],
)
print(response.choices[0].message.content)

# 4. When you edit the output, log the correction to keep learning.
# brain.correct(draft=response.choices[0].message.content, final=your_edit)
