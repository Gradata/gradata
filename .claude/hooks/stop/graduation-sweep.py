#!/usr/bin/env python3
"""Session-end hook: run graduation sweep on lessons.

Promotes lessons that survived the session (INSTINCT → PATTERN → RULE).
Demotes lessons that were contradicted. Kills untestable ones.

This is the core of the learning loop — without it, lessons never graduate.
"""
import os
import sys
from pathlib import Path

BRAIN = Path(os.environ.get("BRAIN_DIR", "C:/Users/olive/SpritesWork/brain"))

# Bootstrap SDK
scripts_dir = BRAIN / "scripts"
if scripts_dir.is_dir():
    sys.path.insert(0, str(scripts_dir))
    try:
        from paths import SDK_SRC
        sys.path.insert(0, str(SDK_SRC))
    except ImportError:
        wd = Path(os.environ.get("WORKING_DIR", "C:/Users/olive/OneDrive/Desktop/Sprites Work"))
        sys.path.insert(0, str(wd / "sdk" / "src"))

# Detect session number
session_num = 0
loop_state = BRAIN / "loop-state.md"
if loop_state.is_file():
    import re
    text = loop_state.read_text(encoding="utf-8")[:300]
    m = re.search(r"Session\s+(\d+)", text)
    if m:
        session_num = int(m.group(1))

# Detect session type from loop-state
session_type = "full"
if loop_state.is_file():
    text = loop_state.read_text(encoding="utf-8")[:500].lower()
    if "sales" in text or "pipeline" in text or "demo" in text:
        session_type = "sales"
    elif "system" in text or "sdk" in text or "architecture" in text:
        session_type = "systems"

from gradata.brain import Brain

brain = Brain(BRAIN)
result = brain.end_session(session_type=session_type)

promotions = result.get("promotions", 0)
demotions = result.get("demotions", 0)
total = result.get("lessons", 0)

if promotions or demotions:
    print(f"Graduation S{session_num}: {promotions} promoted, {demotions} demoted ({total} total)")
