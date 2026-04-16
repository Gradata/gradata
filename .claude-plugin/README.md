# Gradata — Claude Code Plugin

AI that learns your judgment. Every correction you make becomes a rule that sharpens future output.

## Prerequisites

This plugin is a thin wrapper around the Gradata Python SDK. You must install the SDK first:

```bash
# Python 3.11+ required
pipx install gradata
```

Verify the install before enabling the plugin:

```bash
python -m gradata --version
```

If `python` is not on your `PATH`, or maps to Python < 3.11, fix that first — the plugin's hooks shell out to `python -m gradata.hooks.*` and will fail silently otherwise.

## Install

```
/plugin marketplace add Gradata/gradata
/plugin install gradata
```

Claude Code will load four hooks on your next session:

| Event            | Hook                               | What it does |
| ---------------- | ---------------------------------- | ------------ |
| SessionStart     | `gradata.hooks.inject_brain_rules` | Injects graduated rules into session context |
| UserPromptSubmit | `gradata.hooks.context_inject`     | Injects brain context per user message |
| PostToolUse      | `gradata.hooks.auto_correct`       | Captures Edit/Write corrections as lessons |
| Stop             | `gradata.hooks.session_close`      | Emits SESSION_END + runs graduation sweep |

## Configure

Gradata stores its brain at `$GRADATA_BRAIN_DIR` if set, otherwise `./brain/` in the current working directory. To initialize a brain for the current project:

```bash
gradata init ./brain
```

To use a shared brain across projects:

```bash
export GRADATA_BRAIN_DIR=~/.gradata/default-brain
gradata init "$GRADATA_BRAIN_DIR"
```

Full SDK docs: https://gradata.ai

## Uninstall

```
/plugin uninstall gradata
```

This removes the hooks from your Claude Code session. Your brain data (corrections, lessons, rules) stays on disk at `$GRADATA_BRAIN_DIR`. To fully remove:

```bash
pipx uninstall gradata
rm -rf ./brain         # or $GRADATA_BRAIN_DIR
```

## Troubleshooting

**Nothing seems to happen.** The hooks fail silent by design so they never block Claude Code. Check:

```bash
python -m gradata.hooks.inject_brain_rules < /dev/null
```

If you see `ModuleNotFoundError: No module named 'gradata'`, `pipx install gradata` did not succeed or `python` is pointing at a different interpreter than the one pipx used. Run `pipx list` to see where Gradata lives, then ensure that interpreter is first on your `PATH`.

**Corrections are not being captured.** Only `Edit` and `Write` tool calls trigger `auto_correct`. Plain chat edits (without a tool call) are not captured yet.

**Rules are not being injected.** Rules only inject once they've graduated past the `PATTERN` threshold (0.60 confidence). Check graduation state:

```bash
gradata rules --all
```

New corrections start at `INSTINCT`. It takes repeated reinforcement before a rule reaches injection-eligible confidence.

**`python` not found on Windows.** Install Python 3.11+ from python.org and check "Add to PATH" during install, or use `py -m gradata.hooks.inject_brain_rules` and alias `python=py` in your shell profile.

**Where are my brain files?** Run `gradata doctor` — it prints the resolved brain directory, lesson count, and rule graduation histogram.

## Links

- SDK: https://pypi.org/project/gradata/
- Source: https://github.com/Gradata/gradata
- Docs: https://gradata.ai
- License: Apache-2.0
