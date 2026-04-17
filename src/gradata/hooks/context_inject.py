"""UserPromptSubmit hook: inject relevant brain context for user messages."""
from __future__ import annotations

from gradata.hooks._base import extract_message, resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "UserPromptSubmit",
    "profile": Profile.STANDARD,
    "timeout": 8000,
}

MIN_MESSAGE_LEN = 60  # skip brain search for trivial follow-ups ("ok", "yes", "continue")
MAX_CONTEXT_LEN = 2000


def main(data: dict) -> dict | None:
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
