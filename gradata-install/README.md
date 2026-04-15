# gradata-install

One command to install Gradata and wire it into your IDE.

## Usage

```bash
npx gradata-install install --ide=claude-code
```

No clone, no venv, no multi-step setup. This wrapper spawns the Python tooling that's already on your machine.

## Supported IDEs

- `claude-code` (default)
- `cursor`
- `codex`
- `gemini-cli`
- `continue`

## What it does

Transparent three-step flow:

1. Verifies Python >= 3.11 is installed (fails with exact install instructions for macOS/Linux/Windows if missing).
2. Installs the `gradata` Python package — prefers `pipx`, falls back to `pip install --user` if pipx isn't available.
3. Runs `gradata hooks install` to wire up your chosen IDE (correction capture, rule injection, status reporting).

This package is a thin Node shim. It does not bundle Python or any Gradata logic. All real work happens in the `gradata` Python package.

## Prerequisites

- Node.js >= 18 (you have this if you ran `npx`)
- Python >= 3.11 ([python.org/downloads](https://www.python.org/downloads/))
- `pipx` recommended ([pipx.pypa.io](https://pipx.pypa.io/)) for clean isolated installs

## After install

- Restart your IDE so it picks up the new hook.
- Verify with `gradata status`.
- Docs and source: [github.com/Gradata/gradata](https://github.com/Gradata/gradata).

## License

AGPL-3.0-or-later — same as the main Gradata project.
