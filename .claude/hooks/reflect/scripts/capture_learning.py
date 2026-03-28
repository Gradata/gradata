#!/usr/bin/env python3
"""Detect and capture correction patterns from user prompts. UserPromptSubmit hook.

Cross-platform compatible (Windows, macOS, Linux).
This script is called by Claude Code's UserPromptSubmit hook to detect
correction patterns, positive feedback, and explicit "remember:" markers.
"""
import sys
import os
import json

# Skip in reviewer terminal — reviewer corrections are not training data
if os.environ.get("GRADATA_ROLE") == "reviewer":
    sys.exit(0)

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


BRAIN_DIR = os.environ.get("BRAIN_DIR", "C:/Users/olive/SpritesWork/brain")
PYTHON = os.environ.get("PYTHON_PATH", "C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe")
EVENTS_PY = os.path.join(BRAIN_DIR, "scripts", "events.py")

# Keyword taxonomy for correction classification.
# Each category maps to keywords that signal that type of correction.
# classify_correction() matches these in order; ORDER MATTERS — more specific
# categories must come before broad ones like ACCURACY that contain "wrong".
# GENERAL is the fallback when nothing matches.
CATEGORY_KEYWORDS = {
    # Specific structural categories first to prevent ACCURACY's "wrong" from
    # swallowing corrections that belong to a more precise bucket.
    "DATA_INTEGRITY": ["filter", "owner", "oliver only", "anna", "shared",
                       "duplicate", "overlap", "wrong person", "wrong deal"],
    "ARCHITECTURE": ["import", "module", "class", "function", "refactor",
                     "dependency", "structure", "script", "python", "def "],
    "TOOL": ["tool", "api", "mcp", "install", "config", "command", "endpoint",
             "token", "integration"],
    "LEADS": ["lead", "prospect", "enrich", "csv", "campaign", "instantly",
              "apollo", "linkedin", "icp"],
    "PRICING": ["price", "cost", "pricing", "monthly", "annual", "$",
                "starter", "standard", "plan"],
    "DEMO_PREP": ["demo", "cheat sheet", "battlecard", "prep"],
    "DRAFTING": ["email", "draft", "subject line", "follow-up", "copy",
                 "prose", "paragraph", "rewrite", "subject"],
    # CONTEXT before PROCESS: multi-word context-loading phrases (session type,
    # startup context) are more specific than bare "forgot"/"skip" and should
    # classify as CONTEXT, not generic PROCESS.
    "CONTEXT": ["session type", "startup context", "context window",
                "already know", "load context", "you loaded"],
    "PROCESS": ["skip", "forgot", "missing step", "workflow", "told you",
                "step", "order"],
    "THOROUGHNESS": ["incomplete", "all of them", "don't stop", "finish",
                     "remaining", "rest of", "the rest"],
    "POSITIONING": ["agency", "competitor", "frame", "position", "pitch",
                    "messaging", "value prop"],
    "COMMUNICATION": ["unclear", "ambiguous", "severity", "blocker",
                      "too verbose", "verbose", "too long", "confusing"],
    "TONE": ["tone", "aggressive", "pushy", "salesy", "formal", "casual",
             "softer", "harsh"],
    # ACCURACY is intentionally last among named categories — "wrong"/"incorrect"
    # are common words that would false-positive on more specific categories above.
    "ACCURACY": ["incorrect", "inaccurate", "verify", "hallucin", "fabricat",
                 "made up", "not real", "doesn't exist", "never said",
                 "misquot", "stale", "wrong number", "wrong data",
                 "wrong name", "wrong company"],
}


def classify_correction(text: str) -> str:
    """Classify a correction prompt into the learning taxonomy.

    Checks each category's keywords (case-insensitive, multi-line safe) in
    the order defined in CATEGORY_KEYWORDS. Returns the first matching category,
    or "GENERAL" if nothing matches.

    This is intentionally a fast heuristic — 10x better than labeling everything
    GENERAL, but not a perfect classifier.
    """
    import re as _re
    # Normalise: collapse whitespace so multi-line prompts match single-line patterns
    normalised = " ".join(text.split()).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in normalised:
                return category
    return "GENERAL"


def infer_session_task_types(text: str) -> list:
    """Infer which task types were active based on correction text content.

    Returns a list of task type strings that can be stored in the correction
    event metadata and used by wrap_up.py testability checks.
    """
    import re as _re
    normalised = " ".join(text.split()).lower()
    task_types = []

    TYPE_SIGNALS = {
        "sales": ["lead", "prospect", "pipeline", "deal", "pipedrive", "crm",
                  "campaign", "outreach", "sequence", "instantly"],
        "drafting": ["email", "draft", "subject", "follow-up", "copy", "prose",
                     "paragraph", "write"],
        "code": ["import", "module", "class", "function", "refactor", "script",
                 "python", "def ", "test", "pytest", "error", "traceback"],
        "demo_prep": ["demo", "cheat sheet", "battlecard", "meeting", "call"],
        "research": ["research", "enrich", "scrape", "apollo", "linkedin", "apify"],
        "system": ["hook", "event", "brain", "session", "config", "startup"],
    }

    for task_type, signals in TYPE_SIGNALS.items():
        if any(s in normalised for s in signals):
            task_types.append(task_type)

    return task_types if task_types else ["general"]


def emit_hallucination(prompt: str, matched_patterns: str, confidence: float):
    """Emit a HALLUCINATION event when accuracy-related correction detected."""
    try:
        import subprocess
        import re as _re
        import json as _json
        data = _json.dumps({
            "trigger": matched_patterns,
            "confidence": confidence,
            "prompt_preview": prompt[:120],
            "detection_method": "correction_proxy",
        })
        tags = _json.dumps(["accuracy:correction_proxy"])
        subprocess.run(
            [PYTHON, EVENTS_PY,
             "emit", "HALLUCINATION", "hook:capture_learning", data, tags],
            capture_output=True, text=True, timeout=5
        )
    except Exception:
        pass  # Non-blocking


def emit_correction(prompt: str, matched_patterns: str, confidence: float):
    """Emit a CORRECTION event when Oliver corrects output.

    This is the critical producer that feeds the entire self-improvement loop:
    update_confidence → lesson_applications → judgment_decay.

    Classification hierarchy:
    1. classify_correction() keyword taxonomy (14 categories) — primary
    2. pattern-name fallback for named guardrail/explicit patterns — secondary
    3. "GENERAL" — last resort when nothing matches
    """
    try:
        import subprocess
        import json as _json

        # Primary: full keyword-based classification against 14-category taxonomy
        category = classify_correction(prompt)

        # Secondary: if keyword classification returned GENERAL, check whether
        # the matched pattern name itself implies a known category (fast path for
        # explicit/guardrail hits that may use terse language)
        if category == "GENERAL":
            pattern_fallback = {
                "dont-assume": "ACCURACY",
                "not-what-i-meant": "COMMUNICATION",
                "already-told": "PROCESS",
                "wrong-approach": "PROCESS",
                "too-verbose": "COMMUNICATION",
                "missed-context": "ACCURACY",
            }
            for pat in (matched_patterns or "").split():
                if pat in pattern_fallback:
                    category = pattern_fallback[pat]
                    break

        # Task-type exposure: inferred from correction text, consumed by wrap_up.py
        session_task_types = infer_session_task_types(prompt)

        data = _json.dumps({
            "category": category,
            "detail": prompt[:200],
            "confidence": confidence,
            "patterns": matched_patterns,
            "session_task_types": session_task_types,
        })
        tags = _json.dumps([f"category:{category}"])
        subprocess.run(
            [PYTHON, EVENTS_PY,
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
