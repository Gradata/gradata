"""Brain-injection synthesis with inline rule anchors.

Two entry points:

* :func:`synthesize_rules_prompt` — category-grouped synthesis. Legacy.
* :func:`synthesize_brain_injection` — slot-grouped synthesis ordered by
  Preston Rhodes' 6-step prompt checklist (task → context → examples →
  persona → format → tone). Token-budgeted. This is the canonical
  session-start output.

Both preserve a 4-char ``r:xxxx`` anchor inline per rule so
``capture_learning.py`` can attribute a later user correction back to the
originating rule via token-overlap matching.

Output shape::

    SynthesizedPrompt(
        text="Task: keep diffs small r:a1f9. Tone: lead with empathy r:b2c3.",
        anchors_used=["a1f9", "b2c3"],
        anchor_to_rule_id={"a1f9": "a1f92b3c4d5e", ...},
    )
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SynthesizedPrompt:
    text: str
    anchors_used: list[str] = field(default_factory=list)
    anchor_to_rule_id: dict[str, str] = field(default_factory=dict)

    def token_count_estimate(self) -> int:
        """Rough estimate — one token per whitespace-delimited word."""
        return len(self.text.split())


# ---------------------------------------------------------------------------
# Slot inference (Preston Rhodes 6-step)
# ---------------------------------------------------------------------------

SLOT_ORDER: tuple[str, ...] = (
    "task",
    "context",
    "examples",
    "persona",
    "format",
    "tone",
)

SLOT_LABELS: dict[str, str] = {
    "task": "Task",
    "context": "Context",
    "examples": "Examples",
    "persona": "Persona",
    "format": "Format",
    "tone": "Tone",
}

_CATEGORY_SLOT: dict[str, str] = {
    "PROCESS": "task",
    "EXECUTION": "task",
    "EXECUTION-DISCIPLINE": "task",
    "EXECUTION_DISCIPLINE": "task",
    "WORKFLOW": "task",
    "CODE": "task",
    "ACCURACY": "context",
    "DATA-INTEGRITY": "context",
    "DATA_INTEGRITY": "context",
    "LEAD-HANDLING": "context",
    "LEAD_HANDLING": "context",
    "RESEARCH": "context",
    "SAFETY": "context",
    "DRAFTING": "format",
    "STRUCTURE": "format",
    "FORMAT": "format",
    "TONE": "tone",
    "VOICE": "tone",
    "PERSONA": "persona",
    "IDENTITY": "persona",
}
_DEFAULT_SLOT = "context"


def _get(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def classify_slot(item: Any) -> str:
    """Infer a Preston-Rhodes slot for a Lesson or rule-shaped dict.

    Resolution order: explicit ``slot`` → example-pair presence → category
    lookup → ``context`` catchall.
    """
    explicit = _get(item, "slot")
    if explicit:
        slot = str(explicit).strip().lower()
        if slot in SLOT_LABELS:
            return slot

    if _get(item, "example_draft") or _get(item, "example_corrected"):
        return "examples"

    cat = str(_get(item, "category") or "").strip().upper()
    if cat in _CATEGORY_SLOT:
        return _CATEGORY_SLOT[cat]
    cat_norm = cat.replace("-", "_")
    if cat_norm in _CATEGORY_SLOT:
        return _CATEGORY_SLOT[cat_norm]
    return _DEFAULT_SLOT


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _anchor_of(rule_id: str) -> str:
    """First 4 chars of the stable lesson id, matching inject_brain_rules."""
    return (rule_id or "")[:4]


def _clean_description(desc: str) -> str:
    """Strip common noise prefixes and trailing punctuation used elsewhere."""
    text = (desc or "").strip()
    for prefix in ("User corrected: ", "[AUTO] ", "[hooked] "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text.rstrip(".;,").strip()


def _rule_id_of(item: Any) -> str:
    for key in ("rule_id", "lesson_id", "id"):
        val = _get(item, key)
        if val:
            return str(val)
    return ""


def _as_rule_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return item
    return {
        "category": getattr(item, "category", "") or "",
        "description": getattr(item, "description", "") or "",
        "rule_id": _rule_id_of(item),
        "slot": getattr(item, "slot", "") or "",
        "example_draft": getattr(item, "example_draft", None),
        "example_corrected": getattr(item, "example_corrected", None),
    }


# ---------------------------------------------------------------------------
# Category-grouped synthesis (legacy, kept for back-compat)
# ---------------------------------------------------------------------------


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

    Legacy category-grouped form. New callers should prefer
    :func:`synthesize_brain_injection` which groups by Preston-Rhodes slot.
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


# ---------------------------------------------------------------------------
# Slot-grouped synthesis (canonical brain injection)
# ---------------------------------------------------------------------------


DEFAULT_BUDGET_TOKENS = 400
_PERSONA_BASELINE_CHARS = 800


def _budget_from_env(override: int | None) -> int:
    if override is not None and override > 0:
        return int(override)
    raw = os.environ.get("GRADATA_SYNTH_BUDGET", "").strip()
    if raw:
        try:
            val = int(raw)
            if val > 0:
                return val
        except ValueError:
            pass
    return DEFAULT_BUDGET_TOKENS


def _load_persona_baseline(source: str | Path | None) -> str:
    """Return a compact baseline string for the persona slot.

    Accepts a raw multi-line string, a path to a markdown file (e.g.
    ``domain/soul.md``), or None. Returns ``""`` on any read error.
    """
    if source is None:
        return ""
    if isinstance(source, str):
        return source.strip()[:_PERSONA_BASELINE_CHARS]
    if not isinstance(source, Path):
        return ""
    if not source.is_file():
        return ""
    try:
        text = source.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    lines = [
        ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith(("#", ">"))
    ]
    compact = " ".join(ln.strip().lstrip("*-").strip() for ln in lines)
    return compact[:_PERSONA_BASELINE_CHARS]


def synthesize_brain_injection(
    lessons: Iterable[Any],
    *,
    budget_tokens: int | None = None,
    max_per_slot: int = 3,
    persona_baseline: str | Path | None = None,
    llm_fn: Callable[[str], str] | None = None,
) -> SynthesizedPrompt:
    """Produce the single synthesized brain-injection prompt.

    Groups rules by :func:`classify_slot` into Preston-Rhodes 6-step order
    (task → context → examples → persona → format → tone). One sentence per
    non-empty slot. Token budget enforced by dropping lowest-priority slots
    first once the running total would exceed ``budget_tokens``.
    """
    budget = _budget_from_env(budget_tokens)
    baseline = _load_persona_baseline(persona_baseline)
    normalized = [_as_rule_dict(x) for x in lessons if x is not None]

    slot_items: dict[str, list[dict]] = {s: [] for s in SLOT_ORDER}
    for item in normalized:
        slot = classify_slot(item)
        slot_items.setdefault(slot, []).append(item)

    anchors_used: list[str] = []
    anchor_to_rule_id: dict[str, str] = {}
    sentences: list[tuple[str, str]] = []

    for slot in SLOT_ORDER:
        items = slot_items.get(slot, [])[:max_per_slot]
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

        if slot == "persona" and baseline:
            sentence = f"Persona: {baseline}"
            if clauses:
                sentence += ". Overrides: " + "; ".join(clauses)
            sentence += "."
            sentences.append((slot, sentence))
            continue

        if not clauses:
            continue
        label = SLOT_LABELS[slot]
        sentences.append((slot, f"{label}: " + "; ".join(clauses) + "."))

    def _render(pairs: list[tuple[str, str]]) -> str:
        return " ".join(s for _, s in pairs)

    while sentences and len(_render(sentences).split()) > budget:
        sentences.pop()

    text = _render(sentences)

    if _llm_enabled() and llm_fn is not None and text:
        text = _apply_llm(text, anchors_used, llm_fn)

    final_anchors = [a for a in anchors_used if f"r:{a}" in text or a in text]
    final_map = {a: anchor_to_rule_id[a] for a in final_anchors if a in anchor_to_rule_id}

    return SynthesizedPrompt(
        text=text,
        anchors_used=final_anchors,
        anchor_to_rule_id=final_map,
    )


# ---------------------------------------------------------------------------
# LLM hook + anchor helpers
# ---------------------------------------------------------------------------


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
    stripped = _ANCHOR_RE.sub("", template_text)
    try:
        new_text = llm_fn(stripped).strip()
    except Exception:
        return template_text

    if not new_text:
        return template_text

    refs = ",".join(anchors_used)
    return f"{new_text} [ref: {refs}]" if refs else new_text


def extract_anchors(text: str) -> list[str]:
    """Helper for live-hook attribution: pull all ``r:xxxx`` anchors from text."""
    if not text:
        return []
    anchors = _ANCHOR_RE.findall(text)
    sweep = re.search(r"\[ref:\s*([0-9a-f,\s]+)\]", text)
    if sweep:
        for tok in sweep.group(1).split(","):
            tok = tok.strip()
            if re.fullmatch(r"[0-9a-f]{4}", tok):
                anchors.append(tok)
    seen: set[str] = set()
    ordered: list[str] = []
    for a in anchors:
        if a not in seen:
            ordered.append(a)
            seen.add(a)
    return ordered
