"""Using Gradata alongside Claude Code.

With the Claude Code plugin installed (`/plugin install gradata`),
corrections on `Edit` / `Write` tool calls are captured automatically and
graduated rules are injected into every session. No code is needed in the
hot path.

This example is the manual equivalent: the same `Brain` API the hooks use,
run directly so you can inspect what gets stored and what would be injected.

Run:
    python examples/with_claude_code.py

See also: .claude-plugin/README.md for the zero-code install flow.
"""

from pathlib import Path

from gradata.brain import Brain

# Gradata resolves the brain directory from GRADATA_BRAIN_DIR, else ./brain/.
# Examples just use a local directory so this script is self-contained.
brain_dir = Path("./demo-brain")
brain_dir.mkdir(exist_ok=True)
(brain_dir / "lessons.md").touch()
brain = Brain(str(brain_dir))

# Simulate a correction that an Edit-tool call would trigger in Claude Code:
# the AI wrote one thing, you saved a different thing. The PostToolUse hook
# (gradata.hooks.auto_correct) calls brain.correct(draft=before, final=after).
brain.correct(
    draft="def foo(x): return x.bar",
    final='def foo(x): return getattr(x, "bar", None)',
)

# At the start of the next Claude Code session, gradata.hooks.inject_brain_rules
# runs this — the graduated rules get prepended to the system prompt.
rules_block = brain.apply_brain_rules("write a python helper")
print("--- Rules that would be injected ---")
print(rules_block or "(no rules have graduated yet — keep correcting)")

# Convergence check — the same number the hook's session_close emits.
conv = brain.convergence()
print(f"\nConvergence: {conv['trend']} ({conv['total_corrections']} corrections)")
