"""UserPromptSubmit hook: inject relevant brain context for user messages."""
from __future__ import annotations

import os
from pathlib import Path

from gradata.hooks._base import run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "UserPromptSubmit",
    "profile": Profile.STANDARD,
    "timeout": 8000,
}

MIN_MESSAGE_LEN = 10
MAX_CONTEXT_LEN = 2000


def _resolve_brain_dir() -> str | None:
    brain_dir = os.environ.get("GRADATA_BRAIN_DIR") or os.environ.get("BRAIN_DIR")
    if brain_dir and Path(brain_dir).exists():
        return brain_dir
    default = Path.home() / ".gradata" / "brain"
    return str(default) if default.exists() else None


def _extract_message(data: dict) -> str | None:
    msg = data.get("message") or data.get("prompt") or data.get("content")
    if not msg or not isinstance(msg, str):
        return None
    msg = msg.strip()
    if len(msg) < MIN_MESSAGE_LEN:
        return None
    if msg.startswith("/"):
        return None
    return msg


def main(data: dict) -> dict | None:
    try:
        message = _extract_message(data)
        if not message:
            return None

        brain_dir = _resolve_brain_dir()
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

        context_parts = []
        total_len = 0
        for r in results:
            text = r.get("text", "") or r.get("content", "") or str(r)
            snippet = text[:500]
            if total_len + len(snippet) > MAX_CONTEXT_LEN:
                break
            context_parts.append(snippet)
            total_len += len(snippet)

        if not context_parts:
            return None

        joined = "\n---\n".join(context_parts)
        return {"result": f"brain context: {joined}"}
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
