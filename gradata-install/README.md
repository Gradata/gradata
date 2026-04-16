# gradata-install

> ⚠️ **Deprecated as of Gradata v0.6.** This npm wrapper is no longer the primary install path.
>
> Use the Python package directly:
>
> ```bash
> pip install gradata
> gradata hooks install
> ```
>
> This npm package remains published for backwards compatibility but will not receive new IDE integrations or feature updates. For Cursor, Codex, Gemini CLI, or Continue support, [open an issue](https://github.com/Gradata/gradata/issues) — we'll prioritize adding the installer to the main `gradata` Python package.

## Why the deprecation?

The Gradata SDK is a Python tool. A Python-ecosystem install path (`pip` / `pipx`) is the natural choice. Wrapping it in an npm package created:

- Two install paths competing for the same user journey
- An extra maintenance surface (Node version compat, npm audit warnings, semver coordination)
- Confusion about what's Python vs what's Node

One install, one mental model:

```bash
pip install gradata           # Install the SDK
gradata hooks install         # Wire up Claude Code hooks
```

## Historical usage (still works, not recommended)

```bash
npx gradata-install install --ide=claude-code
```

Under the hood this always did exactly two things:

1. `pip install gradata` (via pipx if available)
2. `gradata hooks install`

Running those two commands directly is equivalent and transparent.

## License

Apache-2.0 — matches the main Gradata SDK.
