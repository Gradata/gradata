"""UserPromptSubmit hook: inject relevant brain context for user messages."""

from __future__ import annotations

import os

from gradata.hooks._base import extract_message, resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "UserPromptSubmit",
    "profile": Profile.STANDARD,
    "timeout": 8000,
}

# Default threshold raised to 100: only substantive questions trigger a brain
# search. Ack-style replies ("ok", "sounds good", "continue where we left off")
# pass through without FTS cost. Override via GRADATA_MIN_MESSAGE_LEN.
MIN_MESSAGE_LEN = int(os.environ.get("GRADATA_MIN_MESSAGE_LEN", "100"))
MAX_CONTEXT_LEN = int(os.environ.get("GRADATA_MAX_CONTEXT_LEN", "2000"))


def main(data: dict) -> dict | None:
    # Kill-switch: GRADATA_CONTEXT_INJECT=0 disables brain context retrieval
    # entirely. Use when SessionStart rules + manual brain queries suffice.
    if os.environ.get("GRADATA_CONTEXT_INJECT", "1") != "1":
        return None
    try:
        message = extract_message(data)
        if not message:
            return None
        if len(message) < MIN_MESSAGE_LEN:
            return None
        if message.startswith("/"):
            return None

        brain_dir = resolve_brain_dir()
        if not brain_dir:
            return None

        try:
            from gradata.brain import Brain

            brain = Brain(brain_dir)
            results = brain.search(message, top_k=3)
        except Exception:
            return None

        if not results:
            return None

        separator = "\n---\n"
        context_parts = []
        total_len = 0
        for r in results:
            text = r.get("text", "") or r.get("content", "") or str(r)
            snippet = text[:500]
            sep_cost = len(separator) if context_parts else 0
            if total_len + len(snippet) + sep_cost > MAX_CONTEXT_LEN:
                break
            context_parts.append(snippet)
            total_len += len(snippet) + sep_cost

        if not context_parts:
            return None

        joined = separator.join(context_parts)
        return {"result": f"brain context: {joined}"}
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
