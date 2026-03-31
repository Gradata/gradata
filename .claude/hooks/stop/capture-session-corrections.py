#!/usr/bin/env python3
"""Session-end hook: capture corrections from the session note into brain.correct().

The wrap-up skill documents corrections in session notes as text:
    ## Corrections This Session
    1. Deal list included non-Oliver deals (wrong label)
    2. HingeSphere identified as prospect (actually a sending domain)

This hook parses those and calls brain.correct() for each one, which:
- Creates lesson entries in lessons.md
- Updates confidence for matching categories
- Logs correction events

This closes gap #1: session corrections → lesson pipeline.
"""
import os
import re
import sys
from pathlib import Path

BRAIN = Path(os.environ.get("BRAIN_DIR", "C:/Users/olive/SpritesWork/brain"))
SESSIONS_DIR = BRAIN / "sessions"

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


def find_latest_session_note() -> Path | None:
    """Find the most recently modified session note."""
    if not SESSIONS_DIR.is_dir():
        return None
    notes = sorted(SESSIONS_DIR.glob("202*-S*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if notes:
        return notes[0]
    # Also check loop-state.md which has corrections
    loop_state = SESSIONS_DIR / "loop-state.md"
    if loop_state.is_file():
        return loop_state
    return None


def extract_corrections(text: str) -> list[str]:
    """Extract correction descriptions from a session note.

    Looks for patterns like:
    ## Corrections This Session
    1. Description of correction
    2. Another correction
    - Bullet correction
    """
    corrections = []

    # Find corrections section
    patterns = [
        r"##\s*Corrections?\s*(?:This\s+Session|Logged)?.*?\n((?:(?:\d+\.|-|\*)\s+.+\n?)+)",
        r"##\s*What\s+Was\s+Corrected.*?\n((?:(?:\d+\.|-|\*)\s+.+\n?)+)",
    ]

    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            block = m.group(1)
            for line in block.splitlines():
                line = re.sub(r"^\s*(?:\d+\.|-|\*)\s+", "", line).strip()
                if line and len(line) > 10:  # Skip trivially short items
                    corrections.append(line)
            break

    return corrections


def main():
    note_path = find_latest_session_note()
    if not note_path:
        return

    text = note_path.read_text(encoding="utf-8")
    corrections = extract_corrections(text)
    if not corrections:
        return

    from gradata.brain import Brain
    brain = Brain(BRAIN)

    created = 0
    for correction_desc in corrections:
        try:
            # Use brain.correct() with the correction as the "final" text
            # and a generic "draft" since we don't have the original
            result = brain.correct(
                draft=f"AI produced output that needed correction: {correction_desc[:50]}",
                final=f"User corrected: {correction_desc}",
                category="SESSION_CORRECTION",
            )
            if result and result.get("lessons_created"):
                created += 1
        except Exception:
            pass  # Silent — don't block session end

    if created:
        print(f"Session corrections: {created} new lessons from {len(corrections)} corrections")


if __name__ == "__main__":
    main()
