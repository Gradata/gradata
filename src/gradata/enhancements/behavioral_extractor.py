"""
Behavioral Instruction Extractor — deterministic rule extraction from diffs.
============================================================================
SDK LAYER: Layer 1 (enhancements). Pure Python, no external dependencies.

Takes (draft, final, classification) and returns an actionable behavioral
instruction WITHOUT requiring an LLM.

Resolution order:
  1. Prefix stripping ("User corrected: ..." → return instruction directly)
  2. Archetype detection (sentence-level structural analysis)
  3. Template generation (archetype → imperative instruction)
  4. Keyword fallback (edit_classifier._INSTRUCTION_TEMPLATES)
  5. LLM hook (future — called when provider is connected)
  6. Generic fallback (category-based generic instruction)

Informed by MiroFish sim 26 research + prior art from Grammarly, Duolingo,
Google Smart Compose (sentence-level diffs > word-level for behavioral extraction).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata.enhancements.edit_classifier import EditClassification

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Archetype Taxonomy (12 correction types)
# ---------------------------------------------------------------------------

class Archetype(Enum):
    PREFIX_INSTRUCTION = auto()   # Already an instruction ("User corrected: ...")
    ADDITION_STEP = auto()        # New workflow step inserted
    REMOVAL_HEDGING = auto()      # Hedging/weak language removed
    REMOVAL_CONTENT = auto()      # Whole content block removed
    REPLACEMENT_WORD = auto()     # Specific word/phrase swap
    REPLACEMENT_TONE = auto()     # Formality/tone shift
    REPLACEMENT_FACTUAL = auto()  # Numbers/dates/URLs corrected
    REORDER = auto()              # Same content, different order
    FORMAT_CHANGE = auto()        # Structure changed (prose→list, etc.)
    TRUNCATION = auto()           # Significantly shortened (>35% reduction)
    EXPANSION = auto()            # Significantly expanded (>50% growth)
    CONSTRAINT_ADDITION = auto()  # New always/never/must rule


@dataclass
class ArchetypeMatch:
    archetype: Archetype
    confidence: float  # 0.0–1.0
    context: dict      # archetype-specific extracted data


# ---------------------------------------------------------------------------
# Detection vocabulary
# ---------------------------------------------------------------------------

# Multi-word hedge phrases for substring matching in raw text.
# Single-word hedges overlap with edit_classifier._TONE_WORDS (used for
# word-set classification). Both lists must be updated together.
_HEDGE_PHRASES = frozenset({
    "no rush", "no pressure", "if you want", "if you'd like",
    "when you get a chance", "at your convenience", "just",
    "maybe", "perhaps", "possibly", "i think", "i believe",
    "might", "could potentially", "sort of", "kind of",
    "not sure but", "feel free to", "no worries if not",
    "totally understand if", "let me know if",
})

_CONSTRAINT_WORDS = frozenset({
    "always", "never", "must", "don't", "do not",
    "required", "mandatory", "prohibited",
})

_ACTION_VERBS = frozenset({
    "check", "verify", "validate", "review", "audit", "test",
    "pull", "push", "run", "execute", "load", "import", "export",
    "create", "build", "deploy", "send", "submit", "approve",
    "research", "analyze", "compare", "confirm", "refresh",
    "open", "close", "start", "stop", "enable", "disable",
    "use", "avoid", "include", "exclude", "add", "remove",
})

_PREFIX_PATTERNS = [
    re.compile(r"^User corrected:\s*(.+)", re.IGNORECASE),
    re.compile(r'^Oliver:\s*["\u201c](.+?)["\u201d]', re.IGNORECASE),
    re.compile(r"^Correction:\s*(.+)", re.IGNORECASE),
    re.compile(r"^Rule:\s*(.+)", re.IGNORECASE),
    re.compile(r"^Fix:\s*(.+)", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Sentence-level helpers
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    """Split text into sentences at period/question/exclamation boundaries."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


def _sentence_overlap(a: str | set, b: str | set) -> float:
    """Word-level Jaccard overlap between two sentences.

    Accepts pre-computed word sets or raw strings.
    """
    a_words = a if isinstance(a, set) else set(a.lower().split())
    b_words = b if isinstance(b, set) else set(b.lower().split())
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / len(a_words | b_words)


def _contains_action_verb(sentence: str) -> bool:
    words = set(sentence.lower().split())
    return bool(words & _ACTION_VERBS)


def _extract_topic(sentences: list[str]) -> str:
    """Extract the main topic from a list of sentences (first noun-like phrase)."""
    if not sentences:
        return "content"
    text = sentences[0].strip()
    text = re.sub(r'^(the|a|an|this|that|we|i|you|it|please|also|then)\s+',
                  '', text, flags=re.IGNORECASE)
    words = text.split()[:6]
    return " ".join(words).rstrip(".,;:") if words else "content"


def _find_sentence_containing(text: str, word: str) -> str:
    for sent in _split_sentences(text):
        if word.lower() in sent.lower():
            return sent
    return text[:100]


def _to_imperative(sentence: str) -> str:
    """Convert a sentence to imperative mood.

    "You should check the data" → "Check the data"
    """
    s = sentence.strip().rstrip(".")
    prefixes = [
        r"^(you\s+)?(should|need\s+to|must|have\s+to|ought\s+to)\s+",
        r"^(we|i)\s+(should|need\s+to|must|have\s+to)\s+",
        r"^(it\s+is\s+)?(important|necessary|critical|essential)\s+(to\s+)?",
        r"^(make\s+sure\s+(to\s+)?)",
        r"^(remember\s+to\s+)",
        r"^(don'?t\s+forget\s+to\s+)",
        r"^(please\s+)",
    ]
    for prefix in prefixes:
        s = re.sub(prefix, "", s, flags=re.IGNORECASE).strip()
    if s:
        s = s[0].upper() + s[1:]
    return s


# ---------------------------------------------------------------------------
# Archetype Detection
# ---------------------------------------------------------------------------

def detect_archetype(
    draft: str,
    final: str,
    classification: EditClassification | None = None,
) -> ArchetypeMatch:
    """Detect the primary correction archetype from draft→final.

    Analyzes at sentence granularity, not word level.
    """
    # 1. PREFIX_INSTRUCTION: already a rule
    for pattern in _PREFIX_PATTERNS:
        m = pattern.match(final.strip())
        if m:
            return ArchetypeMatch(
                Archetype.PREFIX_INSTRUCTION, 1.0,
                {"instruction": m.group(1).strip()}
            )

    draft_sents = _split_sentences(draft)
    final_sents = _split_sentences(final)
    draft_words = set(draft.lower().split())
    final_words = set(final.lower().split())
    added_words = final_words - draft_words
    removed_words = draft_words - final_words

    # Precompute word sets for sentence overlap (avoids re-splitting per pair)
    draft_sent_sets = [set(s.lower().split()) for s in draft_sents]
    final_sent_sets = [set(s.lower().split()) for s in final_sents]
    added_sents = [s for s, ws in zip(final_sents, final_sent_sets)
                   if not any(_sentence_overlap(ws, ds) > 0.5 for ds in draft_sent_sets)]

    # 2. REMOVAL_HEDGING (check BEFORE length — hedging removal shortens text)
    removed_hedges = [h for h in _HEDGE_PHRASES
                      if h in draft.lower() and h not in final.lower()]
    if removed_hedges:
        return ArchetypeMatch(
            Archetype.REMOVAL_HEDGING, 0.90,
            {"removed_phrases": removed_hedges}
        )

    # 3. CONSTRAINT_ADDITION (check BEFORE length — constraints lengthen text)
    new_constraints = [w for w in _CONSTRAINT_WORDS
                       if w in final.lower() and w not in draft.lower()]
    if new_constraints:
        constraint_sent = _find_sentence_containing(final, new_constraints[0])
        return ArchetypeMatch(
            Archetype.CONSTRAINT_ADDITION, 0.85,
            {"constraint_word": new_constraints[0],
             "constraint_sentence": constraint_sent}
        )

    # 4. ADDITION_STEP: new sentences with action verbs (before length check)
    if added_sents and _contains_action_verb(added_sents[0]):
        return ArchetypeMatch(
            Archetype.ADDITION_STEP, 0.80,
            {"added_step": added_sents[0]}
        )

    # 5. REPLACEMENT_TONE (uses classifier output, before length check)
    if classification:
        desc_lower = classification.description.lower()
        if "casualized" in desc_lower or "formalized" in desc_lower:
            direction = "casual" if "casualized" in desc_lower else "formal"
            return ArchetypeMatch(
                Archetype.REPLACEMENT_TONE, 0.85,
                {"direction": direction}
            )

    # 6. TRUNCATION / EXPANSION (generic length change — after specific checks)
    len_ratio = len(final) / max(len(draft), 1)
    if len_ratio < 0.65:
        removed_sents = [s for s, ws in zip(draft_sents, draft_sent_sets)
                         if not any(_sentence_overlap(ws, fs) > 0.5 for fs in final_sent_sets)]
        topic = _extract_topic(removed_sents) if removed_sents else "content"
        return ArchetypeMatch(
            Archetype.TRUNCATION, 0.85,
            {"reduction_pct": round((1 - len_ratio) * 100), "removed_topic": topic}
        )
    if len_ratio > 1.5:
        topic = _extract_topic(added_sents) if added_sents else "detail"
        return ArchetypeMatch(
            Archetype.EXPANSION, 0.80,
            {"growth_pct": round((len_ratio - 1) * 100), "added_topic": topic}
        )

    # 7. REORDER: same words, different arrangement
    if draft_words == final_words and draft != final:
        return ArchetypeMatch(Archetype.REORDER, 0.85, {})

    # 8. REPLACEMENT_FACTUAL (reuse regex from edit_classifier)
    from gradata.enhancements.edit_classifier import _FACTUAL_RE
    old_facts = set(_FACTUAL_RE.findall(draft))
    new_facts = set(_FACTUAL_RE.findall(final))
    if old_facts != new_facts and (old_facts or new_facts):
        return ArchetypeMatch(
            Archetype.REPLACEMENT_FACTUAL, 0.85,
            {"old_facts": list(old_facts), "new_facts": list(new_facts)}
        )

    # 9. FORMAT_CHANGE
    old_has_list = bool(re.search(r'^\s*[-*+]\s', draft, re.MULTILINE))
    new_has_list = bool(re.search(r'^\s*[-*+]\s', final, re.MULTILINE))
    if old_has_list != new_has_list:
        return ArchetypeMatch(
            Archetype.FORMAT_CHANGE, 0.80,
            {"old_format": "list" if old_has_list else "prose",
             "new_format": "list" if new_has_list else "prose"}
        )

    # 10. REMOVAL_CONTENT
    removed_sents = [s for s, ws in zip(draft_sents, draft_sent_sets)
                     if not any(_sentence_overlap(ws, fs) > 0.5 for fs in final_sent_sets)]
    if removed_sents and not added_sents:
        topic = _extract_topic(removed_sents)
        return ArchetypeMatch(
            Archetype.REMOVAL_CONTENT, 0.75,
            {"removed_topic": topic}
        )

    # 11. REPLACEMENT_WORD
    if len(added_words) <= 3 and len(removed_words) <= 3 and added_words and removed_words:
        return ArchetypeMatch(
            Archetype.REPLACEMENT_WORD, 0.80,
            {"old_words": sorted(removed_words)[:3],
             "new_words": sorted(added_words)[:3]}
        )

    # 12. Fallback: any new sentences
    if added_sents:
        return ArchetypeMatch(
            Archetype.ADDITION_STEP, 0.60,
            {"added_step": added_sents[0]}
        )

    # Ultimate fallback
    return ArchetypeMatch(
        Archetype.REPLACEMENT_WORD, 0.40,
        {"old_words": sorted(removed_words)[:3],
         "new_words": sorted(added_words)[:3]}
    )


# ---------------------------------------------------------------------------
# Template Generation
# ---------------------------------------------------------------------------

def generate_instruction(match: ArchetypeMatch, category: str = "") -> str:
    """Generate an imperative behavioral instruction from an archetype match."""
    ctx = match.context
    a = match.archetype

    if a == Archetype.PREFIX_INSTRUCTION:
        return ctx["instruction"]

    if a == Archetype.REMOVAL_HEDGING:
        phrases = ctx["removed_phrases"][:3]
        quoted = ", ".join(f"'{p}'" for p in phrases)
        return f"Don't use hedging language like {quoted}"

    if a == Archetype.CONSTRAINT_ADDITION:
        sent = ctx.get("constraint_sentence", "")
        if sent:
            return _to_imperative(sent)
        return f"{ctx['constraint_word'].capitalize()} follow this constraint"

    if a == Archetype.ADDITION_STEP:
        step = ctx["added_step"]
        imperative = _to_imperative(step)
        if not imperative.lower().startswith(("always", "never", "don't")):
            return f"Always {imperative[0].lower()}{imperative[1:]}"
        return imperative

    if a == Archetype.REMOVAL_CONTENT:
        topic = ctx.get("removed_topic", "that content")
        return f"Don't include {topic}"

    if a == Archetype.REPLACEMENT_WORD:
        old = ctx.get("old_words", [])
        new = ctx.get("new_words", [])
        if old and new:
            return f"Use '{', '.join(new)}' instead of '{', '.join(old)}'"
        if new:
            return f"Include '{', '.join(new)}'"
        if old:
            return f"Don't use '{', '.join(old)}'"
        return "Revise wording"

    if a == Archetype.REPLACEMENT_TONE:
        direction = ctx.get("direction", "appropriate")
        return f"Write in a {direction} tone"

    if a == Archetype.REPLACEMENT_FACTUAL:
        return "Verify facts, numbers, and dates before including them"

    if a == Archetype.REORDER:
        return "Present information in a more logical order"

    if a == Archetype.FORMAT_CHANGE:
        new_fmt = ctx.get("new_format", "the preferred format")
        old_fmt = ctx.get("old_format", "the current format")
        return f"Use {new_fmt} instead of {old_fmt}"

    if a == Archetype.TRUNCATION:
        pct = ctx.get("reduction_pct", 30)
        topic = ctx.get("removed_topic", "")
        if topic and topic != "content":
            return f"Keep it concise — cut {topic}"
        return f"Be more concise — the draft was ~{pct}% too long"

    if a == Archetype.EXPANSION:
        topic = ctx.get("added_topic", "relevant details")
        return f"Include more detail about {topic}"

    return "Revise this type of output"


# ---------------------------------------------------------------------------
# Quality Gate
# ---------------------------------------------------------------------------

_IMPERATIVE_STARTERS = frozenset({
    "use", "don", "always", "never", "include", "exclude",
    "check", "verify", "write", "keep", "cut", "add",
    "remove", "present", "be", "avoid", "ensure", "start",
    "lead", "break", "replace", "run", "test", "audit",
    "research", "validate", "pull", "load", "revise",
})

_GENERIC_FALLBACKS = {
    "TONE": "Adjust tone to match the context",
    "CONTENT": "Revise content to be more accurate and relevant",
    "STRUCTURE": "Improve the organization and structure",
    "FACTUAL": "Verify all facts, numbers, and dates",
    "STYLE": "Follow the established style conventions",
    "PROCESS": "Follow the correct workflow sequence",
    "DRAFTING": "Improve the writing quality",
    "LEADS": "Follow lead handling procedures",
    "CODE": "Follow coding best practices",
}


def _is_actionable(instruction: str) -> bool:
    if not instruction or len(instruction) < 5:
        return False
    first_word = instruction.split()[0].lower().removesuffix("'t")
    return first_word in _IMPERATIVE_STARTERS


def _try_llm_extract(llm_provider, draft: str, final: str, classification) -> str | None:
    """Try LLM extraction, return result or None on failure."""
    if llm_provider is None:
        return None
    try:
        # Build a prompt from the correction context
        category = classification.category if classification else "UNKNOWN"
        prompt = (
            f"Extract an actionable behavioral instruction from this correction:\n\n"
            f"Draft: {draft}\n\n"
            f"Final: {final}\n\n"
            f"Category: {category}\n\n"
            f"Return a single imperative instruction (e.g., 'Always X', 'Don't Y', 'Use Z instead of W')."
        )

        # Call complete() with appropriate parameters
        refined = llm_provider.complete(prompt, max_tokens=100, timeout=10)

        if refined and _is_actionable(refined):
            return refined
    except Exception as exc:
        _log.warning(
            "LLM extraction failed for category=%s: %s",
            classification.category if classification else "UNKNOWN",
            exc
        )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_instruction(
    draft: str,
    final: str,
    classification: EditClassification | None = None,
    *,
    category: str = "",
    llm_provider=None,
) -> str | None:
    """Main entry point. Returns an actionable behavioral instruction.

    Resolution:
      1. Archetype detection + template (sentence-level, deterministic)
      2. Quality gate (must be imperative)
      3. LLM refinement (when provider connected, for low-confidence matches)
      4. Generic category-based fallback

    Args:
        draft: Original AI output
        final: User's corrected version
        classification: EditClassification from edit_classifier (optional)
        category: Correction category (DRAFTING, PROCESS, etc.)
        llm_provider: Optional LLM provider for refinement of low-confidence matches.
                      Interface: llm_provider.extract(draft, final, classification) -> str

    Returns:
        Actionable behavioral instruction, or None if extraction fails.
    """
    match = detect_archetype(draft, final, classification)
    instruction = generate_instruction(match, category)

    if instruction and _is_actionable(instruction):
        # LLM HOOK: refine low-confidence extractions when provider connected
        if match.confidence < 0.60:
            refined = _try_llm_extract(llm_provider, draft, final, classification)
            if refined:
                return refined
        return instruction

    # LLM HOOK: full extraction for failed archetype detection
    refined = _try_llm_extract(llm_provider, draft, final, classification)
    if refined:
        return refined

    # Generic fallback
    cat = category or (classification.category if classification else "")
    return _GENERIC_FALLBACKS.get(cat.upper())