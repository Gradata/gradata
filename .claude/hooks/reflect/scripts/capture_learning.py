#!/usr/bin/env python3
"""Detect and capture correction patterns from user prompts. UserPromptSubmit hook.

Cross-platform compatible (Windows, macOS, Linux).
This script is called by Claude Code's UserPromptSubmit hook to detect
correction patterns, positive feedback, and explicit "remember:" markers.
"""
import sys
import os
import json

# Fix Windows encoding for emoji output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.reflect_utils import (
    get_queue_path,
    load_queue,
    save_queue,
    detect_patterns,
    create_queue_item,
    should_include_message,
    MAX_CAPTURE_PROMPT_LENGTH,
)

# Patterns that indicate accuracy/hallucination issues (proxy detection)
HALLUCINATION_PATTERNS = {
    "dont-assume", "not-what-i-meant", "already-told",
}
HALLUCINATION_KEYWORDS = [
    r"wrong", r"incorrect", r"inaccurate", r"made.?up",
    r"hallucin", r"fabricat", r"doesn.?t exist", r"not real",
    r"that.?s not true", r"never said", r"misquot", r"wrong number",
    r"wrong.?data", r"stale.?data", r"outdated",
]


def emit_hallucination(prompt: str, matched_patterns: str, confidence: float):
    """Emit a HALLUCINATION event when accuracy-related correction detected."""
    try:
        import subprocess
        import re as _re
        python = "C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe"
        import json as _json
        data = _json.dumps({
            "trigger": matched_patterns,
            "confidence": confidence,
            "prompt_preview": prompt[:120],
            "detection_method": "correction_proxy",
        })
        tags = _json.dumps(["accuracy:correction_proxy"])
        subprocess.run(
            [python, "C:/Users/olive/SpritesWork/brain/scripts/events.py",
             "emit", "HALLUCINATION", "hook:capture_learning", data, tags],
            capture_output=True, text=True, timeout=5
        )
    except Exception:
        pass  # Non-blocking


def emit_correction(prompt: str, matched_patterns: str, confidence: float):
    """Emit a CORRECTION event when Oliver corrects output.

    This is the critical producer that feeds the entire self-improvement loop:
    update_confidence → lesson_applications → judgment_decay.
    """
    try:
        import subprocess
        import re as _re
        python = "C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe"
        import json as _json
        # Detect category from patterns (DRAFTING, PROCESS, ACCURACY, etc.)
        category = "GENERAL"
        category_map = {
            "dont-assume": "ACCURACY", "not-what-i-meant": "COMMUNICATION",
            "already-told": "PROCESS", "wrong-approach": "PROCESS",
            "too-verbose": "COMMUNICATION", "missed-context": "ACCURACY",
        }
        for pat in (matched_patterns or "").split():
            if pat in category_map:
                category = category_map[pat]
                break
        data = _json.dumps({
            "category": category,
            "detail": prompt[:200],
            "confidence": confidence,
            "patterns": matched_patterns,
        })
        tags = _json.dumps([f"category:{category}"])
        subprocess.run(
            [python, "C:/Users/olive/SpritesWork/brain/scripts/events.py",
             "emit", "CORRECTION", "hook:capture_learning", data, tags],
            capture_output=True, text=True, timeout=5
        )
    except Exception:
        pass  # Non-blocking


def main() -> int:
    """Main entry point."""
    # Read JSON from stdin
    input_data = sys.stdin.read()
    if not input_data:
        return 0

    try:
        data = json.loads(input_data)
    except json.JSONDecodeError:
        return 0

    # Extract prompt from JSON - handle different possible field names
    prompt = data.get("prompt") or data.get("message") or data.get("text")
    if not prompt:
        return 0

    # Filter out system content (XML tags, tool results, session continuations)
    if not should_include_message(prompt):
        return 0

    # Skip very long prompts — real user corrections are short.
    # Exception: explicit "remember:" markers are always processed.
    if len(prompt) > MAX_CAPTURE_PROMPT_LENGTH and "remember:" not in prompt.lower():
        return 0

    # Initialize queue if doesn't exist
    queue_path = get_queue_path()
    if not queue_path.exists():
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        queue_path.write_text("[]", encoding="utf-8")

    # Detect patterns
    item_type, patterns, confidence, sentiment, decay_days = detect_patterns(prompt)

    # If we found something, queue it
    if item_type:
        queue_item = create_queue_item(
            message=prompt,
            item_type=item_type,
            patterns=patterns,
            confidence=confidence,
            sentiment=sentiment,
            decay_days=decay_days,
        )

        items = load_queue()
        items.append(queue_item)
        save_queue(items)

        # Check if this correction is an accuracy/hallucination proxy
        import re as _re
        pattern_set = set(patterns.split()) if patterns else set()
        is_hallucination = bool(pattern_set & HALLUCINATION_PATTERNS)
        if not is_hallucination and sentiment == "correction":
            # Check for hallucination keywords in the prompt
            for kw in HALLUCINATION_KEYWORDS:
                if _re.search(kw, prompt, _re.IGNORECASE):
                    is_hallucination = True
                    break
        if is_hallucination:
            emit_hallucination(prompt, patterns, confidence)

        # Emit CORRECTION event for ALL corrections (not just hallucinations)
        # This feeds: update_confidence, lesson_applications, judgment_decay, validator checks
        if sentiment == "correction":
            emit_correction(prompt, patterns, confidence)

        # Output feedback for Claude to acknowledge the capture
        # UserPromptSubmit hooks with exit code 0 add stdout as context
        preview = prompt[:40] + "..." if len(prompt) > 40 else prompt
        print(f"📝 Learning captured: '{preview}' (confidence: {confidence:.0%})")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # Never block on errors - just log and exit 0
        print(f"Warning: capture_learning.py error: {e}", file=sys.stderr)
        sys.exit(0)
