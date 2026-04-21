"""UserPromptSubmit hook: inject relevant brain context for user messages."""

from __future__ import annotations

import json
import os
from pathlib import Path

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
MAX_CONTEXT_LEN = int(os.environ.get("GRADATA_MAX_CONTEXT_LEN", "800"))
# Reduce default top_k from 3→2: third result rarely changes decisions and
# costs ~48 tokens/turn in the typical scenario (2026-04-21 autoresearch).
CONTEXT_TOP_K = int(os.environ.get("GRADATA_CONTEXT_TOP_K", "2"))

# Jaccard threshold above which a snippet is considered a duplicate of an
# already-injected rule description. Override via GRADATA_CONTEXT_DEDUP_THRESHOLD.
_DEDUP_THRESHOLD = float(os.environ.get("GRADATA_CONTEXT_DEDUP_THRESHOLD", "0.70"))


def _jaccard(a: str, b: str) -> float:
    """Token-set Jaccard similarity between two strings (case-insensitive)."""
    ta, tb = set(a.lower().split()), set(b.lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _load_injected_descriptions(brain_dir: str) -> list[str]:
    """Return rule descriptions already injected via SessionStart (.last_injection.json)."""
    try:
        manifest_path = Path(brain_dir) / ".last_injection.json"
        if not manifest_path.is_file():
            return []
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        anchors = data.get("anchors", {})
        return [entry["description"] for entry in anchors.values() if entry.get("description")]
    except Exception:
        return []


def _is_duplicate(snippet: str, injected_descriptions: list[str], threshold: float) -> bool:
    """Return True if snippet overlaps with any injected description above threshold."""
    return any(_jaccard(snippet, desc) >= threshold for desc in injected_descriptions)


def _strip_frontmatter(text: str) -> str:
    """Strip YAML/TOML frontmatter (---...--- block) from the start of text.

    Frontmatter fields (type, pattern, personas, last_seen) carry no semantic
    signal for the LLM — only the content after the closing '---' matters.
    """
    if not text.startswith("---"):
        return text
    end = text.find("---", 3)
    if end == -1:
        return text
    return text[end + 3 :].lstrip()


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
            results = brain.search(message, top_k=CONTEXT_TOP_K)
        except Exception:
            return None

        if not results:
            return None

        # Dedup: load descriptions already injected in SessionStart and drop
        # snippets that substantially overlap. Gate via GRADATA_CONTEXT_DEDUP.
        dedup_enabled = os.environ.get("GRADATA_CONTEXT_DEDUP", "1") == "1"
        injected_descriptions: list[str] = (
            _load_injected_descriptions(brain_dir) if dedup_enabled else []
        )

        separator = "|"
        context_parts = []
        total_len = 0
        for r in results:
            text = r.get("text", "") or r.get("content", "") or str(r)
            text = _strip_frontmatter(text)
            snippet = text[:200]
            if dedup_enabled and _is_duplicate(snippet, injected_descriptions, _DEDUP_THRESHOLD):
                continue
            sep_cost = len(separator) if context_parts else 0
            if total_len + len(snippet) + sep_cost > MAX_CONTEXT_LEN:
                break
            context_parts.append(snippet)
            total_len += len(snippet) + sep_cost

        if not context_parts:
            return None

        joined = separator.join(context_parts)
        return {"result": f"ctx:{joined}"}
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
