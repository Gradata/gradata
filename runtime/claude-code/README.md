# Runtime Adapter: Claude Code

This directory will contain all Claude Code-specific runtime bindings when SDK extraction begins.

## What moves here
- CLAUDE.md (master rules)
- .claude/hooks/ (event hooks)
- .claude/commands/ (slash commands)
- .claude/settings.json (permissions, plugins)
- brain/scripts/paths.py (platform paths)
- brain/scripts/start.py (launcher)
- brain/scripts/launch.py (pre-session validator)
- brain/scripts/create_shortcut.ps1 (desktop shortcut)

## What stays in /brain
- All markdown data (prospects, sessions, lessons, patterns)
- config.py (portable RAG config)
- embed.py (embedding pipeline)
- query.py (semantic search)
- requirements.txt (dependencies)
