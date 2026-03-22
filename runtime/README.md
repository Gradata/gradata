This directory contains platform-specific compiled output. Brain layer (brain/) is universal. Runtime layer (this) adapts to the target platform.

## carl-compiler.py

Reads CARL rules from `.carl/` and compiles them into platform-specific formats:

| Format | Output | Use case |
|--------|--------|----------|
| `claude` | `compiled/claude-rules.md` | Claude Code (CLAUDE.md style) |
| `cursor` | `compiled/.cursorrules` | Cursor IDE |
| `api` | `compiled/rules.json` | API system prompts |
| `markdown` | `compiled/rules.md` | Any markdown-reading agent |

```
python runtime/carl-compiler.py --format claude
python runtime/carl-compiler.py --format cursor
python runtime/carl-compiler.py --format api
python runtime/carl-compiler.py --format markdown
python runtime/carl-compiler.py --all
python runtime/carl-compiler.py --all --include-domain
python runtime/carl-compiler.py --stats
```

`--include-domain` adds domain/carl/ rules (sales-specific). Without it, only core .carl/ rules compile.
