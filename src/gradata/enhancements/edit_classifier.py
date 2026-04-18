"""
Edit Classifier — 5-category classification of text diffs.
===========================================================
SDK LAYER: Layer 1 (enhancements). Pure Python heuristics.

Classifies changed sections from a DiffResult into:
  FACTUAL   — numbers, dates, names, URLs changed
  STYLE     — punctuation, formatting (em dashes, bold, colons)
  STRUCTURE — reordering, line breaks, heading/list changes
  TONE      — hedging words, formality shift (formal↔casual), sentiment markers
  PROCESS   — behavioral/workflow corrections (always/never/first/before patterns)
  CONTENT   — substantive information (default for anything else)
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .diff_engine import DiffResult
    from .instruction_cache import InstructionCache


@dataclass
class EditClassification:
    """A single classified edit from a diff."""
    category: str       # TONE | CONTENT | STRUCTURE | FACTUAL | STYLE
    confidence: float   # 0.0-1.0
    severity: str       # inherited from DiffResult.severity
    description: str    # human-readable summary


# ---------------------------------------------------------------------------
# Heuristic keyword sets
# ---------------------------------------------------------------------------

# Factual tokens: dollar amounts, ISO dates, percentages, URLs, 3+-digit numbers.
# NOTE: detection/intent_classifier.py defines its own _FACTUAL_RE as a list of
# separate compiled patterns (iterated with `for pat in _FACTUAL_RE`). Types are
# incompatible — keep them separate.
_FACTUAL_RE = re.compile(
    r"(\$[\d,.]+|\d{4}-\d{2}-\d{2}|\d+%|https?://\S+|\b\d{3,}\b)"
)

# Common English function words for edit-diff filtering.
# NOTE: enhancements/similarity.py extends this list with NLP-specific terms
# ("change", "added", "cut", etc.) that would corrupt _meaningful_words if merged.
_STOP_WORDS: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "can", "could", "might", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "that",
    "this", "it", "its", "and", "or", "but", "not", "no", "if", "so",
    "than", "too", "very", "s", "t", "d", "ll", "ve", "re", "m",
    "i", "you", "we", "they", "he", "she", "me", "my", "your", "our",
    "their", "his", "her", "us", "them", "up", "out", "all", "am",
}

_TONE_WORDS = {
    "actually", "just", "really", "basically", "honestly",
    "perhaps", "maybe", "possibly", "might", "could",
    "I think", "I believe", "I feel", "in my opinion",
    "very", "extremely", "quite", "rather", "somewhat",
    "sorry", "unfortunately", "please", "kindly",
}

# Formality markers: presence in old but not new = casualized, vice versa = formalized
_FORMAL_MARKERS = {
    "dear", "sir", "madam", "hereby", "pursuant", "kindly", "henceforth",
    "sincerely", "regards", "esteemed", "valued", "cordially", "formally",
    "respectively", "herewith", "aforementioned", "earliest convenience",
    "we would be delighted", "we are pleased", "we appreciate your",
    "it is my pleasure", "do not hesitate",
}
_CASUAL_MARKERS = {
    "hey", "hi", "yo", "quick", "btw", "fyi", "gonna", "wanna",
    "cool", "awesome", "nice", "thanks", "cheers", "lol", "asap",
    "hop on", "chat", "catch up", "touch base", "ping",
}

# Process/behavioral correction markers
_PROCESS_WORDS = {
    "first", "before", "after", "then", "always", "never", "must",
    "step", "workflow", "process", "checklist", "gate", "verify",
    "plan", "review", "approve", "check", "validate", "research",
    "pull", "extract", "transcript", "adversary", "audit",
    "pipeline", "sequence", "order", "prerequisite",
}

_STRUCTURE_MARKERS = re.compile(
    r"^(\s*[-*+]\s|\s*\d+[.)]\s|\s*#{1,6}\s|</?[a-z])", re.MULTILINE
)



def _word_set(text: str) -> set[str]:
    """Extract lowercase words from text."""
    return set(re.findall(r"\b[a-z]+\b", text.lower()))


def _meaningful_words(words: set[str]) -> list[str]:
    """Filter to meaningful words (no stop words), sorted by length desc."""
    return sorted(
        (w for w in words if w not in _STOP_WORDS and len(w) > 2),
        key=len, reverse=True,
    )


def _classify_section(old_text: str, new_text: str, severity: str) -> list[EditClassification]:
    """Classify a single changed section. Returns ALL applicable categories."""
    old_lower = old_text.lower()
    new_lower = new_text.lower()
    old_words = _word_set(old_text)
    new_words = _word_set(new_text)
    results: list[EditClassification] = []

    # FACTUAL: numbers, dates, URLs changed
    old_facts = set(_FACTUAL_RE.findall(old_text))
    new_facts = set(_FACTUAL_RE.findall(new_text))
    if old_facts != new_facts and (old_facts or new_facts):
        changed = (old_facts - new_facts) | (new_facts - old_facts)
        results.append(EditClassification(
            category="FACTUAL",
            confidence=0.85,
            severity=severity,
            description=f"Changed factual content: {', '.join(list(changed)[:3])}",
        ))

    # STYLE: mostly punctuation/formatting changes
    word_diff = len(old_words.symmetric_difference(new_words))
    char_diff = sum(1 for a, b in zip(old_text, new_text, strict=False) if a != b)
    is_punctuation_heavy = (
        word_diff <= 2
        and char_diff > 0
        and char_diff <= max(5, len(old_text) * 0.15)
    )
    if is_punctuation_heavy:
        results.append(EditClassification(
            category="STYLE",
            confidence=0.75,
            severity=severity,
            description="Punctuation or formatting change",
        ))

    # STRUCTURE: same words but different arrangement
    if old_words == new_words and old_text.strip() != new_text.strip():
        results.append(EditClassification(
            category="STRUCTURE",
            confidence=0.80,
            severity=severity,
            description="Content reordered or reformatted",
        ))

    # STRUCTURE: heading/list markers changed
    old_markers = len(_STRUCTURE_MARKERS.findall(old_text))
    new_markers = len(_STRUCTURE_MARKERS.findall(new_text))
    if abs(old_markers - new_markers) >= 2:
        results.append(EditClassification(
            category="STRUCTURE",
            confidence=0.70,
            severity=severity,
            description="List or heading structure changed",
        ))

    # PROCESS: behavioral/workflow corrections
    process_in_new = sum(1 for w in _PROCESS_WORDS if w in new_words and w not in old_words)
    process_in_old = sum(1 for w in _PROCESS_WORDS if w in old_words and w not in new_words)
    if process_in_new >= 2 or (process_in_new >= 1 and process_in_old == 0):
        added_process = [w for w in _PROCESS_WORDS if w in new_words and w not in old_words]
        results.append(EditClassification(
            category="PROCESS",
            confidence=0.75,
            severity=severity,
            description=f"Behavioral/process correction (added: {', '.join(list(added_process)[:4])})",
        ))

    # TONE: hedging/formality words added or removed
    tone_added = sum(1 for w in _TONE_WORDS if w in new_lower and w not in old_lower)
    tone_removed = sum(1 for w in _TONE_WORDS if w in old_lower and w not in new_lower)
    if tone_added + tone_removed >= 2:
        direction = "softened" if tone_added > tone_removed else "strengthened"
        results.append(EditClassification(
            category="TONE",
            confidence=0.70,
            severity=severity,
            description=f"Tone {direction} ({tone_added} added, {tone_removed} removed)",
        ))

    # TONE: formality shift (formal→casual or casual→formal)
    formal_in_old = sum(1 for m in _FORMAL_MARKERS if m in old_lower)
    formal_in_new = sum(1 for m in _FORMAL_MARKERS if m in new_lower)
    casual_in_old = sum(1 for m in _CASUAL_MARKERS if m in old_lower)
    casual_in_new = sum(1 for m in _CASUAL_MARKERS if m in new_lower)
    formality_shift = (formal_in_old - formal_in_new) + (casual_in_new - casual_in_old)
    if abs(formality_shift) >= 1:
        direction = "casualized" if formality_shift > 0 else "formalized"
        results.append(EditClassification(
            category="TONE",
            confidence=0.80,
            severity=severity,
            description=f"Tone {direction} (formality shift: {formality_shift:+d})",
        ))

    # CONTENT: always check for substantive word changes
    added = new_words - old_words
    removed = old_words - new_words
    added_meaningful = _meaningful_words(added)
    removed_meaningful = _meaningful_words(removed)
    if added_meaningful or removed_meaningful:
        desc_parts = []
        if removed_meaningful:
            desc_parts.append(f"cut: {', '.join(removed_meaningful[:5])}")
        if added_meaningful:
            desc_parts.append(f"added: {', '.join(added_meaningful[:5])}")
        results.append(EditClassification(
            category="CONTENT",
            confidence=0.60,
            severity=severity,
            description=f"Content change ({'; '.join(desc_parts)})",
        ))

    # Fallback: if nothing matched, still return a CONTENT classification
    if not results:
        results.append(EditClassification(
            category="CONTENT",
            confidence=0.50,
            severity=severity,
            description="Content change (modified)",
        ))

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_edits(diff: DiffResult) -> list[EditClassification]:
    """Classify each changed section in a DiffResult.

    Returns all applicable classifications per changed section.
    Empty list if no changes detected.
    """
    if not diff.changed_sections:
        return []

    results: list[EditClassification] = []
    for section in diff.changed_sections:
        results.extend(_classify_section(
            section.old_text,
            section.new_text,
            diff.severity,
        ))
    return results


def summarize_edits(classifications: list[EditClassification]) -> str:
    """Produce a human-readable summary of edit classifications.

    Includes semantic descriptions so lessons capture *what* changed,
    not just category counts.

    Example: "Tone formal→casual; Content change (shortened, removed hedging)"
    """
    if not classifications:
        return ""

    # Collect unique descriptions, preserving order
    seen: set[str] = set()
    parts: list[str] = []
    for c in classifications:
        desc = c.description.strip()
        if desc and desc.lower() not in seen:
            seen.add(desc.lower())
            parts.append(desc)

    if parts:
        return "; ".join(parts[:5])  # Cap at 5 to keep lesson descriptions concise

    # Fallback: category counts if no descriptions available
    counts: Counter[str] = Counter()
    severities: dict[str, str] = {}
    for c in classifications:
        counts[c.category] += 1
        severities[c.category] = c.severity
    fallback_parts = [
        f"{count} {cat} ({severities.get(cat, 'unknown')})"
        for cat, count in counts.most_common()
    ]
    total = sum(counts.values())
    return f"{total} edit{'s' if total != 1 else ''}: {', '.join(fallback_parts)}"


# ---------------------------------------------------------------------------
# Behavioral Instruction Extraction (v0.4.0)
# ---------------------------------------------------------------------------

_INSTRUCTION_TEMPLATES: dict[str, str] = {
    # ── CODE patterns (30+) ──────────────────────────────────────────
    "getattr": "Use getattr() for safe attribute access on objects that may lack the attribute",
    "valueerror,typeerror": "Add explicit ValueError/TypeError guards for invalid inputs",
    "except,try,false": "Wrap risky operations in try/except with explicit error handling",
    "collections,callable,import,abc": "Import from collections.abc for abstract base types",
    "list,str,int": "Add explicit type hints for function parameters and return values",
    "optional,defined,ignore,type": "Use Optional[] and type: ignore for conditional imports",
    "hash": "Use hash() or __hash__ instead of hashlib for non-cryptographic hashing",
    "noqa": "Suppress specific linter warnings with targeted noqa comments",
    "logging,getlogger": "Use module-level logger via logging.getLogger(__name__)",
    "none,else,true": "Handle None/falsy cases explicitly with early returns",
    "async,await": "Use async/await for I/O-bound operations instead of blocking calls",
    "pathlib": "Use pathlib.Path instead of os.path for file system operations",
    "f-string,format": "Use f-strings for string formatting instead of .format() or %",
    "dataclass": "Use dataclasses for simple data containers instead of plain dicts",
    "enum": "Use Enum for fixed sets of values instead of string constants",
    "walrus,:=": "Use walrus operator := when the assignment result is immediately needed",
    "comprehension": "Use list/dict/set comprehensions for simple transformations",
    "generator,yield": "Use generators for lazy evaluation of large sequences",
    "contextmanager": "Use context managers (with statement) for resource cleanup",
    "slots": "Add __slots__ to data-heavy classes to reduce memory usage",
    "abstract,abc": "Use ABC for interfaces that must be implemented by subclasses",
    "property": "Use @property for computed attributes instead of getter methods",
    "defaultdict": "Use collections.defaultdict to avoid KeyError on missing keys",
    "isinstance": "Use isinstance() for type checks instead of type() == comparisons",
    "guard,clause": "Use guard clauses (early return) to reduce nesting depth",
    "constant,magic": "Extract magic numbers into named constants with clear intent",
    "docstring": "Add docstrings to public functions explaining purpose, args, and returns",
    "dry,duplicate": "Extract duplicated code into a shared helper function",
    "import,lazy": "Use lazy imports for heavy dependencies to speed up module loading",
    "frozen,immutable": "Use frozen dataclasses or tuples for immutable data structures",
    "lru_cache,cache": "Use functools.lru_cache for expensive pure function results",
    "protocol,structural": "Use typing.Protocol for structural subtyping instead of ABCs",
    # ── TONE patterns (15+) ──────────────────────────────────────────
    "casualized": "Write in a casual, direct tone — avoid formal business language",
    "formalized": "Use professional, formal tone for this context",
    "softened": "Use softer, more empathetic language",
    "strengthened": "Be more direct and assertive — remove hedging words",
    "concise,shorter": "Cut unnecessary words — say more with less",
    "verbose,expand": "Add more detail and explanation for clarity",
    "empathetic": "Acknowledge the reader's situation before giving advice",
    "authoritative": "Write with confidence — remove qualifiers like 'maybe' and 'I think'",
    "humble,tentative": "Use tentative language to invite discussion rather than dictate",
    "enthusiastic": "Add energy and positive framing without being over-the-top",
    "neutral,objective": "Remove opinion and emotional language — stick to facts",
    "encouraging": "Frame feedback positively — lead with what's working before suggesting changes",
    "technical,precise": "Use precise technical terminology instead of vague descriptions",
    "simple,plain": "Use plain language — avoid jargon the audience won't understand",
    "urgent,action": "Create urgency — make the call to action clear and time-bound",
    # ── PROCESS patterns (15+) ───────────────────────────────────────
    "first,plan": "Always plan before implementing — plan then adversary review then build",
    "check,verify": "Verify data and assumptions before acting on them",
    "approve,review": "Get review or approval before proceeding with changes",
    "audit,before": "Audit existing code/state before making modifications",
    "before,research": "Research the topic thoroughly before producing output",
    "test,after": "Run tests after every code change to catch regressions early",
    "commit,atomic": "Make atomic commits — each commit should do one logical thing",
    "backup,before": "Save a backup or checkpoint before making destructive changes",
    "document,decision": "Document the reasoning behind decisions, not just the outcome",
    "prioritize,urgent": "Address the most impactful or time-sensitive items first",
    "batch,parallel": "Batch independent operations together for efficiency",
    "incremental": "Make changes incrementally — small steps with verification between each",
    "rollback": "Always have a rollback plan before deploying changes",
    "monitor,after": "Monitor the system after changes to catch unexpected side effects",
    "scope,limit": "Define scope before starting — resist expanding mid-task",
    "delegate,escalate": "Escalate blockers immediately instead of spinning on them",
    # ── STRUCTURE patterns (10+) ─────────────────────────────────────
    "reordered": "Present information in a more logical order",
    "heading,structure": "Use clear heading hierarchy for document structure",
    "bullet,list": "Use bullet points for lists of 3+ items instead of inline enumeration",
    "numbered,steps": "Use numbered lists for sequential steps, bullets for unordered items",
    "table,comparison": "Use a table when comparing multiple items across shared attributes",
    "tldr,summary": "Start with a summary/TL;DR for long documents",
    "section,break": "Break long sections into smaller subsections with descriptive headings",
    "code,block": "Use fenced code blocks for code snippets — never inline for multi-line code",
    "link,reference": "Add hyperlinks to referenced resources instead of just naming them",
    "callout,warning": "Use callouts or admonitions to highlight warnings, tips, and notes",
    # ── ACCURACY patterns (10+) ──────────────────────────────────────
    "source,cite": "Include source links when citing data or statistics",
    "date,timezone": "Double-check date calculations and timezone handling",
    "number,round": "Round percentages to whole numbers unless decimal precision matters",
    "acronym,spell": "Spell out acronyms on first use in any document",
    "crossref": "Cross-reference numbers between sections of the same document",
    "unit,conversion": "Include units with all measurements and verify unit conversions",
    "name,spelling": "Verify the spelling of proper nouns — names, companies, products",
    "version,current": "Check that referenced software versions and API endpoints are current",
    "quote,exact": "Use exact quotes when attributing statements — don't paraphrase in quotes",
    "math,formula": "Show your work for calculations so readers can verify the math",
    # ── COMMUNICATION patterns (10+) ─────────────────────────────────
    "subject,email": "Keep email subject lines under 50 characters and action-oriented",
    "context,open": "Start messages with context before making a request",
    "cta,clear": "End with a clear call-to-action — what should the reader do next?",
    "thread,reply": "Reply in the existing thread instead of starting a new one",
    "recipient,cc": "Only CC people who need to be informed, not everyone",
    "attachment,mention": "Mention attachments explicitly in the email body",
    "followup,timing": "Follow up within 24-48 hours if no response to important requests",
    "meeting,agenda": "Include an agenda when scheduling meetings",
    "async,written": "Default to async written communication over real-time meetings",
    "feedback,specific": "Give specific, actionable feedback — not vague impressions",
    # ── DRAFTING patterns (10+) ──────────────────────────────────────
    "lede,first": "Lead with the key takeaway — don't bury the lede",
    "active,voice": "Use active voice over passive voice in all writing",
    "transition,flow": "Use transition phrases to connect paragraphs logically",
    "redundant,remove": "Remove redundant phrases — 'in order to' → 'to', 'at this point in time' → 'now'",
    "specific,concrete": "Replace vague language with specific, concrete details",
    "parallel,grammar": "Use parallel grammatical structure in lists and comparisons",
    "shorter,sentence": "Break long sentences into shorter ones for readability",
    "strong,verb": "Use strong verbs instead of weak verb + adverb combinations",
    "delete,filler": "Delete filler words: 'very', 'really', 'just', 'quite', 'actually'",
    "proofread,final": "Proofread the final version for typos and grammatical errors",
}


def _match_template(classification: EditClassification) -> str | None:
    desc_lower = classification.description.lower()

    for keyword in ("casualized", "formalized", "softened", "strengthened"):
        if keyword in desc_lower:
            return _INSTRUCTION_TEMPLATES.get(keyword)

    if "reordered" in desc_lower or "reformatted" in desc_lower:
        return _INSTRUCTION_TEMPLATES.get("reordered")

    added_match = re.search(r"added:\s*([^)]+)", desc_lower)
    if added_match:
        added_words = [w.strip() for w in added_match.group(1).split(",")]
        # Try multi-word keys (sorted for consistency)
        for n in range(min(len(added_words), 4), 0, -1):
            key = ",".join(sorted(added_words[:n]))
            if key in _INSTRUCTION_TEMPLATES:
                return _INSTRUCTION_TEMPLATES[key]
        for word in added_words:
            if word in _INSTRUCTION_TEMPLATES:
                return _INSTRUCTION_TEMPLATES[word]

    return None


_EXTRACTION_TIMEOUT = 12.0  # seconds

# Cached provider instance — created on first LLM call
_provider_instance = None


def _get_llm_provider():
    """Get or create the LLM provider for extraction."""
    global _provider_instance
    if _provider_instance is None:
        from .llm_provider import get_provider
        _provider_instance = get_provider()
    return _provider_instance


def _call_llm_for_instruction(
    diff: DiffResult, classification: EditClassification,
) -> str | None:
    """Call LLM to extract a behavioral instruction. Returns None on any failure."""
    import logging
    _log = logging.getLogger("gradata")

    old_text = ""
    new_text = ""
    for section in diff.changed_sections[:3]:
        old_text += section.old_text[:500] + "\n"
        new_text += section.new_text[:500] + "\n"

    prompt = (
        "A human corrected an AI's output. Extract ONE behavioral instruction "
        "that explains what the AI should do differently next time.\n\n"
        f"Category: {classification.category}\n"
        f"BEFORE:\n{old_text.strip()}\n\n"
        f"AFTER:\n{new_text.strip()}\n\n"
        "Reply with ONE imperative sentence (e.g., 'Use casual tone in emails' "
        "or 'Always validate input before processing'). No explanation."
    )

    try:
        provider = _get_llm_provider()
        text = provider.complete(prompt, max_tokens=100, timeout=_EXTRACTION_TIMEOUT)
        if text and 5 < len(text) < 200:
            return text
    except Exception as e:
        _log.debug("LLM instruction extraction failed: %s", e)

    return None


def extract_behavioral_instruction(
    diff: DiffResult,
    classification: EditClassification,
    *,
    cache: InstructionCache | None = None,
    llm_enabled: bool = True,
) -> str | None:
    """Extract a behavioral instruction from a correction.

    Resolution order: cache hit -> template match -> LLM extraction -> None.
    """
    from .instruction_cache import InstructionCache

    added_match = re.search(r"added:\s*([^)]+)", classification.description.lower())
    cut_match = re.search(r"cut:\s*([^);]+)", classification.description.lower())
    added_words = [w.strip() for w in added_match.group(1).split(",")] if added_match else []
    removed_words = [w.strip() for w in cut_match.group(1).split(",")] if cut_match else []
    cache_key = InstructionCache.make_key(classification.category, added_words, removed_words)

    if cache:
        cached = cache.get(cache_key)
        if cached:
            return cached

    template = _match_template(classification)
    if template:
        if cache:
            cache.put(cache_key, template)
        return template

    if llm_enabled:
        instruction = _call_llm_for_instruction(diff, classification)
        if instruction and cache:
            cache.put(cache_key, instruction)
        return instruction

    return None
