#!/usr/bin/env python3
"""Session-start hook: bridge memory feedback files into brain lessons.

This closes the gap between Anthropic's memory system (MEMORY.md + feedback_*.md)
and Gradata's graduation pipeline (lessons.md → INSTINCT → PATTERN → RULE).

Runs silently at session start. Only creates lessons for NEW feedback files
that don't already exist in lessons.md (idempotent).
"""
import sys
from pathlib import Path

# Bootstrap paths
BRAIN = Path(__file__).resolve().parents[3] / "../../SpritesWork/brain"
# Resolve properly for this machine
import os
BRAIN = Path(os.environ.get("BRAIN_DIR", "C:/Users/olive/SpritesWork/brain"))

# Find SDK source
scripts_dir = BRAIN / "scripts"
if scripts_dir.is_dir():
    sys.path.insert(0, str(scripts_dir))
    try:
        from paths import SDK_SRC
        sys.path.insert(0, str(SDK_SRC))
    except ImportError:
        # Fallback: find SDK relative to working dir
        wd = Path(os.environ.get("WORKING_DIR", "C:/Users/olive/OneDrive/Desktop/Sprites Work"))
        sys.path.insert(0, str(wd / "sdk" / "src"))

from gradata.enhancements.memory_bridge import bridge_memories_to_lessons

# Memory dir: the Claude Code project memory
# Derive from WORKING_DIR — Claude Code stores project memories under ~/.claude/projects/<escaped-path>/memory
WORKING_DIR = Path(os.environ.get("WORKING_DIR", "C:/Users/olive/OneDrive/Desktop/Sprites Work"))
_escaped = str(WORKING_DIR).replace("\\", "-").replace("/", "-").replace(":", "-").lstrip("-")
MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", str(Path.home() / ".claude" / "projects" / _escaped / "memory")))
LESSONS_PATH = BRAIN / "lessons.md"

if MEMORY_DIR.is_dir():
    result = bridge_memories_to_lessons(MEMORY_DIR, LESSONS_PATH)
    if result["created"] > 0:
        print(f"Memory bridge: {result['created']} new lessons from {result['scanned']} feedback files")
