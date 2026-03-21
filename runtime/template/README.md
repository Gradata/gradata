# Runtime Adapter: Template

Blank adapter for new platforms. Copy this directory and implement:

1. **paths.py** — Set BRAIN_DIR, DOMAIN_DIR, and tool locations for your platform
2. **rules file** — Equivalent of CLAUDE.md for your platform (.cursorrules, system prompt, etc.)
3. **hooks** — Event-driven automation (session start, tool failure, compaction) adapted to your platform
4. **commands** — Slash commands or equivalent interaction patterns

The brain/ directory is universal. Your adapter connects it to your specific AI tool.
