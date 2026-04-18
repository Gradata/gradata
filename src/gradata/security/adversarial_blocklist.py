"""Lightweight adversarial-phrase blocklist for correction ingest.

Companion defence to ``correction_hash`` (A1 indirect prompt injection).
Scans correction text for canonical prompt-injection triggers and, on match,
flags the correction ``requires_review=True`` so the existing
``approval_required`` gate intercepts graduation.

Design choices:

* **Flag, do not reject.** Users legitimately write about these concepts
  (teaching a colleague, drafting a red-team report, documenting attacks).
  False positives are expected; the cost of a false positive is a one-click
  promote, the cost of a false negative is a persistent poisoned rule.
* **Case-insensitive, whitespace-tolerant substring match.** Low false
  negative rate, near-zero runtime cost. This is not a universal adversarial
  suffix detector — those transfer across models (Zou et al. 2023 GCG,
  https://arxiv.org/abs/2307.15043) and require embedding-based detection.
  The goal here is to catch obvious human-readable injection attempts in
  pasted text.
* **Seed list only.** The phrase list is intentionally small so it is
  auditable and extendable via configuration. Expansion should be data-driven
  once we observe misses in production.

References:
- Greshake et al. 2023, "Not What You've Signed Up For" (indirect prompt
  injection threat model). https://arxiv.org/abs/2302.12173
- Wallace et al. 2019, "Universal Adversarial Triggers for Attacking and
  Analyzing NLP" (transferable adversarial trigger sequences).
  https://arxiv.org/abs/1908.07125
- Perez & Ribeiro 2022, "Ignore Previous Prompt: Attack Techniques For
  Language Models" (goal hijacking & prompt leakage patterns).
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Seed phrase list
# ---------------------------------------------------------------------------
# Lowercase canonical forms. Match is case-insensitive and tolerant of
# collapsible whitespace runs (one or more spaces / tabs / newlines between
# tokens). Keep entries short and generic — we are optimising recall on
# obvious human-readable injections, not precision.

ADVERSARIAL_PHRASES: tuple[str, ...] = (
    # Classic prompt-injection openers (Perez & Ribeiro 2022 family)
    "ignore previous instructions",
    "ignore prior instructions",
    "ignore all previous",
    "ignore the above",
    "disregard your rules",
    "disregard previous",
    "forget previous instructions",
    "forget everything above",
    # Role hijack openers
    "you are now",
    "from now on you are",
    "act as if you",
    "pretend you are",
    "new role:",
    "new instructions:",
    # System-prompt leakage / manipulation
    "system prompt",
    "reveal your prompt",
    "show your instructions",
    "print your system",
    # Jailbreak jargon
    "jailbreak",
    "dan mode",
    "developer mode enabled",
    "do anything now",
    # Override hints
    "override previous",
    "override your",
    "bypass your",
)


_COMPILED_PATTERN: re.Pattern[str] = re.compile(
    "|".join(
        r"\s+".join(re.escape(tok) for tok in phrase.split())
        for phrase in ADVERSARIAL_PHRASES
    ),
    re.IGNORECASE,
)


def scan_for_adversarial_phrases(text: str) -> list[str]:
    """Return canonical forms of every adversarial phrase found in ``text``.

    Duplicates are collapsed. Order preserves first occurrence in the input.
    Empty or ``None``-ish inputs yield an empty list.
    """
    if not text:
        return []

    hits: list[str] = []
    seen: set[str] = set()
    for match in _COMPILED_PATTERN.finditer(text):
        # Normalize whitespace runs back to single spaces and lowercase for
        # canonical bucketing.
        canonical = re.sub(r"\s+", " ", match.group(0)).strip().lower()
        if canonical not in seen:
            seen.add(canonical)
            hits.append(canonical)
    return hits


def contains_adversarial_phrases(text: str) -> bool:
    """Boolean shortcut for callers that don't need the matched list."""
    if not text:
        return False
    return _COMPILED_PATTERN.search(text) is not None


def scan_correction(
    before_text: str | None,
    after_text: str | None,
) -> list[str]:
    """Scan both halves of a correction pair. Returns combined unique hits.

    We scan ``before`` as well as ``after`` because the attacker surface is the
    pasted content regardless of which side it lands on — e.g. a user could
    paste an injected email as the *draft* and lightly edit to produce the
    *final*, leaving the payload in before_text.
    """
    hits = scan_for_adversarial_phrases(before_text or "")
    for hit in scan_for_adversarial_phrases(after_text or ""):
        if hit not in hits:
            hits.append(hit)
    return hits
