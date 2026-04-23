"""Meta-Harness D — synthesized prompt injection with inline rule anchors.

Instead of injecting a flat list of 10-20 tagged rules and clusters, this
module collapses them into compact prose grouped by category. Each rule
still carries a 4-char anchor inline (``r:a1f9``) so the live hook
``capture_learning.py`` can attribute a later user correction to the
originating rule via token-overlap matching.

Two modes:

* **Template mode** (default) — deterministic, offline. Groups rules by
  category and emits one sentence per group with anchors preserved.
* **LLM mode** — ``GRADATA_SYNTHESIZE_WITH_LLM`` env var truthy. Calls
  ``synthesize_with_llm`` (provided by caller or no-op fallback) to produce
  natural prose; we re-insert anchors afterward so the caller's LLM doesn't
  need to know about them.

Output shape::

    SynthesizedPrompt(
        text="Drafting: never attribute quotes prospects didn't say r:a1f9; "
             "use writer+critic for sequences r:b2c3. Tone: start with empathy r:c3d4.",
        anchors_used=["a1f9", "b2c3", "c3d4"],
        anchor_to_rule_id={"a1f9": "a1f92b3c4d5e", ...},
    )
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field


@dataclass
class SynthesizedPrompt:
    text: str
    anchors_used: list[str] = field(default_factory=list)
    anchor_to_rule_id: dict[str, str] = field(default_factory=dict)

    def token_count_estimate(self) -> int:
        """Rough estimate — one token per whitespace-delimited word."""
        return len(self.text.split())


def _anchor_of(rule_id: str) -> str:
    """First 4 chars of the stable lesson id, matching inject_brain_rules."""
    return (rule_id or "")[:4]


def _clean_description(desc: str) -> str:
    """Strip common noise prefixes and trailing punctuation used elsewhere."""
    text = (desc or "").strip()
    for prefix in ("User corrected: ", "[AUTO] ", "[hooked] "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    # Remove trailing period so rule concatenation with ; reads cleanly.
    return text.rstrip(".;,").strip()


def _group_by_category(rules: Iterable[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for r in rules:
        cat = (r.get("category") or "GENERAL").upper()
        groups.setdefault(cat, []).append(r)
    return groups


def synthesize_rules_prompt(
    rules: list[dict],
    *,
    max_per_category: int = 4,
    llm_fn: Callable[[str], str] | None = None,
) -> SynthesizedPrompt:
    """Collapse a list of rules into a compact, anchor-preserving prompt.

    Args:
        rules: List of dicts with keys ``category``, ``description``,
            ``rule_id`` (full hex id). ``rule_id`` is used to derive the
            inline 4-char anchor.
        max_per_category: Cap on rules per category group so a dominant
            category can't drown out the rest.
        llm_fn: Optional callable that takes a template prompt and returns
            LLM-synthesized prose. Only consulted when
            ``GRADATA_SYNTHESIZE_WITH_LLM`` is truthy. Anchors are re-
            attached after the LLM returns — the LLM itself does not need
            to know about them.

    Returns:
        A :class:`SynthesizedPrompt`. Empty input → empty prompt.
    """
    if not rules:
        return SynthesizedPrompt(text="")

    groups = _group_by_category(rules)
    anchors_used: list[str] = []
    anchor_to_rule_id: dict[str, str] = {}
    sentences: list[str] = []

    for category in sorted(groups.keys()):
        items = groups[category][:max_per_category]
        clauses: list[str] = []
        for item in items:
            rule_id = item.get("rule_id") or ""
            anchor = _anchor_of(rule_id)
            desc = _clean_description(item.get("description", ""))
            if not desc:
                continue
            if anchor and anchor not in anchor_to_rule_id:
                anchors_used.append(anchor)
                anchor_to_rule_id[anchor] = rule_id
            suffix = f" r:{anchor}" if anchor else ""
            clauses.append(f"{desc}{suffix}")
        if not clauses:
            continue
        cat_label = category.replace("_", " ").title()
        sentences.append(f"{cat_label}: " + "; ".join(clauses) + ".")

    text = " ".join(sentences)

    if _llm_enabled() and llm_fn is not None and text:
        text = _apply_llm(text, anchors_used, llm_fn)

    return SynthesizedPrompt(
        text=text,
        anchors_used=anchors_used,
        anchor_to_rule_id=anchor_to_rule_id,
    )


def _llm_enabled() -> bool:
    return os.environ.get("GRADATA_SYNTHESIZE_WITH_LLM", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


_ANCHOR_RE = re.compile(r"(?<![0-9a-zA-Z])r:([0-9a-f]{4})")


def _apply_llm(
    template_text: str,
    anchors_used: list[str],
    llm_fn: Callable[[str], str],
) -> str:
    """Hand the anchor-stripped text to the LLM, then reattach anchors.

    The LLM produces prose. We attempt to match each anchor's original
    context word back into the new prose. If matching fails we append the
    anchors in a trailing sweep ``[ref: a1f9,b2c3]`` so attribution still
    works even when the LLM reshuffled clauses.
    """
    stripped = _ANCHOR_RE.sub("", template_text)
    try:
        new_text = llm_fn(stripped).strip()
    except Exception:
        return template_text  # fall back to the template on any LLM error

    if not new_text:
        return template_text

    # Conservative reattach: append a ref sweep so every anchor is present.
    refs = ",".join(anchors_used)
    return f"{new_text} [ref: {refs}]" if refs else new_text


def extract_anchors(text: str) -> list[str]:
    """Helper for live-hook attribution: pull all ``r:xxxx`` anchors from text."""
    if not text:
        return []
    anchors = _ANCHOR_RE.findall(text)
    # also catch trailing sweep [ref: a,b,c]
    sweep = re.search(r"\[ref:\s*([0-9a-f,\s]+)\]", text)
    if sweep:
        for tok in sweep.group(1).split(","):
            tok = tok.strip()
            if re.fullmatch(r"[0-9a-f]{4}", tok):
                anchors.append(tok)
    # dedup, preserve first-seen order
    seen: set[str] = set()
    ordered: list[str] = []
    for a in anchors:
        if a not in seen:
            ordered.append(a)
            seen.add(a)
    return ordered
